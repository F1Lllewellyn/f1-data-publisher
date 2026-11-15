"""Same-run byte custody and bounded real-Git Peak publication; all data synthetic."""
import copy
import json
import os
from pathlib import Path
import subprocess
import textwrap
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import test_sp2026_integrated_recovery_guard_v1 as fixtures
import test_f1_1b_integrated_recovery_publication as publication
from test_sp2026_integrated_recovery_guard_v1 import dashboard_mod, peak_mod, write
from test_f1_1b_integrated_recovery_publication import ROOT


class PeakHandoffTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.CurrentSessionReadinessTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.now = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)
        current = dashboard_mod.discover_state(self.root, reference_time=self.now)
        write(self.root / 'latest/readiness_dashboards/combined_readiness_dashboard.json', current)
        mandatory = ['latest/latest_manifest.json', 'latest/data_readiness.json',
                     'latest/combined_source_manifest.json',
                     'latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json',
                     'latest/readiness_dashboards/combined_readiness_dashboard.json']
        self.status = dict(operation='full_run_chain', created_utc='2026-11-07T17:01:00Z',
            github_run_id='1234', github_run_attempt='1', workflow_head_sha='a'*40,
            downstream_current=True, commit_allowed=True, failed_steps=[],
            latest_state=dict(event_id=current['event_id'], session_key=current['session_key']),
            handoff_fingerprints=peak_mod.byte_fingerprints(self.root, mandatory + list(current['consumed_fingerprints'])),
            steps=[dict(label=label, ok=True, started_utc='2026-11-07T17:00:00Z') for label in
                   ('session_data_processor_run_now', 'workbook_kpi_refresh_apply', 'dashboard_readiness_publish')])
        self.env = dict(GITHUB_EVENT_NAME='workflow_run', UPSTREAM_RUN_ID='1234', UPSTREAM_RUN_ATTEMPT='1', UPSTREAM_HEAD_SHA='a'*40)

    def observe(self, status=None, now=None):
        write(self.root / 'latest/peak_elite/orchestrator_status.json', self.status if status is None else status)
        with patch.dict(os.environ, self.env):
            return peak_mod.verify_bridge_input(self.root, reference_time=now or self.now)

    def test_exact_run_and_bytes_verify_context_without_claiming_prediction(self):
        r = self.observe()
        self.assertEqual(r['status'], 'VERIFIED_CONTEXT_ONLY', r)
        for key in ('prediction_locked', 'stable_engine_executed', 'promotion_allowed'):
            self.assertIs(r[key], False)

    def test_wrong_run_attempt_or_sha_holds(self):
        for field in ('github_run_id', 'github_run_attempt', 'workflow_head_sha'):
            with self.subTest(field=field):
                s = copy.deepcopy(self.status); s[field] = 'other'
                self.assertIn('HOLD_UPSTREAM_RUN_MISMATCH:'+field, self.observe(s)['reasons'])

    def test_missing_capture_failed_stage_and_old_capture_do_not_become_success(self):
        for mutate in (lambda s: s.update(operation='health_only'),
                       lambda s: s.update(failed_steps=['session_data_processor_run_now']),
                       lambda s: s['steps'].pop(),
                       lambda s: s['steps'][0].update(started_utc='2026-11-07T17:00:50Z')):
            s = copy.deepcopy(self.status); mutate(s)
            self.assertEqual(self.observe(s)['status'], 'HOLD')

    def test_every_bound_byte_is_checked_and_omitted_raw_binding_is_rejected(self):
        for relative in self.status['handoff_fingerprints']:
            path = self.root / relative; raw = path.read_bytes()
            with self.subTest(path=relative):
                path.write_bytes(raw+b' ')
                self.assertEqual(self.observe()['status'], 'HOLD')
                path.write_bytes(raw)
        s = copy.deepcopy(self.status)
        raw_key = next(p for p in s['handoff_fingerprints'] if '/raw/' in p)
        del s['handoff_fingerprints'][raw_key]
        self.assertIn('HOLD_UPSTREAM_CUSTODY_INCOMPLETE', self.observe(s)['reasons'])

    def test_newer_qualifying_supersedes_fp3_even_when_report_bytes_match(self):
        r = self.observe(now=datetime(2026, 11, 7, 20, 30, tzinfo=timezone.utc))
        self.assertIn('HOLD_UPSTREAM_SESSION_NOT_CURRENT', r['reasons'])

    def test_future_stale_or_malformed_reports_hold_without_exception(self):
        for status in ([], 1, 'bad', dict(self.status, created_utc='2026-11-08T00:00:00Z'),
                       dict(self.status, handoff_fingerprints=42), dict(self.status, steps=[None])):
            with self.subTest(status=status):
                self.assertEqual(self.observe(status)['status'], 'HOLD')


class PeakPublicationTests(unittest.TestCase):
    git = publication.BridgePublicationTests.git
    write = publication.BridgePublicationTests.write
    remote_head = publication.BridgePublicationTests.remote_head

    def setUp(self):
        publication.BridgePublicationTests.setUp(self)
        # Ignore workbook archives just as the repository does: only fresh approved
        # sandbox artifacts are force-added, never old archives or canonical files.
        self.write('.gitignore', '_runtime/\n*.xlsx\n')
        self.git('add', '.gitignore'); self.git('commit', '-m', 'sandbox ignores')
        self.git('push'); self.base = self.remote_head()
        self.write('_runtime/peak_elite/start.marker', '', 20)
        self.write('latest/peak_elite/orchestrator_status.json', '{"commit_allowed":true}', 30)
        self.write('latest/data_readiness.json', '{"state":"HOLD"}', 30)
        self.write('history/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_OLD.xlsx', 'old', 10)
        self.write('history/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_NEW.xlsx', 'new', 30)

    def publish(self):
        path = ROOT / '.github/workflows/f1-peak-elite-control-room-one-click-v1.yml'
        script = textwrap.dedent(path.read_text().split('- name: Commit safe repaired workflows', 1)[1].split('run: |', 1)[1])
        script = script.replace('${{ inputs.commit_outputs }}', 'true')
        return subprocess.run(['bash', '-c', script], cwd=self.root,
            env=dict(os.environ, GITHUB_REF_NAME='main', F1_SAFE_PUSH_SLEEP_SECONDS='0'),
            capture_output=True, text=True, timeout=15)

    def test_only_current_owned_files_publish_and_duplicate_is_noop(self):
        r = self.publish(); self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        paths = set(self.git('diff', '--name-only', self.base, 'HEAD').stdout.splitlines())
        self.assertEqual(paths, {'latest/peak_elite/orchestrator_status.json', 'latest/data_readiness.json',
            'history/session_data_processor/upstream.json',
            'history/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_NEW.xlsx'})
        first = self.remote_head()
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.remote_head(), first)

    def test_missing_marker_and_preexisting_index_cannot_publish(self):
        self.git('add', 'README.md')  # unchanged file does not dirty the index
        self.write('README.md', 'unowned mutation'); self.git('add', 'README.md')
        self.assertIn('HOLD_PRESTAGED_INPUT', self.publish().stdout)
        self.assertEqual(self.remote_head(), self.base)

    def test_protected_asset_code_and_history_mutation_cannot_publish(self):
        self.write('Engine_2026-06-07_STABLE', 'changed')
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertEqual(self.remote_head(), self.base)
        self.write('Engine_2026-06-07_STABLE', 'protected sentinel\n')
        self.write('scripts/ops/safe_git_push_rebase_retry.sh', '# changed code')
        self.assertIn('HOLD_UNREVIEWED_CODE_MUTATION', self.publish().stdout)
        self.assertEqual(self.remote_head(), self.base)

    def test_publication_denied_and_rejected_remote_preserve_original_remote(self):
        self.write('latest/peak_elite/orchestrator_status.json', '{"commit_allowed":false}', 30)
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertEqual(self.remote_head(), self.base)
        self.write('latest/peak_elite/orchestrator_status.json', '{"commit_allowed":true}', 30)
        hook = self.remote/'hooks/pre-receive'; hook.write_text('#!/bin/sh\nexit 1\n'); hook.chmod(0o755)
        self.assertNotEqual(self.publish().returncode, 0)
        self.assertEqual(self.remote_head(), self.base)
        self.assertNotEqual(self.git('rev-parse', 'HEAD').stdout.strip(), self.base)
