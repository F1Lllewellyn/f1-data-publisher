"""Execute integrated-loop publication with isolated Git and explicit HOLD state."""
import os
import subprocess
import textwrap
import unittest
import test_f1_1b_integrated_recovery_publication as publication


class IntegratedPublicationTests(unittest.TestCase):
    git = publication.BridgePublicationTests.git
    write = publication.BridgePublicationTests.write
    remote_head = publication.BridgePublicationTests.remote_head

    def setUp(self):
        publication.BridgePublicationTests.setUp(self)
        self.write('_runtime/autorepair_integrated_health/start.marker', '', 20)
        self.write('_runtime/autorepair/session_workbook_recovery/commit_allowed.txt', 'true')
        self.write('latest/readiness_dashboards/combined_readiness_dashboard.json', '{"downstream_eligible":false,"prediction_locked":false}', 30)
        self.write('history/readiness_dashboards/old.json', '{}', 10)
        self.write('history/readiness_dashboards/new.json', '{}', 30)

    def publish(self):
        text = (publication.ROOT/'.github/workflows/f1-session-autorepair-integrated-loop-v1.yml').read_text()
        shell = textwrap.dedent(text.split('- name: Commit source-backed integrated outputs', 1)[1].split('run: |', 1)[1])
        return subprocess.run(['bash', '-c', shell], cwd=self.root, capture_output=True, text=True,
            env=dict(os.environ, GITHUB_REF_NAME='main', F1_SAFE_PUSH_SLEEP_SECONDS='0'), timeout=15)

    def test_source_publication_is_bounded_and_repeat_is_noop(self):
        r = self.publish(); self.assertEqual(r.returncode, 0, r.stderr+r.stdout)
        changed = set(self.git('diff', '--name-only', self.base, 'HEAD').stdout.splitlines())
        self.assertEqual(changed, {'history/session_data_processor/upstream.json',
            'latest/workbook_kpi_refresh_applier/upstream.xlsx',
            'latest/readiness_dashboards/combined_readiness_dashboard.json', 'history/readiness_dashboards/new.json'})
        head = self.remote_head(); self.assertEqual(self.publish().returncode, 0); self.assertEqual(self.remote_head(), head)

    def test_hold_publishes_only_explicit_fresh_diagnostics(self):
        self.write('_runtime/autorepair/session_workbook_recovery/commit_allowed.txt', 'false')
        r = self.publish(); self.assertEqual(r.returncode, 0, r.stderr+r.stdout)
        self.assertEqual(set(self.git('diff', '--name-only', self.base, 'HEAD').stdout.splitlines()), {
            'latest/readiness_dashboards/combined_readiness_dashboard.json', 'history/readiness_dashboards/new.json'})

    def test_false_diagnostic_ready_and_protected_mutation_do_not_publish(self):
        self.write('_runtime/autorepair/session_workbook_recovery/commit_allowed.txt', 'false')
        self.write('latest/readiness_dashboards/combined_readiness_dashboard.json', '{"downstream_eligible":true,"prediction_locked":false}', 30)
        self.assertNotEqual(self.publish().returncode, 0); self.assertEqual(self.remote_head(), self.base)
        self.write('Engine_2026-06-07_STABLE', 'changed')
        self.assertIn('HOLD_PROTECTED_ASSET_MUTATION', self.publish().stdout)

    def test_tracked_history_mutation_is_rejected(self):
        self.write('history/sentinel.json', '{"original":true}')
        self.git('add', 'history/sentinel.json'); self.git('commit', '-m', 'historic sentinel'); self.git('push')
        head = self.remote_head(); self.write('history/sentinel.json', '{"original":false}')
        self.assertIn('HOLD_HISTORICAL_EVIDENCE_MUTATION', self.publish().stdout)
        self.assertEqual(self.remote_head(), head)

    def test_legacy_yield_requires_verified_capture_not_timestamp_only(self):
        text = (publication.ROOT/'.github/workflows/f1-session-autorepair-integrated-loop-v1.yml').read_text()
        self.assertIn('guard.json &&', text)
        self.assertIn('--operation verify_bridge_input; then', text)
