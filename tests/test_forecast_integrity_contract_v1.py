"""Offline synthetic contract fixtures. No network or production execution."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "integrity", ROOT / "scripts/forecast_bundles/forecast_integrity_contract_v1.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
FIXTURE = json.loads((ROOT / "tests/fixtures/dr002_integrity_v1.json").read_text())


class IntegrityAcceptance(unittest.TestCase):
    def setUp(self):
        self.r = copy.deepcopy(FIXTURE["forecast"])
        self.receipts = copy.deepcopy(FIXTURE["verified_execution_records"])

    def assess(self, state, reason=None, rebind=True):
        # Independent fixture captures each changed input set. Hash-tampering
        # tests explicitly disable this; real callers need verified receipts.
        if rebind:
            self.r['producer']['input_manifest_sha256'] = M.input_manifest_sha256(self.r)
            self.receipts['fixture-execution']['input_manifest_sha256'] = self.r['producer']['input_manifest_sha256']
        before = copy.deepcopy((self.r, self.receipts))
        result = M.classify_forecast(self.r, verified_execution_records=self.receipts)
        self.assertEqual(result['state'], state)
        self.assertEqual(result['blind_validation_eligible'], state == 'VALID_LOCKED')
        if reason:
            self.assertIn(reason, result['reason_codes'])
        self.assertEqual((self.r, self.receipts), before)
        return result

    def revision(self, observed):
        return dict(revision_id='revision-1',forecast_id=self.r['forecast_id'],
                    product_id=self.r['product_id'], event_id=self.r['event_id'],
                    meeting_id=self.r['meeting_id'],session_id=self.r['session_id'],
                    source_id='grid',source_sha256='e'*64,first_observed_utc=observed,
                    capture_evidence_ref='fixture://verified-revision')

    def test_valid_pre_outcome(self):
        self.assess('VALID_LOCKED')

    def test_evaluation_gates_always_excluded(self):
        for gate in ('race_result','post_event'):
            with self.subTest(gate=gate):
                self.r['gate']=gate
                self.assess('OUTCOME_AWARE_EVALUATION_ONLY','evaluation_gate')

    def test_late_first_observation(self):
        self.r['evidence'][0]['first_observed_utc']='2026-09-26T10:01:00Z'
        self.assess('HOLD','first_observed_after_cutoff')

    def test_late_ingestion_required(self):
        self.r['evidence'][0]['ingested_utc']='2026-09-26T10:01:00Z'
        self.assess('HOLD','ingested_after_cutoff')

    def test_late_ingestion_permitted_by_contract(self):
        self.r['evidence'][0].update(ingested_utc='2026-09-26T10:01:00Z',ingestion_required_at_cutoff=False)
        self.assess('VALID_LOCKED')

    def test_all_scope_dimensions(self):
        for key in ('event_id','meeting_id','session_id'):
            with self.subTest(key=key):
                self.setUp()
                self.r['evidence'][0][key]='unrelated'
                self.assess('HOLD','source_scope_mismatch')

    def test_absent_allowlist_requires_target_session(self):
        self.r['allowed_session_ids']=None
        self.assess('HOLD','source_scope_mismatch')
        self.r['evidence'][0]['session_id']=self.r['session_id']
        self.assess('VALID_LOCKED')

    def test_empty_allowlist_rejected(self):
        self.r['allowed_session_ids']=[]
        self.assess('HOLD','ambiguous_allowed_sessions')

    def test_lock_cannot_replace_availability(self):
        del self.r['evidence'][0]['first_observed_utc']
        self.r['source_found']=True
        self.assess('HOLD','missing_or_malformed_contract')

    def test_missing_mandatory(self):
        self.r['evidence']=[]
        self.assess('HOLD','missing_mandatory_evidence')

    def test_optional_consumed_evidence_checked(self):
        e=copy.deepcopy(self.r['evidence'][0]);e.update(source_id='optional',meeting_id='other')
        self.r['evidence'].append(e)
        self.assess('HOLD','source_scope_mismatch')

    def test_late_lock(self):
        self.r['forecast_lock_utc']='2026-09-26T10:30:01Z'
        self.assess('MISSED_DEADLINE','lock_after_deadline')

    def test_deadline_inclusive(self):
        self.r['forecast_lock_utc']=self.r['forecast_deadline_utc']
        self.assess('VALID_LOCKED')

    def test_lock_at_outcome_excluded(self):
        self.r['forecast_lock_utc']=self.r['outcome_availability_boundary_utc']
        self.assess('OUTCOME_AWARE_EVALUATION_ONLY','not_before_outcome')

    def test_predeadline_revision_supersedes(self):
        self.r['revisions']=[self.revision('2026-09-26T10:20:00Z')]
        self.assess('SUPERSEDED','pre_deadline_revision_not_incorporated')

    def test_late_revision_preserves_original(self):
        self.r['revisions']=[self.revision('2026-09-26T10:30:01Z')]
        result=self.assess('VALID_LOCKED')
        self.assertEqual(result['revision_events'],[dict(revision_id='revision-1',event_state='POST_CUTOFF_REVISION')])

    def test_revision_at_deadline_unresolved(self):
        self.r['revisions']=[self.revision('2026-09-26T10:30:00Z')]
        self.assess('HOLD','revision_at_deadline_policy_unresolved')

    def test_replacement_late_never_restores_superseded(self):
        self.r['revisions']=[self.revision('2026-09-26T10:20:00Z')]
        self.assess('SUPERSEDED')
        self.r['evidence'][0].update(source_sha256='e'*64,first_observed_utc='2026-09-26T10:20:00Z',ingested_utc='2026-09-26T10:20:00Z')
        self.r.update(evidence_cutoff_utc='2026-09-26T10:20:00Z',forecast_generation_utc='2026-09-26T10:25:00Z',forecast_lock_utc='2026-09-26T10:31:00Z')
        self.assess('MISSED_DEADLINE')

    def test_revision_scope_rejected(self):
        rev=self.revision('2026-09-26T10:20:00Z');rev['product_id']='other'
        self.r['revisions']=[rev]
        self.assess('HOLD','ambiguous_revision_provenance')

    def test_stable_claim_requires_matching_execution_proof(self):
        self.r['producer']['engine_implementation']='Engine_2026-06-07_STABLE'
        self.assess('HOLD','execution_lineage_unproven')
        self.receipts['fixture-execution']['engine_implementation']='Engine_2026-06-07_STABLE'
        self.assess('HOLD','engine_execution_provenance_missing')

    def test_no_receipt_no_lineage(self):
        result=M.classify_forecast(self.r)
        self.assertEqual(result['state'],'HOLD')
        self.assertIn('execution_lineage_unproven',result['reason_codes'])

    def engine_claim(self):
        claim=dict(engine_implementation='Engine_2026-06-07_STABLE',
                   engine_execution_id='synthetic-engine-execution',
                   engine_code_sha256='e'*64,
                   engine_execution_proof_ref='fixture://verified-engine-execution')
        self.r['producer'].update(claim)
        self.receipts['fixture-execution'].update(claim)

    def test_matching_synthetic_engine_execution(self):
        self.engine_claim()
        self.assess('VALID_LOCKED')

    def test_engine_hash_proof_and_identity_mismatches(self):
        for key, value in [('engine_code_sha256','f'*64),
                           ('engine_execution_proof_ref','fixture://other'),
                           ('engine_execution_id','other-execution')]:
            with self.subTest(key=key):
                self.setUp();self.engine_claim()
                self.receipts['fixture-execution'][key]=value
                self.assess('HOLD','engine_execution_provenance_mismatch')

    def test_missing_engine_proof_fields(self):
        for key in ('engine_execution_id','engine_code_sha256','engine_execution_proof_ref'):
            with self.subTest(key=key):
                self.setUp();self.engine_claim()
                del self.r['producer'][key]
                self.assess('HOLD','engine_execution_provenance_missing')

    def test_missing_engine_receipt_fields(self):
        for key in ('engine_execution_id','engine_code_sha256','engine_execution_proof_ref'):
            with self.subTest(key=key):
                self.setUp();self.engine_claim()
                del self.receipts['fixture-execution'][key]
                self.assess('HOLD','engine_execution_provenance_mismatch')

    def test_wrapper_hash_cannot_stand_in_for_engine(self):
        self.engine_claim()
        for p in (self.r['producer'],self.receipts['fixture-execution']):
            p['engine_code_sha256']=p['code_sha256']
        self.assess('HOLD','wrapper_hash_is_not_engine_hash')

    def test_same_executable_identity_can_share_hash(self):
        self.engine_claim()
        for p in (self.r['producer'],self.receipts['fixture-execution']):
            p['implementation']=p['engine_implementation']
            p['engine_code_sha256']=p['code_sha256']
        self.assess('VALID_LOCKED')

    def test_null_engine_claim_valid(self):
        self.assertIsNone(self.r['producer']['engine_implementation'])
        self.assess('VALID_LOCKED')

    def test_orphan_engine_provenance_rejected(self):
        self.r['producer']['engine_execution_id']='orphan'
        self.assess('HOLD','engine_provenance_without_engine_claim')

    def test_hash_binding(self):
        self.r['evidence'][0]['source_sha256']='f'*64
        self.assess('HOLD','input_manifest_hash_mismatch',rebind=False)

    def test_legacy_not_upgraded(self):
        for value in (True,None):
            self.r['legacy']=value
            self.assess('TEMPORAL_ELIGIBILITY_UNPROVEN')
        self.assertEqual(M.classify_forecast({'source_found':True,'blind_validation_eligible':True})['state'],'TEMPORAL_ELIGIBILITY_UNPROVEN')

    def test_no_new_gates(self):
        self.r['gate']='final_pre_race'
        self.assess('HOLD','unsupported_gate_or_mode')

    def test_nonprospective(self):
        for mode in ('replay','manual_validation'):
            self.r['execution_mode']=mode
            self.assess('OUTCOME_AWARE_EVALUATION_ONLY')

    def test_malformed_and_unknown_fields_fail_closed(self):
        for key in ('forecast_lock_utc','forecast_deadline_utc','outcome_availability_boundary_utc'):
            with self.subTest(key=key):
                self.setUp();self.r[key]='2026-09-26T10:00:00'
                self.assess('HOLD','missing_or_malformed_contract')

    def test_duplicate_evidence_rejected(self):
        self.r['evidence'].append(copy.deepcopy(self.r['evidence'][0]))
        self.assess('HOLD','ambiguous_source_identity')

    def test_unapproved_contract(self):
        self.r['contract_approved']=False
        self.assess('HOLD','unapproved_contract')

    def test_malformed_gate(self):
        self.r['gate']=[]
        self.assess('HOLD','missing_or_malformed_contract')

    def test_unrelated_revision_source(self):
        rev=self.revision('2026-09-26T10:20:00Z');rev['source_id']='unconsumed'
        self.r['revisions']=[rev]
        self.assess('HOLD','ambiguous_revision_provenance')

    def test_future_ingestion_even_when_cutoff_exemption(self):
        self.r['evidence'][0].update(ingested_utc='2026-09-26T10:06:00Z',ingestion_required_at_cutoff=False)
        self.assess('HOLD','inconsistent_ingestion_time')

    def test_optional_descriptive_times_not_availability(self):
        self.r['evidence'][0].update(event_time_utc='2026-09-26T12:00:00Z',publisher_time_utc=None)
        self.assess('VALID_LOCKED')

    def test_fixture_schema_and_state_catalog(self):
        s=json.loads((ROOT/'schemas/forecast_integrity_contract_v1.schema.json').read_text())
        self.assertEqual(set(s['required']),set(self.r))
        self.assertEqual(set(s['$defs']['forecast_classification_state']['enum']),{x.value for x in M.ForecastState})
        self.assertEqual(set(s['$defs']['revision_event_state']['enum']),{x.value for x in M.RevisionEventState})
        self.assertNotIn('POST_CUTOFF_REVISION',{x.value for x in M.ForecastState})
        self.assertEqual(s['$defs']['classification']['properties']['state'],
                         {'$ref':'#/$defs/forecast_classification_state'})
        events=s['$defs']['classification']['properties']['revision_events']['items']
        self.assertNotIn('state',events['properties'])
        self.assertEqual(events['properties']['event_state'],{'$ref':'#/$defs/revision_event_state'})


if __name__=='__main__':
    unittest.main()
