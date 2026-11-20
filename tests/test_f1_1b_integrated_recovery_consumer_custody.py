"""Actual v16/v24/v25 execution, synthetic sources, no provider or production writes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_f1_1b_integrated_recovery_peak_handoff as peak_fixture


class ConsumerCustodyTests(unittest.TestCase):
    def setUp(self):
        fixture = peak_fixture.ConsumerOutputCustodyTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture; self.root = fixture.root
        self.output, self.downstream, self.context = fixture.output, fixture.downstream, fixture.context
        self.enterContext(patch.object(self.output, 'utc_now', return_value=fixture.setup.now))
        for module in (self.downstream, self.context):
            self.enterContext(patch.object(module, 'utc_now_iso', return_value=fixture.setup.now.isoformat()))

    def files(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for folder in ('history','latest') for p in (self.root/folder).rglob('*') if p.is_file()}

    def run_chain(self):
        self.output.run(self.root); self.downstream.run(self.root); self.context.run(self.root)

    def test_duplicate_chain_is_byte_identical_and_noop(self):
        before=self.files()
        mtimes={p:p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()}
        self.run_chain()
        self.assertEqual(self.files(),before)
        self.assertTrue(all(p.stat().st_mtime_ns==v for p,v in mtimes.items()))

    def test_restart_restores_missing_latest_without_rewriting_history(self):
        before=self.files()
        (self.root/'latest/forecast_bundle_ledger/latest_bundle_snapshot.json').unlink()
        (self.root/'latest/downstream_consumers/race_predictions/consumer_input.json').unlink()
        self.run_chain()
        self.assertEqual(self.files(),before)

    def test_original_capture_identity_availability_and_bootstrap_hash_survive(self):
        bootstrap=json.loads((self.root/'latest/downstream_consumers/race_predictions/consumer_bootstrap.json').read_text())
        self.assertEqual(bootstrap['original_capture_run_id'],'synthetic_original_capture')
        self.assertEqual(bootstrap['capture_origin']['run_id'],'1234')
        self.assertEqual(bootstrap['capture_origin']['run_attempt'],'1')
        self.assertEqual(bootstrap['capture_origin']['head_sha'],'a'*40)
        self.assertEqual(bootstrap['event']['session_key'],11407)
        self.assertTrue(bootstrap['custody']['source_availability'])
        self.assertFalse(bootstrap['custody']['prediction_locked'])
        self.assertEqual(hashlib.sha256((self.root/bootstrap['context_path']).read_bytes()).hexdigest(),bootstrap['context_sha256'])

    def test_all_three_writers_reject_historical_collisions_before_latest_changes(self):
        for folder,module,pattern in [('forecast_bundle_ledger',self.output,'bundle_snapshot.json'),('downstream_consumers',self.downstream,'combined_downstream_consumer_manifest.json'),('chat_context',self.context,'race_predictions_context.md')]:
            with self.subTest(stage=folder):
                path=next((self.root/'history'/folder).rglob(pattern));raw=path.read_bytes();path.write_bytes(raw+b'corruption')
                before=self.files()
                with self.assertRaisesRegex(RuntimeError,'HOLD_IMMUTABLE_HISTORY_COLLISION'):module.run(self.root)
                self.assertEqual(self.files(),before)
                path.write_bytes(raw)

    def test_current_bytes_changed_between_load_and_write_hold(self):
        inputs=self.downstream.load_contract_inputs(self.root)
        payloads={c:self.downstream.build_consumer_payload(self.root,inputs,c) for c in self.downstream.CONSUMERS}
        path=self.root/'latest/combined_source_manifest.json';path.write_bytes(path.read_bytes()+b' ')
        before=self.files()
        with self.assertRaisesRegex(RuntimeError,'HOLD_'):self.downstream.write_outputs(self.root,payloads,inputs)
        self.assertEqual(self.files(),before)

    def test_v16_rechecks_source_before_any_output_is_written(self):
        snapshot=self.output.build_snapshot(self.root,'irrelevant')
        change=self.output.detect_material_change(self.root,snapshot)
        path=self.root/'latest/combined_source_manifest.json';path.write_bytes(path.read_bytes()+b' ')
        before=self.files()
        with self.assertRaisesRegex(RuntimeError,'HOLD_CURRENT_CONTEXT_CHANGED_BEFORE_PUBLICATION'):
            self.output.write_outputs(self.root,snapshot,change)
        self.assertEqual(self.files(),before)

    def test_missing_qualifying_cannot_reuse_green_fp3(self):
        with patch.object(self.output,'utc_now',return_value=self.output.dt.datetime(2026,11,7,20,30,tzinfo=self.output.dt.timezone.utc)):
            snapshot=self.output.build_snapshot(self.root,'irrelevant')
        self.assertFalse(snapshot['source_backed'])
        self.assertEqual(snapshot['custody']['expected_session_key'],11408)
        self.assertFalse(snapshot['handoffs']['race_predictions']['ready_for_use'])
        with patch.object(self.context,'utc_now_iso',return_value='2026-11-07T20:30:00Z'),self.assertRaisesRegex(RuntimeError,'HOLD_CURRENT_CONTEXT'):
            self.context.run(self.root)

    def test_wrong_original_attempt_or_consumer_payload_cannot_be_reused(self):
        path=self.root/'latest/downstream_consumers/race_predictions/consumer_input.json'
        data=json.loads(path.read_text());data['capture_origin']['run_attempt']='99';path.write_text(json.dumps(data))
        before=self.files()
        with self.assertRaisesRegex(RuntimeError,'HOLD_CONSUMER_PAYLOAD_MISMATCH'):self.context.run(self.root)
        self.assertEqual(self.files(),before)

    def test_unrelated_green_dashboard_cannot_override_current_authority(self):
        path=self.root/'latest/other/dashboard_state.json';path.parent.mkdir();path.write_text(json.dumps({'source_status':'clean','source_backed':True,'session_manifest':'latest/old/source_readiness_manifest.json'}))
        snapshot=self.output.build_snapshot(self.root,'irrelevant')
        self.assertEqual(snapshot['event']['session_key'],11407)
        self.assertNotIn('old',snapshot['source']['manifest_path'])

    def test_symlink_history_target_and_traversal_identity_hold(self):
        with tempfile.TemporaryDirectory() as temporary:
            external=Path(temporary)/'outside';external.write_bytes(b'original')
            target=self.root/'history/link';target.symlink_to(external)
            batch=self.output.OutputBatch(self.root)
            with self.assertRaisesRegex(RuntimeError,'HOLD_OUTPUT_PATH_CUSTODY'):batch.add(target,b'changed')
            self.assertEqual(external.read_bytes(),b'original')
        with self.assertRaisesRegex(RuntimeError,'HOLD_INVALID_OUTPUT_IDENTITY'):self.output.safe_component('../outside')


if __name__ == '__main__':
    unittest.main()
