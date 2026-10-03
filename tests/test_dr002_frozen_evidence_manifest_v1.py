import ast
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('frozen',Path(__file__).resolve().parents[1]/'scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

class FrozenTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.receipts=[];self.pairs=[]
        self.add_capture('weather','11371',b'[ {"value": 1} ]\n')
        self.request=dict(event_id='baku',meeting_id='1295',allowed_session_ids=['11371'],captures=self.pairs)
    def add_capture(self,source,session,body):
        i=len(self.receipts)
        r=dict(schema_version='dr002-receipt-v1',receipt_id='capture-'+str(i),receipt_type='source_capture',
            receipt_created_utc='2026-10-03T15:36:44Z',scope=dict(event_id='baku',meeting_id='1295',session_id=session),
            parent_receipt_ids=[],payload=dict(source_id=source,source_uri='https://example.test/'+source,
            source_sha256=f.sha256(body),event_time_utc=None,publisher_time_utc=None,
            first_observed_utc='2026-10-03T15:36:42Z',ingested_utc='2026-10-03T15:36:43Z',
            capture_ref='_runtime/original/raw.json',implementation='synthetic'))
        rp=self.root/(str(i)+'-receipt.json');cp=self.root/(str(i)+'-raw.json')
        rp.write_bytes(f.canonical_json_bytes(r));cp.write_bytes(body)
        self.receipts.append(r);self.pairs.append(dict(receipt_path=str(rp),content_path=str(cp)))
    def save(self,i=0):Path(self.pairs[i]['receipt_path']).write_bytes(f.canonical_json_bytes(self.receipts[i]))
    def build(self):return f.build_frozen_evidence_manifest(self.request)
    def reject(self):
        with self.assertRaises((ValueError,OSError,TypeError,KeyError)):self.build()
    def test_one_valid_capture(self):
        result=self.build();self.assertTrue(f.validate_frozen_evidence_manifest(result));self.assertEqual(len(result['manifest']['evidence']),1)
    def test_multiple_allowed_sessions(self):
        self.add_capture('drivers','11372',b'[]');self.request['allowed_session_ids'].append('11372')
        self.assertEqual(len(self.build()['manifest']['evidence']),2)
    def test_input_and_session_order_independent(self):
        self.add_capture('drivers','11372',b'[]');self.request['allowed_session_ids'].append('11372')
        first=f.canonical_json_bytes(self.build());self.request['captures'].reverse();self.request['allowed_session_ids'].reverse()
        self.assertEqual(first,f.canonical_json_bytes(self.build()))
    def test_receipt_hash(self):self.assertEqual(self.build()['manifest']['evidence'][0]['receipt_sha256'],f.receipt_sha256(self.receipts[0]))
    def test_receipt_set_gate2b1_algorithm(self):
        self.assertEqual(self.build()['manifest']['input_receipt_manifest_sha256'],f.input_receipt_manifest_sha256(self.receipts))
    def test_exact_content_hash(self):self.assertEqual(self.build()['manifest']['evidence'][0]['source_sha256'],f.sha256(Path(self.pairs[0]['content_path']).read_bytes()))
    def test_wrong_bytes(self):Path(self.pairs[0]['content_path']).write_bytes(b'other');self.reject()
    def test_normalized_bytes_not_substituted(self):Path(self.pairs[0]['content_path']).write_bytes(b'[{"value":1}]');self.reject()
    def test_missing_content(self):Path(self.pairs[0]['content_path']).unlink();self.reject()
    def test_missing_receipt(self):Path(self.pairs[0]['receipt_path']).unlink();self.reject()
    def test_malformed_receipt(self):Path(self.pairs[0]['receipt_path']).write_bytes(b'{bad');self.reject()
    def test_duplicate_json_key(self):Path(self.pairs[0]['receipt_path']).write_bytes(b'{"a":1,"a":2}');self.reject()
    def test_wrong_receipt_type(self):self.receipts[0]['receipt_type']='producer_execution';self.save();self.reject()
    def test_parents(self):self.receipts[0]['parent_receipt_ids']=['other'];self.save();self.reject()
    def test_duplicate_receipt_id(self):
        self.add_capture('other','11371',b'[]');self.receipts[1]['receipt_id']=self.receipts[0]['receipt_id'];self.save(1);self.reject()
    def test_duplicate_source_id(self):self.add_capture('weather','11371',b'[]');self.reject()
    def test_wrong_event(self):self.receipts[0]['scope']['event_id']='other';self.save();self.reject()
    def test_wrong_meeting(self):self.receipts[0]['scope']['meeting_id']='other';self.save();self.reject()
    def test_disallowed_session(self):self.receipts[0]['scope']['session_id']='other';self.save();self.reject()
    def test_empty_evidence(self):self.request['captures']=[];self.reject()
    def test_duplicate_allowed_session(self):self.request['allowed_session_ids']*=2;self.reject()
    def test_malformed_source_hash(self):self.receipts[0]['payload']['source_sha256']='bad';self.save();self.reject()
    def test_unsupported_receipt_trust(self):self.receipts[0]['trusted']=True;self.save();self.reject()
    def test_unsupported_request_trust(self):self.request['production_authenticated']=True;self.reject()
    def test_inconsistent_capture_times(self):self.receipts[0]['payload']['first_observed_utc']='2026-10-03T16:00:00Z';self.save();self.reject()
    def test_relocation_does_not_change_hash(self):
        before=self.build()
        with tempfile.TemporaryDirectory() as other:
            request=copy.deepcopy(self.request)
            for pair in request['captures']:
                for key,path in pair.items():
                    target=Path(other)/Path(path).name;target.write_bytes(Path(path).read_bytes());pair[key]=str(target)
            self.assertEqual(before,f.build_frozen_evidence_manifest(request))
    def test_no_random_clock_discovery(self):
        tree=ast.parse(Path(f.__file__).read_text())
        imported=[a.name for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)) for a in n.names]
        self.assertFalse(set(imported)&{'uuid','random','datetime','time','glob','os','urllib'})
        calls=[n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)]
        self.assertFalse(set(calls)&{'glob','rglob','iterdir','walk','listdir','scandir','now','uuid4'})
    def test_only_explicit_files_read(self):
        (self.root/'undeclared-driver.json').write_bytes(b'contamination')
        paths=[]
        def reader(path):paths.append(path);return Path(path).read_bytes()
        result=f.build_frozen_evidence_manifest(self.request,read_bytes=reader)
        self.assertEqual(paths,[self.pairs[0]['receipt_path'],self.pairs[0]['content_path']]);self.assertEqual(len(result['manifest']['evidence']),1)
    def test_unbound_false_trust_no_execution_receipts(self):
        result=self.build();self.assertEqual(result['manifest']['trust'],f.TRUST)
        self.assertIs(result['manifest']['trust']['production_authenticated'],False)
        self.assertIs(result['manifest']['trust']['historical_availability_proven'],False)
        encoded=f.canonical_json_bytes(result)
        self.assertNotIn(b'producer_execution',encoded);self.assertNotIn(b'engine_execution',encoded)
        self.assertNotIn(b'"input_manifest_sha256"',encoded)
    def test_no_input_mutation(self):
        request=copy.deepcopy(self.request);self.build();self.assertEqual(request,self.request)
    def test_frozen_hash_tamper_rejected(self):
        result=self.build();result['frozen_evidence_manifest_sha256']='0'*64
        with self.assertRaises(ValueError):f.validate_frozen_evidence_manifest(result)
    def test_receipt_set_tamper_rejected(self):
        result=self.build();result['manifest']['input_receipt_manifest_sha256']='0'*64
        with self.assertRaises(ValueError):f.validate_frozen_evidence_manifest(result)
    def test_trust_upgrade_rejected(self):
        result=self.build();result['manifest']['trust']['production_authenticated']=True
        with self.assertRaises(ValueError):f.validate_frozen_evidence_manifest(result)
    def test_bad_source_rejects_entire_set(self):
        self.add_capture('other','11371',b'[]');Path(self.pairs[1]['content_path']).write_bytes(b'bad');self.reject()

if __name__=='__main__':unittest.main()
