"""Offline synthetic temporal cases plus the four pinned real Baku byte fixtures."""
import ast
import base64
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import zlib

spec = importlib.util.spec_from_file_location('replay_audit', Path(__file__).resolve().parents[1] / 'scripts/forecast_bundles/dr002_replay_leakage_evidence_v1.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

# Exact read-only historical bytes fetched at the work-order dependency baseline.
# They are audit evidence, not generated predictions or availability receipts.
REAL_CASE_COMPRESSED = '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'

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.content = b'{"synthetic":"weather"}'
        self.receipt = dict(schema_version='dr002-receipt-v1', receipt_id='capture:synthetic',
            receipt_type='source_capture', receipt_created_utc='2026-01-01T09:02:00Z',
            scope=dict(event_id='event', meeting_id='meeting', session_id='practice'), parent_receipt_ids=[],
            payload=dict(source_id='weather', source_uri='synthetic:weather', source_sha256=a.sha256(self.content),
                event_time_utc=None, publisher_time_utc=None, first_observed_utc='2026-01-01T09:00:00Z',
                ingested_utc='2026-01-01T09:01:00Z', capture_ref='synthetic:bytes', implementation='synthetic-capture'))
        e = {k: self.receipt['payload'][k] for k in a.PROJECTION_FIELDS}
        e.update(self.receipt['scope'], capture_evidence_ref=self.receipt['receipt_id'], ingestion_required_at_cutoff=True)
        self.record = dict(schema_version='dr002-integrity-v1', legacy=False, execution_mode='replay',
            forecast_id='synthetic-forecast', product_id='synthetic-product', product_contract_id='synthetic-contract',
            contract_approved=False, gate='post_qualifying', lane_name='stable_baseline',
            event_id='event', meeting_id='meeting', session_id='practice', allowed_session_ids=['practice'],
            evidence_cutoff_utc='2026-01-01T10:00:00Z', forecast_generation_utc='2026-01-01T10:01:00Z',
            forecast_deadline_utc='2026-01-01T10:02:00Z', forecast_lock_utc='2026-01-01T10:02:00Z',
            outcome_availability_boundary_utc='2026-01-01T11:00:00Z', mandatory_source_ids=['weather'],
            revision_policy='none', evidence=[e], revisions=[])
        self.kinds = {'weather': 'predictive'}
        self.refresh_binding()
    def refresh_binding(self):
        self.bindings = {self.receipt['receipt_id']: dict(receipt_sha256=a.receipt_sha256(self.receipt), verification_ref='SYNTHETIC-ONLY')}
    def synchronize(self):
        self.record['evidence'][0].update({k:self.receipt['payload'][k] for k in a.PROJECTION_FIELDS})
        self.refresh_binding()
    def run_audit(self):
        return a.evaluate_as_of(self.record, captures=[self.receipt], content_by_receipt_id={self.receipt['receipt_id']:self.content},
            evidence_kinds=self.kinds, verified_receipt_bindings=self.bindings)
    def codes(self):
        return {f['code'] for f in self.run_audit()['findings']}
    def real_files(self):
        return {k:base64.b64decode(v) for k,v in json.loads(zlib.decompress(base64.b64decode(REAL_CASE_COMPRESSED))).items()}
    def test_clean_synthetic_asof(self):self.assertEqual(self.run_audit()['evidence_as_of_state'],'AS_OF_CONTRACT_CLEAN')
    def test_late_observation(self):
        self.receipt['payload'].update(first_observed_utc='2026-01-01T10:01:00Z',ingested_utc='2026-01-01T10:01:00Z');self.receipt['receipt_created_utc']='2026-01-01T10:02:00Z';self.synchronize()
        self.assertEqual(self.run_audit()['evidence_as_of_state'],'INELIGIBLE');self.assertIn('first_observed_after_cutoff',self.codes())
    def test_late_ingestion_required(self):
        self.receipt['payload']['ingested_utc']='2026-01-01T10:01:00Z';self.receipt['receipt_created_utc']='2026-01-01T10:02:00Z';self.synchronize();self.assertIn('ingested_after_cutoff',self.codes())
    def test_late_ingestion_not_required(self):
        self.receipt['payload']['ingested_utc']='2026-01-01T10:01:00Z';self.receipt['receipt_created_utc']='2026-01-01T10:02:00Z';self.synchronize();self.record['evidence'][0]['ingestion_required_at_cutoff']=False;self.assertEqual(self.run_audit()['evidence_as_of_state'],'AS_OF_CONTRACT_CLEAN')
    def test_early_event_publisher_cannot_rescue(self):
        self.receipt['payload'].update(event_time_utc='2025-01-01T00:00:00Z',publisher_time_utc='2025-01-01T00:00:00Z',first_observed_utc='2026-01-01T10:01:00Z',ingested_utc='2026-01-01T10:01:00Z');self.receipt['receipt_created_utc']='2026-01-01T10:02:00Z';self.synchronize();self.assertIn('first_observed_after_cutoff',self.codes())
    def test_missing_observed(self):
        del self.receipt['payload']['first_observed_utc'];self.assertEqual(self.run_audit()['evidence_as_of_state'],'UNPROVEN')
    def test_missing_evidence_provenance(self):
        self.record['evidence'][0].pop('first_observed_utc');self.assertEqual(self.run_audit()['evidence_as_of_state'],'UNPROVEN')
    def test_missing_capture(self):
        r=a.evaluate_as_of(self.record,captures=[],content_by_receipt_id={},evidence_kinds=self.kinds);self.assertEqual(r['evidence_as_of_state'],'UNPROVEN')
    def test_outcome_input(self):self.kinds['weather']='outcome';self.assertIn('outcome_evidence_in_predictive_input',self.codes())
    def test_race_result_input(self):self.kinds['weather']='race_result';self.assertEqual(self.run_audit()['evidence_as_of_state'],'INELIGIBLE')
    def test_post_event_input(self):self.kinds['weather']='post_event';self.assertEqual(self.run_audit()['evidence_as_of_state'],'INELIGIBLE')
    def test_unknown_role_unproven(self):self.kinds={};self.assertEqual(self.run_audit()['evidence_as_of_state'],'UNPROVEN')
    def test_later_snapshot_cannot_backdate(self):
        self.record['evidence'][0].update(current_api_available=True,source_timestamp_utc='2025-01-01T00:00:00Z',git_commit_time='2025-01-01T00:00:00Z');self.bindings={};self.assertEqual(self.run_audit()['evidence_as_of_state'],'UNPROVEN')
    def test_exact_hash_late_observation(self):self.test_late_observation();self.assertEqual(a.sha256(self.content),self.receipt['payload']['source_sha256'])
    def test_stable_lane_is_not_engine_proof(self):self.assertEqual(self.run_audit()['engine_execution'],'NOT_PROVEN')
    def test_legacy_blind_flag_not_override(self):
        self.record.update(legacy=True,blind_validation_eligible=True);self.assertEqual(self.run_audit()['forecast_classification']['state'],'TEMPORAL_ELIGIBILITY_UNPROVEN')
    def test_real_baku_case(self):
        r=a.audit_legacy_baku(self.real_files());self.assertEqual(r['audit_result'],'COMPLETED');self.assertEqual(r['forecast_classification']['state'],'TEMPORAL_ELIGIBILITY_UNPROVEN');self.assertEqual(r['observed']['forecast_row_count'],30);self.assertIsNone(r['actual_leakage_proven']);self.assertFalse(r['gate2b7_ready'])
    def test_real_case_lock_does_not_prove_source_availability(self):
        r=a.audit_legacy_baku(self.real_files());self.assertTrue(r['observed']['legacy_blind_flag']);self.assertIn('source_first_observed_utc',r['missing']);self.assertEqual(r['temporal_eligibility'],'UNPROVEN')
    def test_real_case_tamper_hold(self):
        f=self.real_files();f['forecast_rows.csv']+=b'\n';self.assertEqual(a.audit_legacy_baku(f)['audit_result'],'HOLD')
    def test_real_case_missing_hold(self):
        f=self.real_files();f.pop('engine_lane_config.json');self.assertEqual(a.audit_legacy_baku(f)['audit_result'],'HOLD')
    def test_replay_clean_not_blind(self):
        r=self.run_audit();self.assertEqual(r['forecast_classification']['state'],'OUTCOME_AWARE_EVALUATION_ONLY');self.assertFalse(r['forecast_classification']['blind_validation_eligible']);self.assertFalse(r['production_blind_eligibility_certified'])
    def test_evaluation_gate_not_blind(self):
        for g in ('post_event','race_result'):
            self.record['gate']=g;self.assertEqual(self.run_audit()['forecast_classification']['state'],'OUTCOME_AWARE_EVALUATION_ONLY')
    def test_generation_at_boundary_reported(self):
        self.record['forecast_generation_utc']=self.record['outcome_availability_boundary_utc'];self.assertEqual(self.run_audit()['forecast_temporal_findings'][0]['reason'],'not_before_outcome')
    def test_lock_after_outcome_reported(self):
        self.record['forecast_lock_utc']='2026-01-01T12:00:00Z';self.assertEqual(self.run_audit()['forecast_temporal_findings'][1]['status'],'INELIGIBLE')
    def test_prospective_outcome_gate2a_precedence(self):
        self.record['execution_mode']='prospective';self.record['contract_approved']=True;self.record['outcome_boundary_evidence_ref']='synthetic';self.record['lock_receipt_ref']='synthetic';self.record['forecast_lock_utc']='2026-01-01T11:00:00Z';self.assertEqual(self.run_audit()['forecast_classification']['reason_codes'],['not_before_outcome'])
    def test_empty_evidence_unproven(self):
        self.record['evidence']=[];r=a.evaluate_as_of(self.record,captures=[],content_by_receipt_id={},evidence_kinds={});self.assertEqual(r['evidence_as_of_state'],'UNPROVEN')
    def test_external_binding_missing(self):self.bindings={};self.assertEqual(self.run_audit()['evidence_as_of_state'],'UNPROVEN')
    def test_external_binding_wrong(self):self.bindings[self.receipt['receipt_id']]['receipt_sha256']='0'*64;self.assertEqual(self.run_audit()['evidence_as_of_state'],'HOLD')
    def test_content_tamper(self):self.content+=b' ';self.assertEqual(self.run_audit()['evidence_as_of_state'],'HOLD')
    def test_projection_tamper(self):self.record['evidence'][0]['source_sha256']='0'*64;self.assertIn('receipt_evidence_projection_mismatch',self.codes())
    def test_wrong_scope(self):self.record['meeting_id']='other';self.assertIn('source_scope_mismatch',self.codes())
    def test_duplicate_capture_hold(self):
        r=a.evaluate_as_of(self.record,captures=[self.receipt,self.receipt],content_by_receipt_id={},evidence_kinds=self.kinds);self.assertEqual(r['evidence_as_of_state'],'HOLD')
    def test_no_mutation(self):
        before=copy.deepcopy((self.record,self.receipt,self.bindings));self.run_audit();self.assertEqual(before,(self.record,self.receipt,self.bindings))
    def test_deterministic(self):self.assertEqual(a.canonical_json_bytes(self.run_audit()),a.canonical_json_bytes(self.run_audit()))
    def test_no_trust_upgrade(self):
        r=self.run_audit();self.assertEqual(r['trust']['binding_status'],'UNBOUND');self.assertFalse(r['trust']['production_authenticated']);self.assertFalse(r['trust']['historical_availability_proven']);self.assertFalse(r['trust']['dr002_activated']);self.assertNotIn('verified_receipt_bindings',r)
    def test_no_io_network_clock_discovery(self):
        tree=ast.parse(Path(a.__file__).read_text());imports={x.name for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)) for x in n.names};attrs={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)};calls={n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertFalse(imports&{'requests','urllib','datetime','random','uuid','glob','os'});self.assertFalse(attrs&{'now','glob','rglob','walk','iterdir','listdir','scandir','read_bytes','write_bytes','write_text'});self.assertNotIn('open',calls)

if __name__=='__main__':unittest.main()
