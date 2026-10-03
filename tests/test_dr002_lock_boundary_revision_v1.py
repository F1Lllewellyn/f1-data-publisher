import ast
import copy
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('proof',Path(__file__).resolve().parents[1]/'scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from verify_forecast_integrity_receipts_v1 import input_receipt_manifest_sha256

def stamp(minute):return '2026-10-03T12:'+str(minute).zfill(2)+':00Z'
class ProofTests(unittest.TestCase):
    def setUp(self):
        self.objects={};self.source=self.capture('input','weather',b'weather',1)
        self.outcome=self.capture('outcome','result',b'result',50)
        p=self.source['payload']
        e={k:p[k] for k in ('source_id','source_uri','source_sha256','event_time_utc','publisher_time_utc','first_observed_utc','ingested_utc')}
        e.update(self.source['scope'],capture_evidence_ref='input',ingestion_required_at_cutoff=True)
        self.f=dict(schema_version='dr002-integrity-v1',legacy=False,execution_mode='prospective',contract_approved=True,
            forecast_id='forecast',product_id='product',product_contract_id='synthetic-contract',gate='post_qualifying',lane_name='experimental',
            event_id='event',meeting_id='meeting',session_id='session',allowed_session_ids=['session'],evidence_cutoff_utc=stamp(5),
            forecast_deadline_utc=stamp(30),forecast_generation_utc=stamp(10),mandatory_source_ids=['weather'],revision_policy='supersede_before_deadline',evidence=[e])
        self.output=b'{ "shadow": true }\n';self.code=b'synthetic code'
        self.producer=dict(schema_version=m.VERSION,receipt_id='producer',receipt_type='producer_execution',receipt_created_utc=stamp(11),scope=m.scope(self.f),parent_receipt_ids=['input'],payload=dict(implementation='synthetic',git_commit='a'*40,code_sha256=m.sha256(self.code),execution_id='execution',forecast_generation_utc=stamp(10),input_manifest_sha256=m.input_manifest_sha256(self.f),input_receipt_manifest_sha256=input_receipt_manifest_sha256([self.source]),forecast_payload_sha256=m.sha256(self.output),engine_implementation=None,engine_receipt_id=None,engine_result_sha256=None))
        self.f['producer']={k:self.producer['payload'][k] for k in ('implementation','git_commit','code_sha256','execution_id','input_manifest_sha256','forecast_payload_sha256','engine_implementation')}
        self.opts=dict(lock_utc=stamp(20),lock_receipt_created_utc=stamp(21),storage_ref='synthetic:immutable/payload',outcome_session_id='session',boundary_policy_ref='synthetic:policy',boundary_receipt_created_utc=stamp(51),revision_receipt_created_utc=stamp(45))
    def capture(self,rid,source,data,minute):
        self.objects[m.sha256(data)]=data
        return dict(schema_version=m.VERSION,receipt_id=rid,receipt_type='source_capture',receipt_created_utc=stamp(minute+1),scope=dict(event_id='event',meeting_id='meeting',session_id='session'),parent_receipt_ids=[],payload=dict(source_id=source,source_uri='https://example.test/'+source,source_sha256=m.sha256(data),event_time_utc=stamp(0),publisher_time_utc=stamp(0),first_observed_utc=stamp(minute),ingested_utc=stamp(minute),capture_ref='synthetic:'+rid,implementation='synthetic'))
    def package(self,**kw):
        opts=dict(self.opts);opts.update(kw)
        return m.build_proof_package(self.f,self.producer,self.output,self.outcome,**opts)
    def verify(self,package,revised=(),missing=False):
        receipts=[self.source,self.producer,self.outcome]+list(revised)+package['receipts']
        objects=dict(self.objects)
        for data in (self.code,self.output,m.canonical_json_bytes({k:package['forecast'][k] for k in m.MANIFEST_KEYS})):objects[m.sha256(data)]=data
        bindings={r['receipt_id']:dict(receipt_sha256=m.receipt_sha256(r),verification_ref='synthetic-only:'+r['receipt_id']) for r in receipts}
        if missing:bindings.pop('producer')
        return m.verify_and_classify(package,receipts,objects=objects,verified_receipt_bindings=bindings)
    def classify(self,package):
        p=package['forecast']['producer'];records={p['execution_id']:{**p,'verification_ref':'synthetic-only'}}
        return m.classify_forecast(package['forecast'],verified_execution_records=records)
    def reject(self,**kw):
        with self.assertRaises((ValueError,KeyError,TypeError)):self.package(**kw)
    def revision(self,minute=25):return self.capture('revised','weather',b'revised',minute)
    def test_valid_lock(self):self.assertEqual(self.package()['receipts'][0]['receipt_type'],'forecast_lock')
    def test_exact_bytes(self):self.assertEqual(self.package()['receipts'][0]['payload']['stored_payload_sha256'],m.sha256(self.output))
    def test_changed_bytes(self):self.output=b'changed';self.reject()
    def test_wrong_parent(self):
        p=self.package();p['receipts'][0]['parent_receipt_ids']=['wrong']
        with self.assertRaises(ValueError):m.complete_forecast_record(self.f,self.producer,*p['receipts'],[])
    def test_producer_scope(self):self.producer['scope']['forecast_id']='wrong';self.reject()
    def test_manifest_mismatch(self):self.f['forecast_deadline_utc']=stamp(29);self.reject()
    def test_lock_before_generation(self):self.reject(lock_utc=stamp(9))
    def test_created_before_lock(self):self.reject(lock_receipt_created_utc=stamp(19))
    def test_deterministic_lock_id(self):self.assertEqual(self.package()['receipts'][0]['receipt_id'],self.package()['receipts'][0]['receipt_id'])
    def test_lock_time_distinct(self):p=self.package()['receipts'][0];self.assertNotEqual(p['payload']['lock_utc'],p['receipt_created_utc'])
    def test_separate_outcome(self):self.assertEqual(self.package()['receipts'][1]['parent_receipt_ids'],['outcome'])
    def test_observation_boundary(self):self.assertEqual(self.package()['forecast']['outcome_availability_boundary_utc'],stamp(50))
    def test_publisher_not_boundary(self):self.outcome['payload']['publisher_time_utc']=stamp(2);self.assertEqual(self.package()['forecast']['outcome_availability_boundary_utc'],stamp(50))
    def test_event_not_boundary(self):self.outcome['payload']['event_time_utc']=stamp(2);self.assertEqual(self.package()['forecast']['outcome_availability_boundary_utc'],stamp(50))
    def test_wrong_outcome_event(self):self.outcome['scope']['event_id']='wrong';self.reject()
    def test_wrong_outcome_meeting(self):self.outcome['scope']['meeting_id']='wrong';self.reject()
    def test_wrong_outcome_session(self):self.outcome['scope']['session_id']='wrong';self.reject()
    def test_input_not_outcome(self):self.outcome=self.source;self.reject()
    def test_same_source_not_outcome(self):self.outcome['payload']['source_id']='weather';self.reject()
    def test_missing_boundary_policy(self):self.reject(boundary_policy_ref='')
    def test_revision_receipt(self):
        c=self.revision();p=self.package(revision_captures=[c]);self.assertEqual(p['receipts'][2]['parent_receipt_ids'],['revised']);self.assertEqual(p['forecast']['revisions'][0]['capture_evidence_ref'],'revised')
    def test_unrelated_revision(self):c=self.revision();c['payload']['source_id']='other';self.reject(revision_captures=[c])
    def test_revision_uri(self):c=self.revision();c['payload']['source_uri']='other';self.reject(revision_captures=[c])
    def test_identical_not_revision(self):c=self.revision();c['payload']['source_sha256']=self.source['payload']['source_sha256'];self.reject(revision_captures=[c])
    def test_deterministic_revision(self):
        c=self.revision();self.assertEqual(self.package(revision_captures=[c]),self.package(revision_captures=[c]))
    def test_duplicate_revision(self):c=self.revision();self.reject(revision_captures=[c,c])
    def test_no_revision_valid(self):self.assertEqual(self.classify(self.package())['state'],'VALID_LOCKED')
    def test_pre_deadline_superseded(self):self.assertEqual(self.classify(self.package(revision_captures=[self.revision()]))['state'],'SUPERSEDED')
    def test_post_deadline_revision(self):
        r=self.classify(self.package(revision_captures=[self.revision(35)]));self.assertEqual(r['state'],'VALID_LOCKED');self.assertEqual(r['revision_events'][0]['event_state'],'POST_CUTOFF_REVISION')
    def test_at_deadline_hold(self):
        r=self.classify(self.package(revision_captures=[self.revision(30)]));self.assertEqual(r['state'],'HOLD');self.assertIn('revision_at_deadline_policy_unresolved',r['reason_codes'])
    def test_incorporated_after_cutoff(self):
        p=self.package(revision_captures=[self.revision()]);f=p['forecast'];f['evidence'][0]['source_sha256']=f['revisions'][0]['source_sha256'];f['producer']['input_manifest_sha256']=m.input_manifest_sha256(f)
        self.assertEqual(self.classify(p)['reason_codes'],['revision_incorporated_after_cutoff'])
    def test_missed_deadline(self):self.assertEqual(self.classify(self.package(lock_utc=stamp(31),lock_receipt_created_utc=stamp(32)))['state'],'MISSED_DEADLINE')
    def test_post_event(self):
        f=copy.deepcopy(self.f);f['gate']='post_event';self.assertEqual(m.classify_forecast(f)['state'],'OUTCOME_AWARE_EVALUATION_ONLY')
    def test_full_graph(self):
        p=self.package();r=self.verify(p);self.assertEqual(r['verification']['status'],'VERIFIED_BINDINGS',r);self.assertEqual(r['classification']['state'],'VALID_LOCKED')
    def test_full_revision_graph(self):
        c=self.revision();r=self.verify(self.package(revision_captures=[c]),[c]);self.assertEqual(r['verification']['status'],'VERIFIED_BINDINGS',r);self.assertEqual(r['classification']['state'],'SUPERSEDED')
    def test_missing_binding(self):r=self.verify(self.package(),missing=True);self.assertIsNone(r['classification']);self.assertEqual(r['verification']['status'],'UNVERIFIABLE')
    def test_no_binding_emitted(self):self.assertNotIn(b'verified_receipt_bindings',m.canonical_json_bytes(self.package()))
    def test_no_normalization(self):self.assertNotIn('normalization',[r['receipt_type'] for r in self.package()['receipts']])
    def test_no_engine(self):self.assertNotIn('engine_execution',[r['receipt_type'] for r in self.package()['receipts']])
    def test_no_mutation(self):f=copy.deepcopy(self.f);self.package();self.assertEqual(f,self.f)
    def test_no_clock_random_network_discovery_writes(self):
        t=ast.parse(Path(m.__file__).read_text());names={a.name for n in ast.walk(t) if isinstance(n,(ast.Import,ast.ImportFrom)) for a in n.names};attrs={n.attr for n in ast.walk(t) if isinstance(n,ast.Attribute)}
        self.assertFalse(names&{'random','uuid','urllib','requests','glob'});self.assertFalse(attrs&{'now','utcnow','glob','rglob','iterdir','walk','listdir','scandir','write_bytes','write_text','open'})
    def test_trust(self):self.assertEqual(self.package()['trust'],m.TRUST);self.assertIs(self.package()['trust']['production_authenticated'],False)
    def test_completed_manifest_unchanged(self):p=self.package();self.assertEqual(m.input_manifest_sha256(p['forecast']),self.producer['payload']['input_manifest_sha256'])
    def test_producer_identity(self):self.f['producer']['execution_id']='wrong';self.reject()
    def test_tampered_boundary_cannot_pass(self):
        p=self.package();p['receipts'][1]['payload']['outcome_availability_boundary_utc']=stamp(49)
        p['forecast']['outcome_availability_boundary_utc']=stamp(49)
        r=self.verify(p);self.assertEqual(r['verification']['status'],'UNVERIFIABLE');self.assertIsNone(r['classification'])
    def test_storage_required(self):self.reject(storage_ref='')
    def test_revision_scope(self):c=self.revision();c['scope']['session_id']='wrong';self.reject(revision_captures=[c])
if __name__=='__main__':unittest.main()
