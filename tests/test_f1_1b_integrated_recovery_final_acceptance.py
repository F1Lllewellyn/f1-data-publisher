"""Offline publication races and explicit reproductions of unapproved boundaries.

Passing a boundary reproduction means the HOLD is proved, not that the legacy
component is scientifically accepted. All legacy output stays in temporary roots.
"""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import test_f1_1b_integrated_recovery_publication as publication
import test_f1_1b_integrated_recovery_peak_handoff as handoff
import test_f1_producer_lock_custody_gate as gate_tests
import test_openf1_normal_incremental_collection_budget_v1 as incremental
import test_sp2026_integrated_recovery_guard_v1 as fixtures

ROOT = publication.ROOT


def report(name, evidence):
    target = os.environ.get('F1_RECOVERY_REPORT_DIR')
    if target:
        path = Path(target)
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + '.json')).write_text(json.dumps(evidence, indent=2) + '\n')


class PublicationRaceTests(unittest.TestCase):
    setUp = publication.BridgePublicationTests.setUp
    git = publication.BridgePublicationTests.git
    write = publication.BridgePublicationTests.write
    publish = publication.BridgePublicationTests.publish
    remote_head = publication.BridgePublicationTests.remote_head

    def competing_push(self, relative, content):
        other = self.root.parent / 'competing-checkout'
        self.git('clone', str(self.remote), str(other))

        def git(*args):
            return subprocess.run(['git', *args], cwd=other, capture_output=True,
                                  text=True, check=True)

        git('checkout', 'main')
        git('config', 'user.name', 'Isolated competing publisher')
        git('config', 'user.email', 'test@example.invalid')
        path = other / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        git('add', relative)
        git('commit', '-m', 'isolated remote advance')
        git('push', 'origin', 'HEAD:main')
        return self.remote_head()

    def test_remote_advance_rebases_unpublished_commit_without_losing_either_output(self):
        remote_before = self.competing_push('unrelated.txt', 'remote-owned bytes\n')
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('push attempt 2/3', result.stdout)
        self.assertEqual(self.git('merge-base', '--is-ancestor', remote_before,
                                  self.remote_head(), check=False).returncode, 0)
        for path, expected in (
            ('unrelated.txt', 'remote-owned bytes\n'),
            ('latest/readiness_handoff/current.json', '{"state":"HOLD"}\n'),
            ('Engine_2026-06-07_STABLE', 'protected sentinel\n'),
        ):
            self.assertEqual(self.git('--git-dir=' + str(self.remote),
                                      'show', 'main:' + path).stdout, expected)
        report('isolated_push_race', dict(status='PASS_OFFLINE',
            remote_parent=remote_before, published_head=self.remote_head(),
            attempts=2, both_writers_preserved=True, protected_sentinel_unchanged=True,
            production_deployed=False, prediction_locked=False))

    def test_conflicting_remote_advance_aborts_rebase_and_preserves_local_evidence(self):
        remote_before = self.competing_push('latest/readiness_handoff/current.json',
                                             '{"state":"REMOTE_HOLD"}\n')
        result = self.publish()
        self.assertEqual(result.returncode, 20, result.stdout + result.stderr)
        self.assertIn('rebase conflict; aborting safely', result.stdout)
        self.assertEqual(self.remote_head(), remote_before)
        self.assertNotEqual(self.git('rev-parse', 'HEAD').stdout.strip(), self.base)
        self.assertEqual(self.git('show', 'HEAD:latest/readiness_handoff/current.json').stdout,
                         '{"state":"HOLD"}\n')
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=no').stdout, '')
        self.assertFalse((self.root / '.git/rebase-merge').exists())
        self.assertFalse((self.root / '.git/rebase-apply').exists())
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'show',
                                  'main:Engine_2026-06-07_STABLE').stdout,
                         'protected sentinel\n')


class ScopeBoundaryTests(unittest.TestCase):
    def test_global_provider_repair_contract(self):
        from test_f1_1b_integrated_recovery_provider_coordination import ProviderCoordinationTests
        case=ProviderCoordinationTests()
        case.test_cancelled_or_finished_process_handover_protects_both_windows()
        case.test_actual_entry_points_share_admission_and_single_scheduled_capture_owner()
        report('global_provider_scope_boundary',dict(status='PASS_OFFLINE',global_coordination_verified=True,real_provider_requests=0,production_deployed=False))

    def test_high_frequency_client_reuses_accepted_provider_budget(self):
        from test_f1_1b_integrated_recovery_provider_coordination import ProviderCoordinationTests
        case=ProviderCoordinationTests()
        case.test_actual_high_frequency_client_respects_limits_and_preserves_token()
        case.test_access_throttle_and_outage_latch_without_retry_storm()
        report('legacy_provider_scope_boundary',dict(status='PASS_OFFLINE',real_provider_requests=0,production_deployed=False))

    def test_v25_duplicate_preserves_history_and_verified_bridge(self):
        fixture = handoff.ConsumerOutputCustodyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        history = next((fixture.root / 'history/chat_context').rglob('combined_context_index.json'))
        before = history.read_bytes()
        with patch.object(fixture.context, 'utc_now_iso', return_value='2026-11-07T18:01:00Z'):
            fixture.context.run(fixture.root)
        self.assertEqual(history.read_bytes(), before)
        self.assertEqual(fixture.observe()['status'], 'VERIFIED_CONTEXT_ONLY')

    def test_rows_only_direct_validator_and_locker_fail_closed(self):
        fixture = gate_tests.GateCustodyTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        locker = fixtures.load_module('final_acceptance_locker','scripts/forecast_bundles/create_forecast_bundles_v1.py')
        event,gate_name,lane='SYNTHETIC_SCOPE_BOUNDARY','post_qualifying','stable_baseline'
        source=fixture.root/'latest/forecasts'/event/gate_name/lane/'forecast_rows.csv'
        source.parent.mkdir(parents=True);source.write_text('driver_name,predicted_race_finish_position\nSYNTHETIC DRIVER,1\n')
        original=source.read_bytes()
        checked=subprocess.run([sys.executable,str(ROOT/'scripts/forecast_bundles/validate_forecast_chain_readiness_v1.py'),
            '--repo',str(fixture.root),'--event-id',event,'--gate',gate_name,'--lane',lane,'--strict'],capture_output=True,text=True,timeout=15)
        self.assertEqual(checked.returncode,2,checked.stderr)
        self.assertEqual(json.loads(checked.stdout)['reason'],'HOLD_STABLE_ENGINE_NOT_EXECUTED')
        with self.assertRaisesRegex(RuntimeError,'HOLD_STABLE_ENGINE_NOT_EXECUTED'):
            locker.create_bundle(fixture.root,event,'2026','','SYNTHETIC',gate_name,lane,fixture.root,True)
        self.assertEqual(source.read_bytes(),original);self.assertFalse((fixture.root/'history').exists())
        report('direct_locker_scope_boundary',dict(status='PASS_FAIL_CLOSED',scientific_status='HOLD_STABLE_ENGINE_NOT_EXECUTED',
            blind_validation_eligible=False,stable_engine_execution_proven=False,scientific_prediction_locked=False))

    def test_direct_workflow_options_reach_scientific_hold_not_argparse_failure(self):
        fixture=gate_tests.GateCustodyTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        for workflow_name,script,extra in (
            ('f1-forecast-bundle-locker-v1','create_forecast_bundles_v1.py',['--race-name','SYNTHETIC','--commit-latest']),
            ('f1-forecast-gate-source-writer-v1','write_gate_forecast_rows_v1.py',[])):
            with self.subTest(workflow=workflow_name):
                workflow=(ROOT/'.github/workflows'/(workflow_name+'.yml')).read_text()
                self.assertNotIn('--commit-outputs',workflow);self.assertIn('contents: read',workflow)
                result=subprocess.run([sys.executable,str(ROOT/'scripts/forecast_bundles'/script),'--repo-root',str(fixture.root),
                    '--event-id','SYNTHETIC_SCOPE_BOUNDARY',*extra],cwd=fixture.root,capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,2);self.assertNotIn('unrecognized arguments',result.stderr)
                self.assertIn('HOLD_STABLE_ENGINE_NOT_EXECUTED',result.stdout)
                self.assertFalse((fixture.root/'latest').exists());self.assertFalse((fixture.root/'history').exists())


class WorkflowPreflightTests(unittest.TestCase):
    def test_actual_workflow_preflights_pass_without_writing_repository_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [
                'scripts/session_data_processor/f1_1b_output_contract_v16.py',
                'scripts/session_data_processor/f1_1b_downstream_consumer_handoff_v24.py',
                'scripts/session_data_processor/f1_1b_consumer_context_publisher_v25.py',
                'scripts/ops/f1_canonical_chain_guard_v27.py',
                'scripts/ops/f1_openf1_live_restriction_guard_v27.py',
                '.github/workflows/f1-peak-elite-control-room-one-click-v1.yml',
                '.github/workflows/f1-session-autorepair-integrated-loop-v1.yml',
                '.github/workflows/f1-1b-output-contract-after-control-room-v22.yml',
                '.github/workflows/openf1-prerace-auto-ingest.yml',
            ]
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            bridge = (ROOT/'.github/workflows/f1-1b-output-contract-after-control-room-v22.yml').read_text()
            self.assertIn("python -m unittest discover -s tests -p 'test_f1_1b_integrated_recovery_consumer_custody.py' -v", bridge)
            self.assertNotIn('scripts/ops/f1_1b_v16_acceptance_tests_v1.py', bridge)
            results = []
            for name in ('f1_1b_v27_legacy_collision_hardening_acceptance_tests.py',
                         'f1_workbook_persistence_handoff_guard_v1.py'):
                with self.subTest(script=name):
                    args = [sys.executable, str(ROOT / 'scripts/ops' / name), '--repo-root', str(root)]
                    if name.startswith('f1_workbook'):
                        args += ['--mode', 'static', '--fail-on-issue']
                    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload['status'], 'pass')
                    results.append(dict(script=name, result=payload))
            report('workflow_preflights', dict(status='PASS_OFFLINE', results=results,
                   outputs_only_in_disposable_root=True, production_deployed=False))


if __name__ == '__main__':
    unittest.main()
