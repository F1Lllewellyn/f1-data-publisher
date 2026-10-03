import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

spec=importlib.util.spec_from_file_location('pilot',Path(__file__).resolve().parents[1]/'scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py')
p=importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
BODY=b'[ {"session_key":11371,"meeting_key":1295,"date":"2026-09-18T13:00:00Z","air_temperature":27.1} ]\n'
TIMES=['2026-10-03T14:00:00Z','2026-10-03T14:00:01Z','2026-10-03T14:00:02Z','2026-10-03T14:00:03Z']

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.package=self.root/'test'
    def capture(self,body=BODY,status=200,**kwargs):
        self.request=kwargs.pop('request',Mock(return_value=(status,body)))
        return p.capture('test',request=self.request,clock=kwargs.pop('clock',Mock(side_effect=TIMES)),runtime_root=self.root,**kwargs)
    def receipt(self):
        return json.loads((self.package/'source_capture_receipt.json').read_bytes())
    def hold(self,**kwargs):
        m=self.capture(**kwargs)
        self.assertEqual(m['validation_status'],'HOLD')
        self.assertFalse((self.package/'source_capture_receipt.json').exists())
        self.assertIsNone(m['receipt_path']); self.assertIsNone(m['receipt_sha256'])
        self.assertTrue((self.package/'capture_manifest.json').exists())
        self.assertTrue((self.package/'pilot_report.md').exists())
        return m
    def test_exact_raw_bytes_hash_readback(self):
        m=self.capture(); self.assertEqual((self.package/'raw/openf1_weather.response.json').read_bytes(),BODY)
        self.assertEqual(m['source_sha256'],hashlib.sha256(BODY).hexdigest())
        self.assertEqual(m['source_sha256'],m['readback_sha256']); self.assertTrue(m['readback_verified'])
        self.assertEqual(m['byte_count'],len(BODY)); self.assertEqual(m['validation_status'],'CAPTURED_UNBOUND')
    def test_normalized_cannot_replace_raw_hash(self):
        m=self.capture(); raw=hashlib.sha256(BODY).hexdigest()
        normalized=(self.package/'normalized/openf1_weather.normalized.json').read_bytes()
        self.assertEqual(m['normalized_sha256'],hashlib.sha256(normalized).hexdigest())
        self.assertNotEqual(m['normalized_sha256'],raw); self.assertEqual(self.receipt()['payload']['source_sha256'],raw)
    def test_observation_completion_and_ingestion_after_readback(self):
        events=[]; times=iter(TIMES)
        def clock(): events.append('clock'); return next(times)
        def request(): events.append('complete'); return 200,BODY
        def writer(path,data): events.append('write'); p.write_bytes(path,data)
        def reader(path): events.append('read'); return path.read_bytes()
        m=self.capture(clock=clock,request=request,writer=writer,reader=reader)
        self.assertEqual(events[:6],['clock','complete','clock','write','read','clock'])
        self.assertEqual(m['first_observed_utc'],TIMES[1]); self.assertEqual(m['response_completed_utc'],TIMES[1])
        self.assertNotEqual(m['first_observed_utc'],m['request_started_utc'])
    def test_time_order_request(self): self.hold(clock=Mock(side_effect=list(reversed(TIMES))))
    def test_time_order_ingestion(self): self.hold(clock=Mock(side_effect=[TIMES[0],TIMES[2],TIMES[1],TIMES[3]]))
    def test_time_order_creation(self): self.hold(clock=Mock(side_effect=[TIMES[0],TIMES[1],TIMES[3],TIMES[2]]))
    def test_invalid_timestamp(self): self.hold(clock=Mock(side_effect=['invalid']+TIMES[1:]))
    def test_equal_times_allowed(self): self.assertEqual(self.capture(clock=lambda:TIMES[0])['validation_status'],'CAPTURED_UNBOUND')
    def test_receipt_scope_and_compatibility(self):
        self.capture(); r=self.receipt(); self.assertEqual(r['scope'],p.SCOPE)
        self.assertTrue(p.validate_receipt_envelope(r)); self.assertTrue(p.verify_temporal_bindings(r))
        self.assertEqual(r['payload']['source_uri'],p.URI); self.assertEqual(r['parent_receipt_ids'],[])
        self.assertIsNone(r['payload']['event_time_utc']); self.assertIsNone(r['payload']['publisher_time_utc'])
    def test_wrong_session(self): self.hold(body=BODY.replace(b'11371',b'11372'))
    def test_wrong_meeting(self): self.hold(body=BODY.replace(b'1295',b'1296'))
    def test_missing_session(self):
        row=json.loads(BODY)[0]; del row['session_key']; self.hold(body=json.dumps([row]).encode())
    def test_missing_meeting(self):
        row=json.loads(BODY)[0]; del row['meeting_key']; self.hold(body=json.dumps([row]).encode())
    def test_empty_bytes(self): self.hold(body=b'')
    def test_malformed_json(self): self.hold(body=b'{bad')
    def test_nonlist_json(self): self.hold(body=b'{}')
    def test_zero_rows(self): self.hold(body=b'[]')
    def test_nonobject_row(self): self.hold(body=b'[1]')
    def test_no_weather_measurement(self):
        row=json.loads(BODY)[0]; del row['air_temperature']; self.hold(body=json.dumps([row]).encode())
    def test_invalid_row_date(self): self.hold(body=BODY.replace(b'2026-09-18T13:00:00Z',b'bad'))
    def test_nonfinite_json(self): self.hold(body=BODY.replace(b'27.1',b'NaN'))
    def test_duplicate_rows(self): self.hold(body=json.dumps(json.loads(BODY)*2).encode())
    def test_non200_no_retry(self): self.hold(status=503); self.request.assert_called_once_with()
    def test_transport_exception_no_retry(self):
        request=Mock(side_effect=OSError('network')); self.hold(request=request); request.assert_called_once_with()
    def test_raw_write_failure(self):
        def writer(path,data):
            if path.name.endswith('response.json'): raise OSError('disk')
            p.write_bytes(path,data)
        self.hold(writer=writer)
    def test_read_failure(self): self.hold(reader=Mock(side_effect=OSError('read')))
    def test_readback_mismatch(self): self.hold(reader=lambda path:b'tampered')
    def test_structural_validation_exception(self): self.hold(validator=Mock(side_effect=ValueError('schema')))
    def test_structural_validation_false(self): self.hold(validator=lambda receipt:False)
    def test_normalized_write_failure(self):
        def writer(path,data):
            if path.name.endswith('normalized.json'): raise OSError('disk')
            p.write_bytes(path,data)
        self.hold(writer=writer)
    def test_receipt_candidate_readback_failure(self):
        self.hold(reader=lambda path:b'tampered' if path.name=='receipt_candidate.diagnostic.json' else path.read_bytes())
    def test_trust_flags(self):
        m=self.capture(); self.assertEqual(m['binding_status'],'UNBOUND')
        for key in ['production_authenticated','historical_availability_proven','dr002_activated']: self.assertIs(m[key],False)
        self.assertNotIn('verified_receipt_bindings',m); self.assertNotIn('trusted',self.receipt())
    def test_deterministic_receipt_identity_and_hash(self):
        m=self.capture(); r=self.receipt()
        self.assertEqual(r['receipt_id'],'source_capture:'+p.sha256(p.canonical_json_bytes({
            'source_id':'openf1:weather:1295:11371', **p.SCOPE,
            'source_sha256':hashlib.sha256(BODY).hexdigest(),'first_observed_utc':TIMES[1]})))
        self.assertEqual(m['receipt_sha256'],p.receipt_sha256(r))
    def test_existing_run_not_overwritten(self):
        self.capture(); original=(self.package/'source_capture_receipt.json').read_bytes(); request=Mock()
        with self.assertRaises(FileExistsError): p.capture('test',request=request,runtime_root=self.root)
        request.assert_not_called(); self.assertEqual(original,(self.package/'source_capture_receipt.json').read_bytes())
    def test_traversal_rejected(self):
        request=Mock()
        with self.assertRaises(ValueError): p.capture('../latest',request=request,runtime_root=self.root)
        request.assert_not_called()
    def test_transport_single_complete_read(self):
        response=MagicMock(); response.status=200; response.read.return_value=BODY
        manager=MagicMock(); manager.__enter__.return_value=response
        with patch.object(p,'urlopen',return_value=manager) as opener:
            self.assertEqual(p.transport(),(200,BODY)); opener.assert_called_once(); response.read.assert_called_once_with()
            self.assertEqual(opener.call_args.args[0].full_url,p.URI)

    def test_manifest_persistence_failure_no_published_receipt(self):
        def writer(path,data):
            if path.name=='capture_manifest.json': raise OSError('manifest failure')
            p.write_bytes(path,data)
        with self.assertRaises(OSError): self.capture(writer=writer)
        self.assertFalse((self.package/'source_capture_receipt.json').exists())
        self.assertTrue((self.package/'receipt_candidate.diagnostic.json').exists())
    def test_report_persistence_failure_no_published_receipt(self):
        def writer(path,data):
            if path.name=='pilot_report.md': raise OSError('report failure')
            p.write_bytes(path,data)
        with self.assertRaises(OSError): self.capture(writer=writer)
        self.assertFalse((self.package/'source_capture_receipt.json').exists())
        self.assertTrue((self.package/'receipt_candidate.diagnostic.json').exists())
    def test_final_rename_failure_no_published_receipt(self):
        with patch.object(Path,'rename',side_effect=OSError('rename failure')):
            with self.assertRaises(OSError): self.capture()
        self.assertFalse((self.package/'source_capture_receipt.json').exists())
        self.assertTrue((self.package/'capture_manifest.json').exists())
        self.assertTrue((self.package/'pilot_report.md').exists())
    def test_final_receipt_published_last(self):
        def writer(path,data):
            self.assertFalse((self.package/'source_capture_receipt.json').exists())
            p.write_bytes(path,data)
        self.capture(writer=writer)
        self.assertTrue((self.package/'source_capture_receipt.json').exists())
    def test_same_observation_same_id(self):
        self.capture(); first=self.receipt()['receipt_id']
        with tempfile.TemporaryDirectory() as root:
            p.capture('other',request=lambda:(200,BODY),clock=Mock(side_effect=TIMES),runtime_root=root)
            second=json.loads((Path(root)/'other/source_capture_receipt.json').read_bytes())['receipt_id']
        self.assertEqual(first,second)
    def test_different_observation_different_id(self):
        self.capture(); first=self.receipt()['receipt_id']
        later=[t.replace('14:00','15:00') for t in TIMES]
        with tempfile.TemporaryDirectory() as root:
            p.capture('other',request=lambda:(200,BODY),clock=Mock(side_effect=later),runtime_root=root)
            second=json.loads((Path(root)/'other/source_capture_receipt.json').read_bytes())['receipt_id']
        self.assertNotEqual(first,second)
    def test_identity_has_no_random_uuid_dependency(self):
        import ast
        tree=ast.parse(Path(p.__file__).read_text())
        imports=[alias.name for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom)) for alias in node.names]
        self.assertFalse(any(name in ('uuid','random','uuid4') for name in imports))

if __name__=='__main__': unittest.main()
