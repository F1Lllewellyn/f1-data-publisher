"""Synthetic fixture expectations are NOT production authentication."""
import ast
import copy
import json
from pathlib import Path
import unittest

from scripts.forecast_bundles import forecast_integrity_contract_v1 as gate2a
from scripts.forecast_bundles import verify_forecast_integrity_receipts_v1 as v

ROOT = Path(__file__).resolve().parents[1]


class ReceiptAcceptance(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((ROOT/'tests/fixtures/dr002_receipts_v1.json').read_text())
        self.receipts = fixture['receipts']
        self.forecast = fixture['forecast']
        self.bindings = fixture['verified_receipt_bindings']
        self.objects = {k: s.encode() for k, s in fixture['objects_utf8'].items()}

    def receipt(self, rid):
        return next(r for r in self.receipts if r['receipt_id'] == rid)

    def bind(self, rid):
        """Only test arrangement: independently set expected fixture receipt digest."""
        self.bindings[rid] = dict(receipt_sha256=v.receipt_sha256(self.receipt(rid)),
                                 verification_ref='synthetic://'+rid)

    def put(self, data):
        data = data.encode() if isinstance(data, str) else data
        digest = v.sha256(data)
        self.objects[digest] = data
        return digest

    def check(self):
        return v.build_verified_execution_records(self.receipts, objects=self.objects,
            forecast=self.forecast, verified_receipt_bindings=self.bindings)

    def passes(self):
        result = self.check()
        self.assertEqual(result['status'], 'VERIFIED_BINDINGS', result)
        self.assertFalse(result['production_authenticated'])
        self.assertEqual(result['trust_scope'], 'EXTERNAL_BINDING_INTERFACE_ONLY')
        return result

    def fails(self, reason=None):
        result = self.check()
        self.assertIn(result['status'], ('MALFORMED', 'UNVERIFIABLE'), result)
        self.assertEqual(result['verified_execution_records'], {})
        if reason:
            self.assertIn(reason, result['reason_codes'])
        return result

    def change(self, rid, key, value, section='payload'):
        target = self.receipt(rid) if section is None else self.receipt(rid)[section]
        target[key] = value
        self.bind(rid)

    def rebind_manifest(self):
        sha = self.put(v.canonical_json_bytes({k: self.forecast[k] for k in v.MANIFEST_KEYS}))
        self.forecast['producer']['input_manifest_sha256'] = sha
        self.change('producer-1', 'input_manifest_sha256', sha)
        captures = [self.receipt(e['capture_evidence_ref']) for e in self.forecast['evidence']]
        self.change('producer-1', 'input_receipt_manifest_sha256', v.input_receipt_manifest_sha256(captures))

    def add_engine(self):
        p = self.forecast['producer']
        p.update(engine_implementation='Engine_2026-06-07_STABLE',engine_execution_id='synthetic-engine',
                 engine_code_sha256=self.put('SYNTHETIC engine bytes; never real engine code'),
                 engine_execution_proof_ref='synthetic://engine-1')
        producer = self.receipt('producer-1')
        producer['payload'].update(engine_implementation=p['engine_implementation'],engine_receipt_id='engine-1',engine_result_sha256=p['forecast_payload_sha256'])
        producer['parent_receipt_ids'].append('engine-1')
        self.bind('producer-1')
        engine = dict(schema_version=v.VERSION,receipt_id='engine-1',receipt_type='engine_execution',
            receipt_created_utc='2026-09-26T10:04:00Z',scope=copy.deepcopy(producer['scope']),
            parent_receipt_ids=['capture-1'],payload=dict(engine_implementation=p['engine_implementation'],
            engine_execution_id=p['engine_execution_id'],engine_code_sha256=p['engine_code_sha256'],
            repository_backed=True,git_commit='b'*40,producer_execution_id=p['execution_id'],
            input_manifest_sha256=p['input_manifest_sha256'],
            input_receipt_manifest_sha256=producer['payload']['input_receipt_manifest_sha256'],
            result_sha256=p['forecast_payload_sha256'],completed_utc='2026-09-26T10:04:00Z'))
        self.receipts.append(engine); self.bind('engine-1')

    def add_revision(self):
        capture = copy.deepcopy(self.receipt('capture-1'))
        capture.update(receipt_id='capture-revised',receipt_created_utc='2026-09-26T10:42:00Z')
        capture['scope']['session_id'] = self.forecast['session_id']
        capture['payload'].update(source_sha256=self.put('SYNTHETIC revised grid'),
            first_observed_utc='2026-09-26T10:40:00Z',ingested_utc='2026-09-26T10:41:00Z')
        self.receipts.append(capture); self.bind('capture-revised')
        rp = dict(revision_id='revision-1',source_id='grid',source_sha256=capture['payload']['source_sha256'],
                  first_observed_utc=capture['payload']['first_observed_utc'])
        scope = copy.deepcopy(self.receipt('producer-1')['scope'])
        rev = dict(schema_version=v.VERSION,receipt_id='revision-1',receipt_type='revision',
            receipt_created_utc='2026-09-26T10:43:00Z',scope=scope,
            parent_receipt_ids=['capture-revised'],payload=rp)
        self.receipts.append(rev); self.bind('revision-1')
        self.forecast['revisions'].append(dict(rp,**{k:scope[k] for k in v.SCOPE+('forecast_id','product_id')},
                                             capture_evidence_ref='capture-revised'))

    def test_valid_full_synthetic_chain(self):
        self.add_engine(); self.add_revision(); self.passes()

    def test_order_independent_and_repeatable(self):
        self.add_engine(); self.add_revision(); expected=self.passes()
        self.receipts.reverse(); self.assertEqual(expected,self.passes())
        self.assertEqual(expected,self.passes())

    def test_no_input_mutation(self):
        before=copy.deepcopy((self.receipts,self.objects,self.forecast,self.bindings))
        self.passes(); self.assertEqual(before,(self.receipts,self.objects,self.forecast,self.bindings))

    def test_receipt_content_tampering(self):
        self.receipt('capture-1')['payload']['source_uri']='synthetic://forged'
        self.fails('receipt_binding_hash_mismatch')

    def test_payload_bytes_tampering(self):
        self.objects[self.forecast['evidence'][0]['source_sha256']]=b'forged'
        self.fails('content_hash_mismatch_source_sha256')

    def test_missing_verified_binding(self):
        del self.bindings['capture-1']; self.fails('missing_or_malformed_verified_binding')

    def test_incorrect_verified_binding(self):
        self.bindings['capture-1']['receipt_sha256']='f'*64; self.fails('receipt_binding_hash_mismatch')

    def test_changed_trusted_binding(self):
        self.add_engine(); self.bindings['engine-1']['verification_ref']='synthetic://wrong-proof'
        self.fails('engine_mismatch_engine_execution_proof_ref')

    def test_changed_producer_or_engine_binding_digest(self):
        for rid in ('producer-1','engine-1'):
            with self.subTest(receipt=rid):
                self.setUp(); self.add_engine()
                self.bindings[rid]['receipt_sha256']='f'*64
                self.fails('receipt_binding_hash_mismatch')

    def test_trusted_flag_cannot_confer_trust(self):
        self.bindings={}; self.receipt('capture-1')['trusted']=True
        self.fails('malformed_envelope')
        del self.receipt('capture-1')['trusted']; self.fails('missing_or_malformed_verified_binding')

    def test_self_asserted_proof_rejected(self):
        self.receipt('producer-1')['payload']['verification_ref']='trusted://me'
        self.fails('malformed_payload')

    def test_duplicate_receipt(self):
        self.receipts.append(copy.deepcopy(self.receipts[0])); self.fails('duplicate_receipt_id')

    def test_missing_parent(self):
        self.change('producer-1','parent_receipt_ids',[],None); self.fails('producer_parent_mismatch')

    def test_unknown_parent(self):
        self.change('producer-1','parent_receipt_ids',['absent'],None); self.fails('unknown_parent')

    def test_duplicate_parent(self):
        self.change('producer-1','parent_receipt_ids',['capture-1','capture-1'],None)
        self.fails('duplicate_or_malformed_parent')

    def test_self_parent(self):
        self.change('producer-1','parent_receipt_ids',['producer-1'],None); self.fails('self_parent')

    def test_multi_receipt_cycle(self):
        self.change('capture-1','parent_receipt_ids',['lock-1'],None); self.fails('cyclic_receipt_chain')

    def test_scope_dimensions(self):
        for key in v.SCOPE+v.PRODUCT:
            with self.subTest(key=key):
                self.setUp(); self.change('producer-1',key,'other','scope')
                self.fails('scope_mismatch_'+key)

    def test_source_scope_dimensions(self):
        for key in v.SCOPE:
            with self.subTest(key=key):
                self.setUp(); self.change('capture-1',key,'other','scope'); self.fails('scope_mismatch_'+key)

    def test_valid_source_envelope(self):
        self.assertTrue(v.validate_receipt_envelope(self.receipt('capture-1')))
        self.assertTrue(v.verify_content_bindings(self.receipt('capture-1'),self.objects))

    def test_missing_source_hash(self):
        del self.receipt('capture-1')['payload']['source_sha256']; self.fails('malformed_payload')

    def test_missing_observation_not_inferred_from_event_or_publication(self):
        c=self.receipt('capture-1')['payload']; del c['first_observed_utc']
        c['publisher_time_utc']='2020-01-01T00:00:00Z'; self.fails('malformed_payload')

    def test_observed_after_ingested(self):
        self.change('capture-1','first_observed_utc','2026-09-26T09:57:00Z')
        self.fails('inconsistent_capture_times')

    def test_backdated_capture_fails_external_binding(self):
        self.receipt('capture-1')['payload']['first_observed_utc']='2020-01-01T00:00:00Z'
        self.fails('receipt_binding_hash_mismatch')

    def test_later_observation_rejected_at_cutoff(self):
        c=self.receipt('capture-1'); c['payload'].update(first_observed_utc='2026-09-26T10:01:00Z',ingested_utc='2026-09-26T10:02:00Z')
        c['receipt_created_utc']='2026-09-26T10:03:00Z'; self.bind('capture-1')
        for k in ('first_observed_utc','ingested_utc'): self.forecast['evidence'][0][k]=c['payload'][k]
        self.rebind_manifest(); self.fails('first_observed_after_cutoff')

    def test_late_ingestion_rejected_when_required(self):
        self.change('capture-1','ingested_utc','2026-09-26T10:01:00Z')
        self.change('capture-1','receipt_created_utc','2026-09-26T10:02:00Z',None)
        self.forecast['evidence'][0]['ingested_utc']='2026-09-26T10:01:00Z'
        self.rebind_manifest(); self.fails('ingested_after_cutoff')

    def test_producer_implementation_commit_code_execution_mismatches(self):
        for key,value in dict(implementation='other',git_commit='f'*40,execution_id='other',code_sha256=None).items():
            with self.subTest(key=key):
                self.setUp(); self.change('producer-1',key,self.put('other code') if value is None else value)
                self.fails('producer_mismatch_'+key)

    def test_gate2a_input_manifest_mismatch(self):
        sha=self.put('{}'); self.forecast['producer']['input_manifest_sha256']=sha
        self.change('producer-1','input_manifest_sha256',sha); self.fails('gate2a_manifest_mismatch')

    def test_receipt_parent_manifest_mismatch(self):
        self.change('producer-1','input_receipt_manifest_sha256','f'*64)
        self.fails('input_receipt_manifest_mismatch')

    def test_parent_content_bound_separately(self):
        self.change('capture-1','capture_ref','synthetic://changed-location')
        self.fails('input_receipt_manifest_mismatch')

    def test_forecast_output_mismatch(self):
        self.change('producer-1','forecast_payload_sha256',self.put('other output'))
        self.fails('producer_mismatch_forecast_payload_sha256')

    def test_lane_proves_no_engine(self):
        result=self.passes(); self.assertEqual(self.forecast['lane_name'],'stable_baseline')
        self.assertIsNone(result['verified_execution_records']['fixture-execution']['engine_implementation'])

    def test_stable_claim_without_engine(self):
        self.forecast['producer']['engine_implementation']='Engine_2026-06-07_STABLE'
        self.change('producer-1','engine_implementation','Engine_2026-06-07_STABLE')
        self.fails('missing_engine_receipt')

    def test_engine_identity_and_hash_mismatches(self):
        for key,value,reason in [
            ('engine_implementation','other','engine_implementation_mismatch'),
            ('engine_execution_id','other','engine_mismatch_engine_execution_id'),
            ('engine_code_sha256',None,'engine_mismatch_engine_code_sha256'),
            ('producer_execution_id','other','engine_invocation_mismatch')]:
            with self.subTest(key=key):
                self.setUp(); self.add_engine(); self.change('engine-1',key,self.put('other engine') if value is None else value)
                self.fails(reason)

    def test_engine_proof_ref_mismatch(self):
        self.add_engine(); self.forecast['producer']['engine_execution_proof_ref']='synthetic://wrong'
        self.fails('engine_mismatch_engine_execution_proof_ref')

    def test_engine_repository_commit_required(self):
        self.add_engine(); self.change('engine-1','git_commit',None); self.fails('engine_repository_commit_unproven')

    def test_engine_parent_manifest_mismatch(self):
        self.add_engine(); self.change('engine-1','input_receipt_manifest_sha256','f'*64)
        self.fails('engine_input_receipt_manifest_mismatch')

    def test_engine_result_mismatch(self):
        self.add_engine(); self.change('engine-1','result_sha256',self.put('other result'))
        self.fails('engine_result_mismatch')

    def test_legitimate_engine_chain(self):
        self.add_engine(); self.passes()

    def test_distinct_engine_result_bound_to_wrapper(self):
        self.add_engine(); sha=self.put('SYNTHETIC engine intermediate result')
        self.change('engine-1','result_sha256',sha)
        self.change('producer-1','engine_result_sha256',sha)
        self.passes()

    def test_no_engine_chain(self):
        self.passes()

    def test_orphan_engine_receipt(self):
        self.add_engine(); self.forecast['producer']['engine_implementation']=None
        self.change('producer-1','engine_implementation',None); self.fails('orphan_engine_claim_or_receipt')

    def test_wrapper_hash_cannot_prove_engine(self):
        self.add_engine(); sha=self.forecast['producer']['code_sha256']
        self.forecast['producer']['engine_code_sha256']=sha; self.change('engine-1','engine_code_sha256',sha)
        self.fails('wrapper_hash_is_not_engine_hash')

    def test_normalization_transform(self):
        self.passes()

    def test_normalization_input_mismatch(self):
        self.change('normalization-1','input_payload_sha256',self.put('other input')); self.fails('normalization_input_mismatch')

    def test_normalization_output_mismatch(self):
        self.change('normalization-1','output_payload_sha256',self.put('other output')); self.fails('lock_payload_mismatch')

    def test_normalization_wrong_parent(self):
        self.change('normalization-1','parent_receipt_ids',['capture-1'],None); self.fails('normalization_parent_mismatch')

    def test_normalization_no_transform(self):
        self.change('normalization-1','output_payload_sha256',self.forecast['producer']['forecast_payload_sha256'])
        self.fails('normalization_without_transformation')

    def test_direct_producer_lock(self):
        self.receipts=[r for r in self.receipts if r['receipt_id']!='normalization-1']
        lock=self.receipt('lock-1'); sha=self.forecast['producer']['forecast_payload_sha256']
        lock['parent_receipt_ids']=['producer-1']; lock['payload'].update(forecast_payload_sha256=sha,stored_payload_sha256=sha)
        self.bind('lock-1'); self.passes()

    def test_chained_normalizations(self):
        r=copy.deepcopy(self.receipt('normalization-1'));r['receipt_id']='normalization-2'
        r['parent_receipt_ids']=['normalization-1']; r['payload']['execution_id']='normalize-2'
        r['payload']['input_payload_sha256']=r['payload']['output_payload_sha256']
        sha=self.put('SYNTHETIC second transformation'); r['payload']['output_payload_sha256']=sha
        self.receipts.append(r); self.bind('normalization-2')
        self.change('lock-1','parent_receipt_ids',['normalization-2'],None)
        for key in ('forecast_payload_sha256','stored_payload_sha256'): self.change('lock-1',key,sha)
        self.passes()

    def test_lock_payload_and_storage_mismatches(self):
        for key in ('forecast_payload_sha256','stored_payload_sha256'):
            with self.subTest(key=key):
                self.setUp(); self.change('lock-1',key,self.put('wrong locked bytes')); self.fails('lock_payload_mismatch')

    def test_lock_forecast_product_mismatches(self):
        for key in ('forecast_id','product_id'):
            with self.subTest(key=key):
                self.setUp(); self.change('lock-1',key,'wrong','scope'); self.fails('scope_mismatch_'+key)

    def test_lock_missing_explicit_time(self):
        del self.receipt('lock-1')['payload']['lock_utc']; self.fails('malformed_payload')

    def test_history_timestamp_cannot_replace_lock(self):
        r=self.receipt('lock-1')['payload']; r['history_copy_utc']=r.pop('lock_utc')
        self.fails('malformed_payload')

    def test_explicit_boundary_passes(self):
        self.passes()

    def test_boundary_source_mismatch(self):
        self.change('boundary-1','source_id','other'); self.fails('boundary_evidence_mismatch')

    def test_boundary_scope_mismatch(self):
        self.change('boundary-capture','meeting_id','other','scope'); self.fails('scope_mismatch_meeting_id')

    def test_boundary_no_policy_default(self):
        del self.receipt('boundary-1')['payload']['boundary_policy_ref']; self.fails('malformed_payload')

    def test_boundary_not_invented(self):
        del self.forecast['outcome_availability_boundary_utc']; self.fails()

    def test_legitimate_revision_observation(self):
        self.add_revision(); self.passes()
        self.assertEqual(self.receipt('revision-1')['parent_receipt_ids'],['capture-revised'])

    def test_revision_wrong_forecast_product(self):
        for key in ('forecast_id','product_id'):
            with self.subTest(key=key):
                self.setUp(); self.add_revision(); self.change('revision-1',key,'wrong','scope')
                self.fails('scope_mismatch_'+key)

    def test_revision_wrong_source_hash_observation(self):
        for key,value in [('source_id','wrong'),('source_sha256',None),('first_observed_utc','2026-09-26T09:50:00Z')]:
            with self.subTest(key=key):
                self.setUp(); self.add_revision(); self.change('revision-1',key,self.put('wrong revision') if value is None else value)
                self.fails('revision_mismatch_'+key)

    def test_revision_observation_must_match_capture(self):
        self.add_revision(); time='2026-09-26T09:50:00Z'
        self.forecast['revisions'][0]['first_observed_utc']=time
        self.change('revision-1','first_observed_utc',time); self.fails('revision_capture_mismatch_first_observed_utc')

    def test_revision_backdating_external_binding(self):
        self.add_revision(); self.receipt('capture-revised')['payload']['first_observed_utc']='2020-01-01T00:00:00Z'
        self.fails('receipt_binding_hash_mismatch')

    def test_revision_unrelated_canonical_source(self):
        self.add_revision(); self.change('capture-revised','source_uri','synthetic://unrelated')
        self.fails('revision_unrelated_source')

    def test_gate2a_no_engine_projection(self):
        result=self.passes()
        self.assertEqual(gate2a.classify_forecast(self.forecast,verified_execution_records=result['verified_execution_records'])['state'],'VALID_LOCKED')

    def test_gate2a_engine_projection(self):
        self.add_engine(); result=self.passes()
        self.assertEqual(gate2a.classify_forecast(self.forecast,verified_execution_records=result['verified_execution_records'])['state'],'VALID_LOCKED')

    def test_changed_projection_binding_fails_gate2a(self):
        result=self.passes(); result['verified_execution_records']['fixture-execution']['code_sha256']='f'*64
        self.assertEqual(gate2a.classify_forecast(self.forecast,verified_execution_records=result['verified_execution_records'])['state'],'HOLD')

    def test_revision_classification_stays_with_gate2a(self):
        self.add_revision(); result=self.passes()
        self.assertNotIn('state',result)
        assessed=gate2a.classify_forecast(self.forecast,verified_execution_records=result['verified_execution_records'])
        self.assertEqual(assessed['state'],'VALID_LOCKED')
        self.assertEqual(assessed['revision_events'][0]['event_state'],'POST_CUTOFF_REVISION')

    def test_evaluation_gates_remain_nonblind(self):
        for gate in ('race_result','post_event'):
            f=copy.deepcopy(self.forecast);f['gate']=gate
            self.assertEqual(gate2a.classify_forecast(f)['state'],'OUTCOME_AWARE_EVALUATION_ONLY')

    def test_unrelated_receipt_rejected(self):
        r=copy.deepcopy(self.receipt('capture-1'));r['receipt_id']='orphan'
        self.receipts.append(r);self.bind('orphan');self.fails('unrelated_receipts')

    def test_malformed_time_rejected(self):
        self.change('capture-1','first_observed_utc','2026-09-26');self.fails('malformed_utc')

    def test_canonical_hash_order(self):
        r=self.receipt('capture-1'); self.assertEqual(v.receipt_sha256(r),v.receipt_sha256(dict(reversed(list(r.items())))))
        self.assertEqual(gate2a.input_manifest_sha256(self.forecast),self.forecast['producer']['input_manifest_sha256'])

    def test_committed_schema_matches_runtime_shapes(self):
        self.assertEqual(json.loads((ROOT/'schemas/forecast_integrity_receipt_v1.schema.json').read_text()),v.receipt_schema())
        self.assertEqual(set(v.PAYLOADS),{'source_capture','engine_execution','producer_execution','normalization','forecast_lock','outcome_boundary','revision'})

    def test_standard_library_no_io_clock_or_production_import(self):
        tree=ast.parse((ROOT/'scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py').read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):self.assertTrue(all(x.name in {'hashlib','json','re'} for x in n.names))
            if isinstance(n,ast.ImportFrom):self.assertEqual(n.module,'datetime')
            if isinstance(n,ast.Call):
                name=n.func.id if isinstance(n.func,ast.Name) else getattr(n.func,'attr','')
                self.assertNotIn(name,{'open','read_text','read_bytes','write_text','write_bytes','now','utcnow','time','urlopen'})


if __name__ == '__main__':
    unittest.main()
