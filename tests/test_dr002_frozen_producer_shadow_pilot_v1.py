"""Offline subprocess tests run the accepted real producer on synthetic bytes."""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pilot', ROOT / 'scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
REAL_RUN = subprocess.run
SHA = '4f3d322478083d20f1a1c63be96a17a4f78bcdbd'

class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = self.root / 'runtime'
        context = patch.object(p, 'RUNTIME_ROOT', self.runtime)
        context.start(); self.addCleanup(context.stop)
        self.sequence = 0
    def run_pilot(self, weather=True):
        self.sequence += 1
        return p.run_pilot(run_id='offline-' + str(self.sequence), implementation_git_sha=SHA, include_weather=weather)
    def result_dir(self):
        return self.runtime / ('offline-' + str(self.sequence))
    def test_accepted_code_blob(self):
        result = self.run_pilot()
        code = p.PRODUCER_PATH.read_bytes()
        self.assertEqual(p.git_blob_sha(code), p.PRODUCER_BLOB_SHA)
        self.assertEqual(result['producer_code_sha256'], hashlib.sha256(code).hexdigest())
    def test_changed_code_fails_before_execution(self):
        wrong = self.root / 'wrong.py'; wrong.write_bytes(b'changed')
        with patch.object(p, 'PRODUCER_PATH', wrong), patch.object(p.subprocess, 'run') as runner:
            with self.assertRaises(p.PilotError): self.run_pilot()
        runner.assert_not_called()
    def test_real_cli_explicit_scope_and_sandbox(self):
        observed = []
        def runner(command, **kw):
            observed.append((command, kw))
            self.assertEqual(Path(command[1]), p.PRODUCER_PATH)
            for option, value in (('--event-id',p.EVENT_ID),('--meeting-id',p.MEETING_ID),('--session-id',p.SESSION_ID),('--gate',p.GATE),('--lane',p.LANE)):
                self.assertEqual(command[command.index(option)+1],value)
            sandbox=Path(command[command.index('--repo-root')+1])
            self.assertNotEqual(sandbox,p.REPO_ROOT)
            self.assertEqual(kw['cwd'],sandbox)
            self.assertTrue(Path(command[command.index('--frozen-input-manifest')+1]).is_relative_to(sandbox))
            self.assertIn('--strict-source',command)
            self.assertFalse(any('generation' in v for v in command))
            self.assertEqual(kw['env']['PYTHONDONTWRITEBYTECODE'],'1')
            return REAL_RUN(command,**kw)
        with patch.object(p.subprocess,'run',side_effect=runner): self.run_pilot()
        self.assertEqual(len(observed),1)
    def test_synthetic_drivers_grid_generate_rows(self):
        r=self.run_pilot();rows=p.read_rows((self.result_dir()/'evidence/forecast_rows.csv').read_bytes())
        self.assertEqual(r['generated_row_count'],2)
        self.assertEqual({x['driver_number'] for x in rows},{'10','20'})
        self.assertEqual({x['driver_number']:x['grid_position'] for x in rows},{'10':'2','20':'1'})
    def test_explicit_weather_readiness(self):
        self.assertEqual(self.run_pilot(False)['source_readiness'],.38)
        self.assertEqual(self.run_pilot(True)['source_readiness'],.48)
    def test_synthetic_inputs_deterministic(self):
        first=self.root/'a';second=self.root/'b'
        _,a,ab=p.build_synthetic_inputs(first);_,b,bb=p.build_synthetic_inputs(second)
        self.assertEqual(a,b);self.assertEqual(ab,bb)
        for name in p.SYNTHETIC_BYTES:self.assertEqual((first/(name+'.csv')).read_bytes(),(second/(name+'.csv')).read_bytes())
    def test_rogue_latest_history_adjacent_ignored(self):
        def runner(command,**kw):
            sandbox=kw['cwd']
            for folder in ('latest/openf1_lightweight_source_closure/data','history/openf1_lightweight_source_closure/rogue'):
                d=sandbox/folder;d.mkdir(parents=True)
                (d/'drivers.csv').write_bytes(b'driver_number,full_name\n999,Rogue\n')
                (d/'starting_grid.csv').write_bytes(b'driver_number,position\n999,1\n')
                (d/'pit.csv').write_bytes(b'driver_number\n999\n')
            (sandbox/'inputs/pit.csv').write_bytes(b'driver_number\n999\n')
            return REAL_RUN(command,**kw)
        with patch.object(p.subprocess,'run',side_effect=runner):r=self.run_pilot()
        self.assertEqual(r['generated_row_count'],2);self.assertEqual(r['source_readiness'],.48)
    def test_frozen_audit_and_identity_hashes(self):
        r=self.run_pilot();root=self.result_dir()/'evidence'
        manifest=json.loads((root/'frozen_input_manifest.json').read_bytes())
        audit=json.loads((root/'producer_audit.json').read_bytes())
        self.assertEqual(audit['input_mode'],'frozen_manifest');self.assertIs(audit['broad_discovery_used'],False)
        self.assertEqual(audit['sources'],r['declared_sources'])
        self.assertEqual(audit['frozen_manifest_sha256'],hashlib.sha256((root/'frozen_input_manifest.json').read_bytes()).hexdigest())
        for e in manifest['sources']:
            self.assertTrue(e['source_id'].startswith('synthetic:'))
            self.assertEqual(e['source_sha256'],hashlib.sha256((root/e['relative_path']).read_bytes()).hexdigest())
    def test_runtime_generation_not_supplied(self):
        before=datetime.now(timezone.utc).replace(microsecond=0)
        r=self.run_pilot();after=datetime.now(timezone.utc)
        generated=datetime.fromisoformat(r['forecast_generation_utc'].replace('Z','+00:00'))
        self.assertLessEqual(before,generated);self.assertLessEqual(generated,after)
    def test_sandbox_outputs_present_then_disposed(self):
        observed=[]
        def runner(command,**kw):
            result=REAL_RUN(command,**kw);sandbox=kw['cwd'];audit=json.loads(result.stdout)
            self.assertTrue((sandbox/'latest/forecasts'/p.EVENT_ID/p.GATE/p.LANE/'forecast_rows.csv').exists())
            self.assertTrue((sandbox/'history/forecasts'/p.EVENT_ID/audit['run_id']/p.GATE/p.LANE/'forecast_rows.csv').exists())
            self.assertTrue((sandbox/'_runtime/actual_forecast_producer_v1'/audit['run_id']/'actual_forecast_producer_audit.json').exists())
            observed.append(sandbox);return result
        with patch.object(p.subprocess,'run',side_effect=runner):r=self.run_pilot()
        self.assertFalse(observed[0].exists());self.assertIs(r['producer_output_sandbox_disposed'],True)
    def test_checkout_outputs_not_written(self):
        # Real checkouts already contain production artifacts: inspect only the
        # fixed synthetic target, never assume latest/history are globally absent.
        targets = (ROOT/'latest/forecasts'/p.EVENT_ID/p.GATE/p.LANE/'forecast_rows.csv',
                   ROOT/'history/forecasts'/p.EVENT_ID)
        before = [(f.exists(), f.stat().st_mtime_ns if f.exists() else None) for f in targets]
        self.run_pilot()
        self.assertEqual(before, [(f.exists(), f.stat().st_mtime_ns if f.exists() else None) for f in targets])
    def test_all_evidence_hashes_recompute(self):
        r=self.run_pilot()
        for name,digest in r['evidence_sha256'].items():
            self.assertEqual(hashlib.sha256((self.result_dir()/'evidence'/name).read_bytes()).hexdigest(),digest)
    def test_copy_failure_no_success(self):
        original=p.persist_checked
        def persist(path,data):
            if path.name=='forecast_rows.csv':raise OSError('diagnostic persistence failed')
            return original(path,data)
        with patch.object(p,'persist_checked',side_effect=persist):
            with self.assertRaises(OSError):self.run_pilot()
        self.assertFalse((self.result_dir()/'execution_manifest.json').exists())
    def test_report_failure_no_success(self):
        original=p.persist_checked
        def persist(path,data):
            if path.name=='shadow_report.md':raise OSError('report persistence failed')
            return original(path,data)
        with patch.object(p,'persist_checked',side_effect=persist):
            with self.assertRaises(OSError):self.run_pilot()
        self.assertFalse((self.result_dir()/'execution_manifest.json').exists())
    def test_manifest_readback_failure_removes_success(self):
        original=p.persist_checked
        def persist(path,data):
            result=original(path,data)
            if path.name=='execution_manifest.json':raise OSError('readback failed')
            return result
        with patch.object(p,'persist_checked',side_effect=persist):
            with self.assertRaises(OSError):self.run_pilot()
        self.assertFalse((self.result_dir()/'execution_manifest.json').exists())
    def test_no_trust_or_activation_claim(self):
        r=self.run_pilot();self.assertEqual(r['status'],p.STATUS);self.assertIs(r['synthetic_inputs'],True)
        for key in (*p.FALSE_FLAGS,'production_forecast_generated','checkout_production_outputs_written','blind_validation_eligible'):
            self.assertIs(r[key],False)
        self.assertNotIn('verified_receipt_bindings',r)
        self.assertNotIn('engine_execution',r)
    def test_no_receipts_emitted(self):
        r=self.run_pilot();self.assertFalse(any('receipt' in n for n in r['evidence_sha256']))
    def test_workflow_manual_main_readonly(self):
        text=(ROOT/'.github/workflows/dr002-frozen-producer-shadow-pilot.yml').read_text()
        self.assertIn('on:\n  workflow_dispatch:',text)
        self.assertIn("if: github.ref == 'refs/heads/main'",text)
        self.assertIn('permissions:\n  contents: read',text)
        self.assertIn('persist-credentials: false',text)
        self.assertIn('ref: ${{ github.sha }}',text)
        self.assertEqual(text.count('python scripts/forecast_bundles/'),1)
        for forbidden in ('schedule:','workflow_call:','secrets.','git push','git commit','contents: write','openf1.org','produce_actual_forecast_rows_v1.py','orchestrate_forecast','Engine_2026-06-07_STABLE'):
            self.assertNotIn(forbidden,text)
    def test_no_discovery_or_network_in_wrapper(self):
        tree=ast.parse((ROOT/'scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py').read_text())
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertTrue(calls.isdisjoint({'glob','rglob','iterdir','walk','listdir','scandir','urlopen','post'}))
        imports={n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)}
        self.assertTrue(imports.isdisjoint({'requests','urllib','socket'}))
    def test_bad_run_id(self):
        with self.assertRaises(p.PilotError):p.run_pilot(run_id='../escape',implementation_git_sha=SHA)
    def test_bad_git_sha(self):
        with self.assertRaises(p.PilotError):p.run_pilot(run_id='a',implementation_git_sha='bad')
    def test_no_overwrite_existing_attempt(self):
        self.run_pilot()
        with self.assertRaises(FileExistsError):p.run_pilot(run_id='offline-1',implementation_git_sha=SHA)
    def test_process_failure_no_retry(self):
        with patch.object(p.subprocess,'run',side_effect=subprocess.CalledProcessError(2,'producer')) as r:
            with self.assertRaises(subprocess.CalledProcessError):self.run_pilot()
        self.assertEqual(r.call_count,1)
        self.assertFalse((self.result_dir()/'execution_manifest.json').exists())

# Tamper real subprocess outputs before the wrapper verifies them.
def changed_output(filename,change):
    def test(self):
        def runner(command,**kw):
            result=REAL_RUN(command,**kw);audit=json.loads(result.stdout)
            sandbox=kw['cwd']
            path=(sandbox/'_runtime/actual_forecast_producer_v1'/audit['run_id']/'actual_forecast_producer_audit.json') if filename=='audit' else sandbox/'latest/forecasts'/p.EVENT_ID/p.GATE/p.LANE/filename
            if filename in ('audit','forecast_metadata.json'):
                value=json.loads(path.read_bytes());change(value);path.write_text(json.dumps(value))
                if filename=='audit':result.stdout=json.dumps(value)
            else:path.write_bytes(change(path.read_bytes()))
            return result
        with patch.object(p.subprocess,'run',side_effect=runner):
            with self.assertRaises((p.PilotError,ValueError,KeyError)):self.run_pilot()
        self.assertFalse((self.result_dir()/'execution_manifest.json').exists())
    return test
for name,file,change in [
    ('audit_discovery','audit',lambda x:x.update(broad_discovery_used=True)),
    ('audit_manifest_hash','audit',lambda x:x.update(frozen_manifest_sha256='0'*64)),
    ('audit_source_identity','audit',lambda x:x['sources'][0].update(source_id='rogue')),
    ('audit_counts','audit',lambda x:x['source_counts'].update(pit=1)),
    ('metadata_trust','forecast_metadata.json',lambda x:x.update(production_authenticated=True)),
    ('metadata_scope','forecast_metadata.json',lambda x:x.update(session_id='wrong')),
    ('metadata_lane','forecast_metadata.json',lambda x:x.update(engine_lane='wrong')),
    ('rows_driver','forecast_rows.csv',lambda b:b.replace(b'Synthetic Twenty',b'Rogue')),
    ('rows_scope','forecast_rows.csv',lambda b:b.replace(p.EVENT_ID.encode(),b'wrong')),
    ('snapshot_hash','source_snapshot_manifest.csv',lambda b:b.replace(b'synthetic:dr002:drivers',b'wrong'))]:
    setattr(PilotTests,'test_reject_'+name,changed_output(file,change))

if __name__=='__main__':unittest.main()
