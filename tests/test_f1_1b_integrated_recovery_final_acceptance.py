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
    def test_two_independent_provider_budgets_do_not_form_a_global_budget(self):
        clock = incremental.FakeClock()
        budgets = [incremental.m.NormalRequestBudget(clock=clock.monotonic,
                    sleeper=clock.sleep) for _ in range(2)]
        requests = []
        for _ in range(16):
            for index, budget in enumerate(budgets):
                budget.acquire()
                requests.append((index, clock.monotonic()))
        self.assertEqual([b.total_requests for b in budgets], [16, 16])
        self.assertEqual(len(requests), 32)
        self.assertLess(requests[-1][1] - requests[0][1], 60)
        standalone = (ROOT / '.github/workflows/f1-session-data-processor-loop-v1.yml').read_text()
        integrated = (ROOT / '.github/workflows/f1-session-autorepair-integrated-loop-v1.yml').read_text()
        self.assertIn('group: f1-session-data-processor-loop-${{ github.ref }}', standalone)
        self.assertIn('group: f1-main-write-serialization', integrated)
        manual = (ROOT / '.github/workflows/f1-session-autorepair-integrated-run-now-button-v1.yml').read_text()
        self.assertIn('group: f1-session-autorepair-integrated-run-now-${{ github.ref }}', manual)
        report('global_provider_scope_boundary', dict(status='HOLD_SCOPE',
            proof='Two real budget instances admit 32 simulated requests within 60 seconds',
            simulated_requests=requests, real_provider_requests=0,
            production_rate_limit_incident_claimed=False, global_coordination_verified=False))

    def test_high_frequency_client_has_no_thirty_per_minute_budget(self):
        # Compile the exact committed client class without importing unrelated
        # parquet/report dependencies. No production HTTP request is possible.
        path = ROOT / 'scripts/openf1/openf1_high_frequency_auto_ingest.py'
        node = next(n for n in ast.parse(path.read_text()).body
                    if isinstance(n, ast.ClassDef) and n.name == 'OpenF1Client')
        clock = incremental.FakeClock()
        requests = []

        def get(*args, **kwargs):
            requests.append(clock.monotonic())
            return types.SimpleNamespace(status_code=200, text='[]',
                                         raise_for_status=lambda: None, json=lambda: [])

        namespace = dict(BASE_URL='https://provider.invalid',
                         requests=types.SimpleNamespace(get=get),
                         time=types.SimpleNamespace(sleep=clock.sleep))
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
        client = namespace['OpenF1Client'](token='', sleep_seconds=0.35)
        for _ in range(31):
            self.assertEqual(client.get('sessions')[1]['status_code'], 200)
        self.assertEqual(len(requests), 31)
        self.assertLess(requests[-1] - requests[0], 60)
        workflows = ('openf1-prerace-auto-ingest', 'openf1-post-race-auto-reliability',
                     'openf1-full-historical-auto-ingest')
        for name in workflows:
            text = (ROOT / '.github/workflows' / (name + '.yml')).read_text()
            self.assertIn('openf1_high_frequency_extract_checkpoint.py', text)
            self.assertIn('--request-sleep 0.35', text)
            self.assertNotIn('group: f1-main-write-serialization', text)
        report('legacy_provider_scope_boundary', dict(status='HOLD_SCOPE',
            simulated_successful_requests=31, elapsed_request_span_seconds=requests[-1] - requests[0],
            real_provider_requests=0, live_rate_limit_incident_claimed=False,
            client=str(path.relative_to(ROOT)), workflows=list(workflows)))

    def test_legacy_v25_duplicate_rewrites_history_and_bridge_detects_it(self):
        fixture = handoff.ConsumerOutputCustodyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        history = next((fixture.root / 'history/chat_context').rglob('combined_context_index.json'))
        before = history.read_bytes()
        with patch.object(fixture.context, 'utc_now_iso', return_value='2026-11-07T18:01:00Z'):
            fixture.context.run(fixture.root)
        self.assertNotEqual(history.read_bytes(), before)
        self.assertEqual(fixture.observe()['status'], 'HOLD')

    def test_legacy_rows_only_locker_claim_is_not_accepted_by_repaired_gate(self):
        fixture = gate_tests.GateCustodyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        locker = fixtures.load_module('final_acceptance_legacy_locker',
            'scripts/forecast_bundles/create_forecast_bundles_v1.py')
        event, gate_name, lane = 'SYNTHETIC_SCOPE_BOUNDARY', 'post_qualifying', 'stable_baseline'
        source = fixture.root / 'latest/forecasts' / event / gate_name / lane / 'forecast_rows.csv'
        source.parent.mkdir(parents=True)
        source.write_text('driver_name,predicted_race_finish_position\nSYNTHETIC DRIVER,1\n')
        checked = subprocess.run([sys.executable, str(ROOT / 'scripts/forecast_bundles/validate_forecast_chain_readiness_v1.py'),
            '--repo', str(fixture.root), '--event-id', event, '--gate', gate_name,
            '--lane', lane, '--strict'], capture_output=True, text=True, timeout=15)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)['status'], 'pass')
        with patch.object(locker, 'utcnow', return_value='2026-11-21T05:30:00Z'):
            created = locker.create_bundle(fixture.root, event, '2026', '', 'SYNTHETIC',
                gate_name, lane, fixture.root, False, include_existing_bundles=False)
        directory = Path(created['history_dir'])
        manifest = json.loads((directory / 'bundle_lock_manifest.json').read_text())
        config = json.loads((directory / 'engine_lane_config.json').read_text())
        self.assertTrue(manifest['blind_validation_eligible'])
        self.assertFalse(config['stable_engine_execution_proven'])
        original = {p: p.read_bytes() for p in directory.iterdir()}
        gate_module = gate_tests.gate
        with patch.object(sys, 'argv', ['gate', '--event-id', event]), \
             patch.object(gate_module, 'fetch_openf1_sessions', return_value=gate_tests.catalog()), \
             patch.object(gate_module, 'utc_now', return_value=gate_module.parse_time('2026-11-21T05:30:00Z')), \
             patch.object(gate_module, 'run_command') as commands, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate_module.main(), 2)
        commands.assert_not_called()
        result = json.loads((gate_module.RUNTIME / 'orchestrator_result.json').read_text())
        self.assertEqual(result['reason'], 'HOLD_STABLE_ENGINE_NOT_EXECUTED')
        self.assertFalse(result['prediction_locked'])
        self.assertEqual(original, {p: p.read_bytes() for p in directory.iterdir()})
        report('direct_locker_scope_boundary', dict(status='HOLD_SCOPE',
            legacy_validator_status='pass', legacy_blind_validation_eligible=True,
            stable_engine_execution_proven=False, repaired_gate=result['reason'],
            scientific_prediction_locked=False, generated_only_in_disposable_test_root=True))

    def test_direct_locker_workflow_option_is_rejected_before_any_output(self):
        fixture = gate_tests.GateCustodyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for workflow_name, script, extra in (
            ('f1-forecast-bundle-locker-v1', 'create_forecast_bundles_v1.py', ['--race-name', 'SYNTHETIC']),
            ('f1-forecast-gate-source-writer-v1', 'write_gate_forecast_rows_v1.py', []),
        ):
            with self.subTest(workflow=workflow_name):
                workflow = (ROOT / '.github/workflows' / (workflow_name + '.yml')).read_text()
                self.assertIn('args+=(--commit-outputs)', workflow)
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/forecast_bundles' / script),
                    '--repo-root', str(fixture.root), '--event-id', 'SYNTHETIC_SCOPE_BOUNDARY',
                    *extra, '--commit-outputs'], cwd=fixture.root,
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 2)
                self.assertIn('unrecognized arguments: --commit-outputs', result.stderr)
                self.assertEqual(list(fixture.root.iterdir()), [])


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
            results = []
            for name in ('f1_1b_v16_acceptance_tests_v1.py', 'f1_1b_v24_acceptance_tests_v1.py',
                         'f1_1b_v25_acceptance_tests_v1.py',
                         'f1_1b_v27_legacy_collision_hardening_acceptance_tests.py',
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
