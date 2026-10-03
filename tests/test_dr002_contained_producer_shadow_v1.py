"""Offline synthetic CSV fixtures execute the exact pinned generic producer."""
import ast
import copy
from contextlib import chdir
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('contained', Path(__file__).resolve().parents[1] / 'scripts/forecast_bundles/dr002_contained_producer_shadow_v1.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

DRIVERS = b'driver_number,full_name,team_name\n10,Synthetic Ten,Ferrari\n20,Synthetic Twenty,McLaren\n'
GRID = b'driver_number,position\n20,1\n10,2\n'
WEATHER = b'air_temperature,session_key,meeting_key\n25,session,meeting\n'


def source(name, content):
    return dict(source_name=name, source_id='synthetic:' + name, content=content, source_sha256=a.sha256(content))


def receipt(s):
    return dict(schema_version='dr002-receipt-v1', receipt_id='capture:' + s['source_name'], receipt_type='source_capture',
        receipt_created_utc='2026-01-01T09:02:00Z', scope=dict(event_id='synthetic-event', meeting_id='meeting', session_id='session'),
        parent_receipt_ids=[], payload=dict(source_id=s['source_id'],source_uri='synthetic:' + s['source_name'],
            source_sha256=s['source_sha256'], event_time_utc=None, publisher_time_utc=None,
            first_observed_utc='2026-01-01T09:00:00Z', ingested_utc='2026-01-01T09:01:00Z',
            capture_ref='synthetic:bytes', implementation='synthetic-capture'))


class ContainedTests(unittest.TestCase):
    def setUp(self):
        self.kw = dict(sources=[source('drivers',DRIVERS),source('starting_grid',GRID)],
            event_id='synthetic-event',meeting_id='meeting',session_id='session',
            gate='post_qualifying',lane='stable_baseline',forecast_generation_utc='2026-01-01T10:00:00Z')
    def go(self):return a.run_contained_shadow(**self.kw)
    def guarded_producer(self):
        p,code=a.load_current_producer()
        for name in ('find_sources','main','copy_to_latest_and_history','write_csv','write_json','_candidate_priority'):
            setattr(p,name,lambda *args,**kw: (_ for _ in ()).throw(AssertionError('forbidden producer call')))
        return p,code
    def test_actual_functions_called(self):
        p,code=self.guarded_producer()
        funcs=('read_csv','build_driver_universe','starting_grid_map','source_readiness_score','score_driver','probability_from_rank','produce_rows')
        from contextlib import ExitStack
        with ExitStack() as stack:
            spies={n:stack.enter_context(patch.object(p,n,wraps=getattr(p,n))) for n in funcs}
            stack.enter_context(patch.object(a,'load_current_producer',return_value=(p,code)))
            self.go()
            for n,spy in spies.items():self.assertTrue(spy.called,n)
    def test_discovery_and_writes_never_called(self):
        with patch.object(a,'load_current_producer',return_value=self.guarded_producer()):self.assertEqual(self.go()['result']['generated_row_count'],2)
    def test_rglob_cannot_influence(self):
        with patch.object(Path,'rglob',side_effect=AssertionError('discovery')):self.go()
    def test_rogue_drivers_ignored(self):
        before=self.go()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'repo/latest/openf1_lightweight_source_closure/data/drivers.csv';p.parent.mkdir(parents=True);p.write_bytes(b'driver_number,full_name,team_name\n99,Rogue,Ferrari\n')
            with chdir(Path(d)/'repo'):self.assertEqual(before,self.go())
    def test_rogue_grid_ignored(self):
        before=self.go()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'repo/history/openf1_lightweight_source_closure/starting_grid.csv';p.parent.mkdir(parents=True);p.write_bytes(b'driver_number,position\n99,1\n10,99\n')
            with chdir(Path(d)/'repo'):self.assertEqual(before,self.go())
    def test_latest_history_not_implicit(self):
        r=self.go()['result'];self.assertEqual([d['driver_number'] for d in r['driver_universe']],[10,20]);self.assertEqual(r['starting_grid'],{'10':2,'20':1});self.assertIn('weather',r['absent_source_names'])
    def test_explicit_byte_origin_not_filename(self):
        # Bytes can be supplied from any origin; there is no source path interface.
        self.kw['sources'][0]['source_id']='explicit:latest-drivers-copy';self.assertEqual(self.go()['result']['generated_row_count'],2)
    def test_undeclared_sources_do_not_affect_hash(self):
        before=self.go()
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)/'repo'
            for folder in ('latest/openf1_lightweight_source_closure/data','history/openf1_lightweight_source_closure'):
                root=repo/folder;root.mkdir(parents=True)
                for name,data in [('drivers',b'driver_number,name,team_name\n99,Rogue,Mercedes\n'),('starting_grid',b'driver_number,position\n99,1\n10,98\n'),('weather',WEATHER),('pit',b'driver_number,pit_duration\n99,20\n')]:
                    (root/(name+'.csv')).write_bytes(data)
            with chdir(repo):after=self.go()
        self.assertEqual(before,after)
        self.assertEqual(before['result']['source_readiness_score'],after['result']['source_readiness_score'])
        self.assertEqual(before['result']['starting_grid'],after['result']['starting_grid'])
    def test_declared_weather_changes_readiness(self):
        before=self.go()['result'];self.kw['sources'].append(source('weather',WEATHER));after=self.go()['result'];self.assertGreater(after['source_readiness_score'],before['source_readiness_score']);self.assertEqual(after['driver_universe'],before['driver_universe']);self.assertEqual(after['source_counts']['weather'],1)
    def test_readiness_remove_source(self):
        self.kw['sources'].append(source('weather',WEATHER));high=self.go()['result']['source_readiness_score'];self.kw['sources'].pop();self.assertLess(self.go()['result']['source_readiness_score'],high)
    def test_tampered_bound_bytes_fail(self):
        self.kw['sources'][0]['content']+=b' ';self.assertRaises(a.ShadowError,self.go)
    def test_changed_declared_bytes_changes_hash(self):
        before=self.go();s=self.kw['sources'][0];s['content']=s['content'].replace(b'Ferrari',b'Mercedes');s['source_sha256']=a.sha256(s['content']);self.assertNotEqual(before['canonical_shadow_output_sha256'],self.go()['canonical_shadow_output_sha256'])
    def test_missing_exact_bytes_fails(self):self.kw['sources'][0]['content']=None;self.assertRaises(a.ShadowError,self.go)
    def test_missing_source_field_fails(self):self.kw['sources'][0].pop('content');self.assertRaises(a.ShadowError,self.go)
    def test_duplicate_source_name_fails(self):self.kw['sources'].append(source('drivers',DRIVERS));self.assertRaises(a.ShadowError,self.go)
    def test_duplicate_source_id_fails(self):self.kw['sources'][1]['source_id']=self.kw['sources'][0]['source_id'];self.assertRaises(a.ShadowError,self.go)
    def test_unknown_source_fails(self):self.kw['sources'].append(source('../../latest/drivers',DRIVERS));self.assertRaises(a.ShadowError,self.go)
    def test_invalid_gate_fails(self):self.kw['gate']='final_pre_race';self.assertRaises(a.ShadowError,self.go)
    def test_invalid_lane_fails(self):self.kw['lane']='stable-engine';self.assertRaises(a.ShadowError,self.go)
    def test_generation_time_exact(self):self.assertTrue(all(r['forecast_generation_utc']==self.kw['forecast_generation_utc'] for r in self.go()['result']['rows']))
    def test_clock_cannot_leak_and_restored(self):
        p,code=self.guarded_producer()
        def no_clock():raise AssertionError('wall clock leaked')
        p.utc_now=no_clock
        with patch.object(a,'load_current_producer',return_value=(p,code)):self.go()
        self.assertIs(p.utc_now,no_clock)
    def test_clock_restored_on_failure(self):
        p,code=self.guarded_producer();original=p.utc_now
        with patch.object(p,'produce_rows',side_effect=RuntimeError('row failure')),patch.object(a,'load_current_producer',return_value=(p,code)):
            self.assertRaises(RuntimeError,self.go)
        self.assertIs(p.utc_now,original)
    def test_deterministic_bytes_and_hash(self):
        r=self.go();self.assertEqual(a.canonical_json_bytes(r),a.canonical_json_bytes(self.go()));self.assertEqual(r['canonical_shadow_output_sha256'],a.sha256(a.canonical_json_bytes(r['result'])))
    def test_input_order_does_not_change(self):
        before=self.go();self.kw['sources'].reverse();self.assertEqual(before,self.go())
    def test_no_input_mutation(self):before=copy.deepcopy(self.kw);self.go();self.assertEqual(before,self.kw)
    def test_rows_not_rewritten(self):
        rows=self.go()['result']['rows'];self.assertEqual(rows[0]['forecast_status'],'actual_forecast_row_generated_from_available_sources');self.assertEqual(rows[0]['engine_lane'],'stable_baseline')
    def test_shadow_wrapper_limits(self):
        r=self.go()['result'];self.assertEqual(r['status'],a.STATUS);self.assertFalse(r['production_forecast_generated']);self.assertFalse(r['blind_validation_eligible']);self.assertIsNone(r['engine_implementation']);self.assertEqual(r['engine_execution'],'NOT_PROVEN');self.assertFalse(r['stable_engine_executed'])
    def test_no_receipts_or_authentication(self):
        r=self.go()['result'];self.assertNotIn('engine_execution_receipt',r);self.assertNotIn('verified_receipt_bindings',r);self.assertFalse(r['trust']['production_authenticated']);self.assertFalse(r['trust']['dr002_activated'])
    def test_receipt_helper_used(self):
        for s in self.kw['sources']:s['receipt']=receipt(s)
        r=self.go()['result'];self.assertEqual(len(r['frozen_receipt_evidence']['manifest']['evidence']),2);self.assertEqual(r['trust']['binding_status'],'UNBOUND')
    def test_receipt_scope_mismatch_fails(self):
        s=self.kw['sources'][0];s['receipt']=receipt(s);s['receipt']['scope']['meeting_id']='wrong';self.assertRaises(ValueError,self.go)
    def test_receipt_hash_mismatch_fails(self):
        s=self.kw['sources'][0];s['receipt']=receipt(s);s['receipt']['payload']['source_sha256']='0'*64;self.assertRaises(ValueError,self.go)
    def test_csv_scope_mismatch_fails(self):self.kw['sources'].append(source('weather',WEATHER.replace(b'session,meeting',b'wrong,meeting')));self.assertRaises(a.ShadowError,self.go)
    def test_only_temp_declared_paths_read(self):
        p,code=self.guarded_producer();seen=[];real=p.read_csv
        def track(path):seen.append(path);return real(path)
        with patch.object(p,'read_csv',side_effect=track),patch.object(a,'load_current_producer',return_value=(p,code)):self.go()
        self.assertEqual({p.name for p in seen},{'drivers.csv','starting_grid.csv'});self.assertTrue(all('dr002-contained-shadow-' in str(p.parent) for p in seen));self.assertTrue(all(not p.exists() for p in seen))
    def test_no_production_directories_written(self):
        real_write=Path.write_bytes;written=[]
        def track(path,data):written.append(path);return real_write(path,data)
        with patch.object(Path,'write_bytes',track):self.go()
        self.assertEqual(len(written),2);self.assertTrue(all(not {'latest','history','ledgers','workbooks'}&set(p.parts) for p in written))
    def test_producer_fingerprint_bound(self):self.assertEqual(self.go()['result']['producer_git_blob_sha'],a.PRODUCER_BLOB_SHA)
    def test_changed_producer_fails_before_exec(self):
        with patch.object(Path,'read_bytes',return_value=b'raise AssertionError("must not execute")'):self.assertRaises(a.ShadowError,a.load_current_producer)
    def test_empty_set_fails(self):self.kw['sources']=[];self.assertRaises(a.ShadowError,self.go)
    def test_no_drivers_fails(self):self.kw['sources']=[source('weather',WEATHER)];self.assertRaises(a.ShadowError,self.go)
    def test_grid_only_exact_universe(self):self.kw['sources']=[source('starting_grid',GRID)];self.assertEqual([d['driver_number'] for d in self.go()['result']['driver_universe']],[10,20])
    def test_missing_source_counts_zero(self):r=self.go()['result'];self.assertTrue(all(r['source_counts'][n]==0 for n in r['absent_source_names']))
    def test_adapter_no_discovery_or_network(self):
        t=ast.parse(Path(a.__file__).read_text());attrs={n.attr for n in ast.walk(t) if isinstance(n,ast.Attribute)};self.assertFalse(attrs&{'glob','rglob','walk','iterdir','listdir','scandir','now','urlopen','find_sources','main','copy_to_latest_and_history','write_csv','write_json'})

if __name__=='__main__':unittest.main()
