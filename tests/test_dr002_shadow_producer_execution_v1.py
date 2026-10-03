import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('shadow',Path(__file__).resolve().parents[1]/'scripts/forecast_bundles/dr002_shadow_producer_execution_v1.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.runtime=self.root/'_runtime/shadow'
        self.raw=b'[ {"session_key":11371,"meeting_key":1295,"date":"2026-09-18T12:00:00Z","air_temperature":25} ]\n'
        self.r=dict(schema_version=s.VERSION,receipt_id='synthetic-source',receipt_type='source_capture',receipt_created_utc='2026-10-03T15:36:44Z',scope=dict(s.SCOPE),parent_receipt_ids=[],payload=dict(source_id=s.SOURCE,source_uri=s.URI,source_sha256=s.sha256(self.raw),event_time_utc=None,publisher_time_utc=None,first_observed_utc='2026-10-03T15:36:42Z',ingested_utc='2026-10-03T15:36:43Z',capture_ref='synthetic/raw',implementation='synthetic'))
        self.pins=dict(receipt_id=self.r['receipt_id'],source_sha256=s.sha256(self.raw),receipt_sha256=s.receipt_sha256(self.r))
        self.m=dict(**s.SCOPE,**s.TRUST,validation_status='CAPTURED_UNBOUND',source_sha256=self.pins['source_sha256'],receipt_sha256=self.pins['receipt_sha256'],request_started_utc='2026-10-03T15:36:41Z',response_completed_utc='2026-10-03T15:36:42Z',first_observed_utc='2026-10-03T15:36:42Z',ingested_utc='2026-10-03T15:36:43Z',receipt_created_utc='2026-10-03T15:36:44Z',readback_verified=True,readback_sha256=s.sha256(self.raw),row_count=1,byte_count=len(self.raw))
        self.rp=self.root/'receipt';self.cp=self.root/'capture';self.bp=self.root/'body';self.codes={p:self.root/('code'+str(i)) for i,p in enumerate(s.CODE_PATHS)}
        for p in self.codes.values():p.write_bytes(b'synthetic code')
        self.save()
    def save(self):self.rp.write_bytes(s.canonical_json_bytes(self.r));self.cp.write_bytes(s.canonical_json_bytes(self.m));self.bp.write_bytes(self.raw)
    def go(self,**kw):
        ticks=iter(['2026-10-03T16:00:00Z','2026-10-03T16:00:01Z']);options=dict(git_commit='a'*40,run_id='test',runtime_root=self.runtime,clock_fn=lambda:next(ticks),code_paths=self.codes,_capture_pins=self.pins);options.update(kw)
        return s.execute(str(self.rp),str(self.bp),str(self.cp),**options)
    def get(self,p):return s.strict_json((self.runtime/'test'/p).read_bytes())
    def reject(self,**kw):
        with self.assertRaises(Exception):self.go(**kw)
        self.assertFalse((self.runtime/'test/receipts/producer_execution_receipt.json').exists())
    def test_deterministic(self):
        self.go();a=(self.runtime/'test/output/shadow_producer_output.json').read_bytes();other=self.root/'other/_runtime/shadow';self.go(runtime_root=other);self.assertEqual(a,(other/'test/output/shadow_producer_output.json').read_bytes())
    def test_not_prediction(self):self.go();self.assertEqual(self.get('output/shadow_producer_output.json')['status'],'SHADOW_EXECUTION_ONLY_NOT_A_PREDICTION')
    def test_outcome_aware(self):self.go();o=self.get('output/shadow_producer_output.json');self.assertEqual(o['gate'],'post_event');self.assertEqual(o['integrity_classification'],'OUTCOME_AWARE_EVALUATION_ONLY')
    def test_row_count(self):self.go();self.assertEqual(self.get('output/shadow_producer_output.json')['source_row_count'],1)
    def test_copied_count_rejected(self):self.m['row_count']=85;self.save();self.reject()
    def test_raw_tamper(self):self.bp.write_bytes(b'[]');self.reject()
    def test_receipt_tamper(self):self.r['payload']['implementation']='forged';self.save();self.reject()
    def test_wrong_event(self):self.r['scope']['event_id']='other';self.save();self.reject()
    def test_wrong_meeting(self):self.r['scope']['meeting_id']='other';self.save();self.reject()
    def test_wrong_session(self):self.r['scope']['session_id']='other';self.save();self.reject()
    def test_wrong_receipt_id(self):self.r['receipt_id']='other';self.save();self.reject()
    def test_wrong_source_hash(self):self.r['payload']['source_sha256']='0'*64;self.save();self.reject()
    def test_frozen_failure(self):
        with patch.object(s,'validate_frozen_evidence_manifest',return_value=False):self.reject()
    def test_frozen_hash_mismatch(self):
        original=s.build_frozen_evidence_manifest
        def bad(*a,**k):r=original(*a,**k);r['frozen_evidence_manifest_sha256']='0'*64;return r
        with patch.object(s,'build_frozen_evidence_manifest',side_effect=bad):self.reject()
    def test_receipt_set_hash(self):
        from verify_forecast_integrity_receipts_v1 import input_receipt_manifest_sha256
        self.assertEqual(self.go()['producer']['input_receipt_manifest_sha256'],input_receipt_manifest_sha256([self.r]))
    def test_gate2a_input_hash(self):
        r=self.go();m=self.get('contract/shadow_input_manifest.json');self.assertEqual(r['producer']['input_manifest_sha256'],s.input_manifest_sha256(m));self.assertEqual(m['forecast_deadline_utc'],r['forecast_generation_utc']);self.assertFalse(m['evidence'][0]['ingestion_required_at_cutoff'])
    def test_readback_failure(self):
        def reader(p):return b'wrong' if str(p).endswith('shadow_producer_output.json') else Path(p).read_bytes()
        self.reject(reader=reader)
    def test_exact_payload_hash(self):
        r=self.go();self.assertEqual(r['producer']['forecast_payload_sha256'],s.sha256((self.runtime/'test/output/shadow_producer_output.json').read_bytes()))
    def test_code_files_order(self):self.go();self.assertEqual([r['path'] for r in self.get('implementation/code_manifest.json')],list(s.CODE_PATHS))
    def test_dependency_change(self):
        read=lambda p:Path(p).read_bytes();a=s.sha256(s.canonical_json_bytes(s.code_manifest(self.codes,read)));self.codes[s.CODE_PATHS[0]].write_bytes(b'change');self.assertNotEqual(a,s.sha256(s.canonical_json_bytes(s.code_manifest(self.codes,read))))
    def test_receipt_parent_structure(self):self.go();r=self.get('receipts/producer_execution_receipt.json');self.assertTrue(s.validate_receipt_envelope(r));self.assertEqual(r['parent_receipt_ids'],[self.r['receipt_id']])
    def test_null_engine(self):
        self.go();r=self.get('receipts/producer_execution_receipt.json');self.assertEqual(r['receipt_type'],'producer_execution')
        for k in ('engine_implementation','engine_receipt_id','engine_result_sha256'):self.assertIsNone(r['payload'][k])
    def test_execution_id(self):p=self.go()['producer'];self.assertEqual(s.execution_identity(p),p['execution_id'])
    def test_generation_changes_id(self):p=self.go()['producer'];a=s.execution_identity(p);p['forecast_generation_utc']='2026-10-03T16:01:00Z';self.assertNotEqual(a,s.execution_identity(p))
    def test_no_random_discovery_network(self):
        t=ast.parse(Path(s.__file__).read_text());imports={a.name for n in ast.walk(t) if isinstance(n,(ast.Import,ast.ImportFrom)) for a in n.names};attrs={n.attr for n in ast.walk(t) if isinstance(n,ast.Attribute)};self.assertFalse(imports&{'uuid','random','glob','urllib','requests'});self.assertFalse(attrs&{'glob','rglob','iterdir','walk','listdir','scandir'})
    def test_explicit_reads(self):
        seen=[]
        def read(p):seen.append(str(p));return Path(p).read_bytes()
        self.go(reader=read);self.assertEqual(seen[:3],[str(self.rp),str(self.bp),str(self.cp)])
    def test_no_prediction_fields(self):self.go();self.assertFalse(set(self.get('output/shadow_producer_output.json'))&{'rank','probability','drivers','driver_score','strategy'})
    def fail_writer(self,name):
        def write(p,d):
            if str(p).endswith(name):raise OSError('synthetic')
            s.write(p,d)
        return write
    def test_manifest_failure(self):self.reject(writer=self.fail_writer('execution_manifest.json'))
    def test_report_failure(self):self.reject(writer=self.fail_writer('shadow_report.md'))
    def test_publish_failure(self):
        def fail(a,b):raise OSError('rename')
        self.reject(publisher=fail)
    def test_runtime_only(self):self.go();self.assertFalse(any((self.root/p).exists() for p in ('latest','history','ledgers','workbooks')))
    def test_unbound(self):
        r=self.go()
        for k,v in s.TRUST.items():self.assertEqual(r[k],v)
    def test_default_pins_reject_synthetic(self):self.reject(_capture_pins=s.PINS)
    def test_capture_trust(self):self.m['production_authenticated']=True;self.save();self.reject()
    def test_git_commit(self):self.reject(git_commit='bad')
    def test_parent(self):self.r['parent_receipt_ids']=['other'];self.save();self.reject()
    def test_structural_failure(self):
        orig=s.validate_receipt_envelope
        with patch.object(s,'validate_receipt_envelope',side_effect=lambda r:False if r['receipt_type']=='producer_execution' else orig(r)):self.reject()
    def test_bad_generation(self):self.reject(clock_fn=lambda:'2026-10-02T00:00:00Z')
    def test_candidate_readback(self):
        def reader(p):return b'bad' if str(p).endswith('receipt_candidate.diagnostic.json') else Path(p).read_bytes()
        self.reject(reader=reader)
    def test_input_hash_mismatch(self):
        with patch.object(s,'input_manifest_sha256',return_value='0'*64):self.reject()
    def test_receipt_set_mismatch(self):
        original=s.build_frozen_evidence_manifest
        def bad(*a,**k):
            r=original(*a,**k);r['manifest']['input_receipt_manifest_sha256']='0'*64
            r['frozen_evidence_manifest_sha256']=s.sha256(s.canonical_json_bytes(r['manifest']));return r
        with patch.object(s,'build_frozen_evidence_manifest',side_effect=bad):self.reject()
    def test_missing_code(self):self.codes[s.CODE_PATHS[0]].unlink();self.reject()
if __name__=='__main__':unittest.main()
