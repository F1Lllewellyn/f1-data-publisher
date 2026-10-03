import csv, hashlib, importlib.util, io, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('producer',Path(__file__).resolve().parents[1]/'scripts/forecasts/produce_actual_forecast_rows_v1.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
D=b'driver_number,full_name,team_name\n10,Synthetic Ten,Ferrari\n20,Synthetic Twenty,McLaren\n'
G=b'driver_number,position\n20,1\n10,2\n'
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.file=self.root/'inputs/manifest.json';self.file.parent.mkdir()
  self.m=dict(schema_version=p.FROZEN_SCHEMA,event_id='event',meeting_id='1295',session_id='11371',sources=[])
  self.add('drivers',D);self.add('starting_grid',G)
 def add(self,n,b):
  (self.file.parent/(n+'.csv')).write_bytes(b);self.m['sources'].append(dict(source_name=n,source_id='source:'+n,relative_path=n+'.csv',source_sha256=hashlib.sha256(b).hexdigest()))
 def save(self):self.file.write_text(json.dumps(self.m))
 def run_inputs(self):
  self.save()
  with p.frozen_sources(self.file,'event','1295','11371') as (s,c,a):
   return p.produce_rows('event','Synthetic','post_qualifying','stable_baseline',p.build_driver_universe(s),p.starting_grid_map(s),c,s),c,a
 def fail(self):
  with self.assertRaises((ValueError,OSError,csv.Error)):self.run_inputs()
 def cli(self,frozen=True,extra=()):
  self.save();args=['p','--repo-root',str(self.root),'--event-id','event','--gate','post_qualifying','--lane','stable_baseline']
  if frozen:args+=['--frozen-input-manifest',str(self.file),'--meeting-id','1295','--session-id','11371']
  with patch.object(sys,'argv',args+list(extra)),patch('sys.stdout',new=io.StringIO()),patch.object(p,'copy_to_latest_and_history') as writer:return p.main(),writer
 def test_default_discovery(self):
  with patch.object(p,'find_sources',return_value=({},dict.fromkeys(p.SOURCE_FILES,0))) as f:self.cli(False)
  f.assert_called_once_with(self.root)
 def test_no_discovery_frozen(self):
  with patch.object(p,'find_sources',side_effect=AssertionError),patch.object(Path,'glob',side_effect=AssertionError),patch.object(Path,'rglob',side_effect=AssertionError):self.cli()
 def test_real_scoring(self):
  with patch.object(p,'score_driver',wraps=p.score_driver) as s,patch.object(p,'probability_from_rank',wraps=p.probability_from_rank) as q:r,c,a=self.run_inputs()
  self.assertEqual(len(r),2);self.assertEqual(s.call_count,2);self.assertEqual(q.call_count,6)
 def test_rogue_latest_history_and_adjacent(self):
  with patch.object(p,'utc_now',return_value='CLOCK'):
   before=self.run_inputs()
   for folder in ('latest/openf1','history/openf1','inputs'):
    d=self.root/folder;d.mkdir(parents=True,exist_ok=True);(d/'weather.csv').write_bytes(b'air_temperature\n99\n');(d/('undeclared_drivers.csv' if folder=='inputs' else 'drivers.csv')).write_bytes(b'driver_number,name\n999,Rogue\n')
   self.assertEqual(before,self.run_inputs())
 def test_readiness_declared_only(self):
  self.assertEqual(p.source_readiness_score(self.run_inputs()[1],'post_qualifying'),.38);self.add('weather',b'air_temperature\n25\n');self.assertEqual(p.source_readiness_score(self.run_inputs()[1],'post_qualifying'),.48);self.m['sources'].pop();self.assertEqual(self.run_inputs()[1]['weather'],0)
 def test_missing_file(self):(self.file.parent/'drivers.csv').unlink();self.fail()
 def test_tampered_file(self):(self.file.parent/'drivers.csv').write_bytes(b'tampered');self.fail()
 def test_symlink_escape(self):
  f=self.file.parent/'drivers.csv';f.unlink();outside=self.root/'outside.csv';outside.write_bytes(D);f.symlink_to(outside);self.fail()
 def test_symlink_inside(self):
  f=self.file.parent/'drivers.csv';f.unlink();other=self.file.parent/'other.csv';other.write_bytes(D);f.symlink_to(other);self.fail()
 def test_invalid_gate(self):
  with self.assertRaises(SystemExit):self.cli(extra=['--gate','bad'])
 def test_invalid_lane(self):
  with self.assertRaises(SystemExit):self.cli(extra=['--lane','bad'])
 def test_missing_scope(self):
  with self.assertRaises(ValueError):self.cli(extra=['--session-id',''])
 def test_metadata(self):
  _,w=self.cli();meta=w.call_args.args[-1];self.assertEqual(meta['input_mode'],'frozen_manifest');self.assertFalse(meta['broad_discovery_used']);self.assertEqual(meta['frozen_manifest_sha256'],hashlib.sha256(self.file.read_bytes()).hexdigest());self.assertEqual(w.call_args.args[-2][0]['source_id'],'source:drivers')
  for k in ('production_authenticated','historical_availability_proven','stable_engine_execution_proven','dr002_activated'):self.assertIs(meta[k],False)
  audit=list((self.root/'_runtime/actual_forecast_producer_v1').iterdir())[0]/'actual_forecast_producer_audit.json';self.assertEqual(json.loads(audit.read_text())['input_mode'],'frozen_manifest')
 def test_default_schema_unchanged(self):
  s={'drivers':self.file.parent/'drivers.csv','starting_grid':self.file.parent/'starting_grid.csv'}
  with patch.object(p,'find_sources',return_value=(s,dict(drivers=2,starting_grid=2))):_,w=self.cli(False)
  self.assertEqual(set(w.call_args.args[-2][0]),{'source_name','found','row_count','path'});self.assertNotIn('input_mode',w.call_args.args[-1])
 def test_snapshot_exact_and_disposed(self):
  self.save()
  with p.frozen_sources(self.file,'event','1295','11371') as (s,c,a):
   self.assertEqual(s['drivers'].read_bytes(),D);(self.file.parent/'drivers.csv').write_bytes(b'driver_number,name\n999,Rogue\n');self.assertEqual([v['driver_number'] for v in p.build_driver_universe(s)],[10,20]);f=s['drivers']
  self.assertFalse(f.exists())
 def test_generation_clock(self):
  with patch.object(p,'utc_now',return_value='CLOCK'):self.assertTrue(all(r['forecast_generation_utc']=='CLOCK' for r in self.run_inputs()[0]))
 def test_order(self):
  with patch.object(p,'utc_now',return_value='CLOCK'):
   b=self.run_inputs();self.m['sources'].reverse();a=self.run_inputs()
  self.assertEqual(b[:2],a[:2]);self.assertEqual(b[2]['sources'],a[2]['sources'])
 def test_duplicate_json(self):
  self.save();self.file.write_text(self.file.read_text().replace('"event_id": "event"','"event_id": "event", "event_id": "event"'))
  with self.assertRaises(ValueError):
   with p.frozen_sources(self.file,'event','1295','11371'):pass
 def test_correct_row_scope(self):
  data=b'driver_number,event_id,meeting_id,session_key\n10,event,1295,11371\n';(self.file.parent/'drivers.csv').write_bytes(data);self.m['sources'][0]['source_sha256']=hashlib.sha256(data).hexdigest();self.assertEqual(len(self.run_inputs()[0]),2)

# Each generated method represents a separate explicit malformed-input fixture.
def bad_entry(field,value,index=0):
 def test(self):self.m['sources'][index][field]=value;self.fail()
 return test
for name,field,value,index in [
 ('unknown_source','source_name','unknown',0),('duplicate_name','source_name','drivers',1),('duplicate_id','source_id','source:drivers',1),('duplicate_path','relative_path','drivers.csv',1),('absolute','relative_path','/tmp/drivers.csv',0),('traversal','relative_path','../drivers.csv',0),('dot_path','relative_path','./drivers.csv',0),('backslash','relative_path','dir\\drivers.csv',0),('malformed_hash','source_sha256','bad',0),('blank_id','source_id','',0)]:setattr(Tests,'test_'+name,bad_entry(field,value,index))
def bad_csv(data):
 def test(self):(self.file.parent/'drivers.csv').write_bytes(data);self.m['sources'][0]['source_sha256']=hashlib.sha256(data).hexdigest();self.fail()
 return test
for name,data in [('empty',b''),('header_only',b'driver_number,name\n'),('unclosed',b'driver_number,name\n10,"unfinished'),('extra_column',b'driver_number,name\n10,Name,extra\n'),('missing_column',b'driver_number,name\n10\n'),('duplicate_column',b'name,name\na,b\n'),('null',b'driver_number,name\n10,\x00\n'),('wrong_event',b'driver_number,event_id\n10,wrong\n'),('wrong_meeting',b'driver_number,meeting_key\n10,999\n'),('wrong_session',b'driver_number,session_id\n10,999\n')]:setattr(Tests,'test_csv_'+name,bad_csv(data))
def bad_top(field,value):
 def test(self):self.m[field]=value;self.fail()
 return test
for field,value in [('event_id','wrong'),('meeting_id','wrong'),('session_id','wrong'),('sources',[]),('schema_version','wrong'),('trusted',True)]:setattr(Tests,'test_manifest_'+field,bad_top(field,value))
if __name__=='__main__':unittest.main()
