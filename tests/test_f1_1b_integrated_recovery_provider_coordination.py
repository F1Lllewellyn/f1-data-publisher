"""Real client/limiter and actual workflow admission contracts; no live HTTP."""
import ast
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import yaml
from test_openf1_normal_incremental_collection_budget_v1 import m, FakeClock
from test_f1_1b_integrated_recovery_byte_custody import processor
ROOT=Path(__file__).resolve().parents[1]


def client_fixture(status=200):
    path=ROOT/'scripts/openf1/openf1_high_frequency_auto_ingest.py'
    node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='OpenF1Client')
    clock=FakeClock(); calls=[]
    def get(*a,**kw):
        calls.append((clock.monotonic(),kw))
        return types.SimpleNamespace(status_code=status,text='[]',json=lambda:[])
    namespace=dict(BASE_URL='https://provider.invalid',requests=types.SimpleNamespace(get=get),time=types.SimpleNamespace(sleep=clock.sleep,monotonic=clock.monotonic))
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    with patch.dict(sys.modules,{'publish_openf1_lightweight_source_closure':m}):
        client=namespace['OpenF1Client'](token='synthetic-test-token')
    return client,clock,calls


class ProviderCoordinationTests(unittest.TestCase):
    def test_corrupt_wire_response_is_retained_and_latches_following_requests(self):
        raw=b'{broken json'
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return raw
        clock=FakeClock();budget=m.NormalRequestBudget(clock=clock.monotonic,sleeper=clock.sleep)
        with patch.object(processor,'REQUEST_BUDGET',budget),patch.object(processor.urllib.request,'urlopen',return_value=Response()) as get:
            rows,meta=processor.http_json('https://provider.invalid')
            self.assertFalse(meta['ok']);self.assertEqual(rows,[])
            self.assertEqual(bytes.fromhex(meta['_response_hex']),raw)
            self.assertTrue(meta['observed_at_utc'])
            self.assertFalse(processor.http_json('https://provider.invalid')[1]['ok'])
            self.assertEqual(get.call_count,1)

    def test_cancelled_or_finished_process_handover_protects_both_windows(self):
        clock=FakeClock(); stamps=[]
        with patch.dict(os.environ,{'F1_OPENF1_HANDOVER_REQUIRED':'true'}):
            for _ in range(3):
                budget=m.NormalRequestBudget(clock=clock.monotonic,sleeper=clock.sleep)
                for _ in range(32):
                    budget.acquire(); stamps.append(clock.monotonic())
        for end in stamps:
            self.assertLessEqual(sum(end-60<t<=end for t in stamps),30)
            self.assertLessEqual(sum(end-1<t<=end for t in stamps),3)
        self.assertTrue(all(x<=30.5 or x<=60 for x in clock.sleeps))

    def test_actual_high_frequency_client_respects_limits_and_preserves_token(self):
        client,clock,calls=client_fixture()
        with patch.dict(sys.modules,{'publish_openf1_lightweight_source_closure':m}):
            for _ in range(31): self.assertEqual(client.get('sessions')[1]['status_code'],200)
        self.assertGreaterEqual(calls[-1][0]-calls[0][0],60)
        self.assertEqual(calls[0][1]['headers'],{'Authorization':'Bearer synthetic-test-token'})
        for stamp,_ in calls:self.assertLessEqual(sum(stamp-1<t<=stamp for t,_ in calls),3)

    def test_access_throttle_and_outage_latch_without_retry_storm(self):
        for status in (401,403,429,503):
            with self.subTest(status=status):
                client,_,calls=client_fixture(status)
                with patch.dict(sys.modules,{'publish_openf1_lightweight_source_closure':m}):
                    for _ in range(20): self.assertIsNone(client.get('weather')[0])
                self.assertEqual(len(calls),1)

    def test_actual_entry_points_share_admission_and_single_scheduled_capture_owner(self):
        names=('f1-peak-elite-control-room-one-click-v1','f1-openf1-lightweight-source-closure','f1-session-data-processor-loop-v1','f1-session-autorepair-integrated-loop-v1','f1-session-autorepair-integrated-run-now-button-v1','openf1-prerace-auto-ingest','openf1-post-race-auto-reliability','openf1-full-historical-auto-ingest')
        for name in names:
            text=(ROOT/'.github/workflows'/f'{name}.yml').read_text(); doc=yaml.safe_load(text)
            self.assertEqual(doc['concurrency'],{'group':'f1-main-write-serialization','cancel-in-progress':False})
            self.assertEqual(doc['env']['F1_OPENF1_HANDOVER_REQUIRED'],'true')
            if name.startswith('openf1-'):
                self.assertIn('HOLD_OPTIONAL_TELEMETRY_DEFERRED_FOR_WEEKEND_CAPTURE',text)
                self.assertEqual(doc['jobs']['extract_and_checkpoint']['timeout-minutes'],30)
            if name in ('f1-session-data-processor-loop-v1','f1-session-autorepair-integrated-loop-v1'):
                self.assertNotIn('schedule',doc.get('on',doc.get(True)))
                self.assertIn('workflow_dispatch',doc.get('on',doc.get(True)))
        legacy=yaml.safe_load((ROOT/'.github/workflows/f1-session-data-processor-run-now-button-v1.yml').read_text(encoding='utf-8-sig'))
        self.assertEqual(legacy['concurrency']['group'],'f1-main-write-serialization')
        with patch.dict(os.environ,{'GITHUB_WORKFLOW':legacy['name']}):
            clock=FakeClock(); budget=m.NormalRequestBudget(clock=clock.monotonic,sleeper=clock.sleep);budget.acquire()
            self.assertEqual(clock.monotonic(),61)

    def test_processor_retains_actual_returned_bytes_and_clock(self):
        raw=b'[ { "session_key" : 100, "meeting_key" : 10 } ]\n'
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return raw
        clock=FakeClock()
        budget=m.NormalRequestBudget(clock=clock.monotonic,sleeper=clock.sleep)
        with patch.object(processor,'REQUEST_BUDGET',budget),patch.object(processor.urllib.request,'urlopen',return_value=Response()),patch.object(processor,'iso_now',return_value='2026-11-20T02:00:00Z'):
            rows,meta=processor.http_json('https://provider.invalid')
        self.assertEqual(bytes.fromhex(meta['_response_hex']),raw)
        self.assertEqual(meta['observed_at_utc'],'2026-11-20T02:00:00Z')
        self.assertEqual(rows[0]['session_key'],100)
