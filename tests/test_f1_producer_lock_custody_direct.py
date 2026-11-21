"""Direct caller adversarial tests. Synthetic candidates are not engine evidence."""
import contextlib
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    path=ROOT/'scripts/forecast_bundles'/name
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

guard=module('validate_forecast_chain_readiness_v1.py')
locker=module('create_forecast_bundles_v1.py')
writer=module('write_gate_forecast_rows_v1.py')


class DirectCustodyTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.event='SYNTHETIC_ONLY';self.gate='post_qualifying';self.lane='stable_baseline';self.now='2026-11-21T06:00:00Z'
        self.source=self.root/'latest/forecasts'/self.event/self.gate/self.lane/'forecast_rows.csv'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('event_id,gate,engine_lane,driver_number,forecast_timestamp_utc,predicted_race_finish_position\nSYNTHETIC_ONLY,post_qualifying,stable_baseline,1,2026-11-21T05:31:00Z,1\n')
        inp=self.root/'retained.json';inp.write_bytes(b'[{"synthetic":true}]')
        self.doc=dict(schema='f1-forecast-execution-candidate-v1',event_id=self.event,gate=self.gate,engine_lane=self.lane,
            meeting_key=900000,session_key=900005,allowed_session_keys=[900004],driver_numbers=[1],
            capture_origin=dict(repository='synthetic/tests',head_sha='a'*40,run_id='1',run_attempt='1'),
            evidence_cutoff_utc='2026-11-21T05:25:00Z',forecast_generation_utc='2026-11-21T05:31:00Z',
            forecast_deadline_utc='2026-11-22T03:50:00Z',outcome_boundary_utc='2026-11-22T04:00:00Z',
            inputs=[dict(path='retained.json',source_id='synthetic',meeting_key=900000,session_key=900004,
                sha256=guard.digest(inp.read_bytes()),observed_at_utc='2026-11-21T05:20:00Z')],
            invocation=dict(execution_id='synthetic_only',engine_implementation='TEST_FIXTURE_NOT_A_MODEL',engine_code_sha256='b'*64,
                started_utc='2026-11-21T05:26:00Z',completed_utc='2026-11-21T05:30:00Z'))
        self.save()
        (self.root/'Engine_2026-06-07_STABLE').write_bytes(b'protected sentinel')

    def save(self):
        self.doc['forecast_sha256']=guard.digest(self.source.read_bytes())
        self.doc['invocation']['output_sha256']=self.doc['forecast_sha256']
        self.doc['invocation']['input_manifest_sha256']=guard.digest(json.dumps(self.doc['inputs'],sort_keys=True,separators=(',',':')).encode())
        self.source.with_name('forecast_execution_manifest.json').write_text(json.dumps(self.doc))

    def inspect(self):return guard.inspect_candidate(self.root,self.source,self.event,self.gate,self.lane,self.now)
    def bytes(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '_runtime' not in p.parts}

    def test_candidate_byte_checks_are_explicitly_not_authentication(self):
        result=self.inspect();self.assertFalse(result['production_authenticated']);self.assertFalse(result['forecast_eligible'])
        before=self.bytes()
        with self.assertRaisesRegex(guard.ScientificHold,'HOLD_STABLE_ENGINE_NOT_EXECUTED'):
            guard.verify_candidate(self.root,self.source,self.event,self.gate,self.lane,self.now)
        self.assertEqual(self.bytes(),before)

    def test_direct_locker_cannot_relock_existing_or_self_attested_candidate(self):
        self.doc.update(production_authenticated=True,stable_engine_executed=True);self.save()
        prior=self.root/'history/forecast_bundles/original/forecast.csv';prior.parent.mkdir(parents=True);prior.write_bytes(b'original prediction')
        before=self.bytes()
        for repeat in range(2):
            with self.assertRaisesRegex(RuntimeError,'HOLD_STABLE_ENGINE_NOT_EXECUTED'):
                locker.create_bundle(self.root,self.event,'2026','','Synthetic',self.gate,self.lane,self.root,True)
        self.assertEqual(self.bytes(),before)

    def test_all_lanes_and_post_outcome_gates_fail_closed(self):
        for lane in guard.LANES:
            with self.subTest(lane=lane),self.assertRaises(guard.ScientificHold):guard.require_forecast_authority(self.event,self.gate,lane)
        for gate in ('race_result','post_event'):
            with self.assertRaisesRegex(guard.ScientificHold,'HOLD_POST_OUTCOME_NOT_PROSPECTIVE'):guard.require_forecast_authority(self.event,gate,self.lane)

    def test_missing_observation_not_replaced_by_ingestion_or_present_time(self):
        for value in (None,'','2026-11-21T05:20:00'):
            with self.subTest(value=value):
                self.doc['inputs'][0]['observed_at_utc']=value;self.save()
                with self.assertRaisesRegex(guard.ScientificHold,'HOLD_SOURCE_AVAILABILITY_CLOCK_NOT_RETAINED'):self.inspect()

    def test_late_source_and_late_execution_are_ineligible(self):
        self.doc['inputs'][0]['observed_at_utc']='2026-11-21T05:26:00Z';self.save()
        with self.assertRaisesRegex(guard.ScientificHold,'HOLD_SOURCE_AVAILABLE_AFTER_CUTOFF'):self.inspect()
        self.doc['inputs'][0]['observed_at_utc']='2026-11-21T05:20:00Z';self.save()
        self.now='2026-11-22T04:00:00Z'
        with self.assertRaisesRegex(guard.ScientificHold,'HOLD_FORECAST_TEMPORAL_ELIGIBILITY'):self.inspect()

    def test_changed_original_input_and_output_fail(self):
        raw=(self.root/'retained.json').read_bytes();(self.root/'retained.json').write_bytes(raw+b' ')
        with self.assertRaisesRegex(guard.ScientificHold,'HOLD_FORECAST_INPUT_BYTES'):self.inspect()
        (self.root/'retained.json').write_bytes(raw);self.source.write_bytes(self.source.read_bytes()+b' ')
        with self.assertRaisesRegex(guard.ScientificHold,'HOLD_FORECAST_OUTPUT_BYTES'):self.inspect()

    def test_rehashed_wrong_event_driver_or_time_still_fails(self):
        original=self.source.read_text()
        for old,new in [('SYNTHETIC_ONLY','ANOTHER_EVENT'),(',1,2026',',99,2026'),('05:31:00Z','05:32:00Z')]:
            with self.subTest(new=new):
                self.source.write_text(original.replace(old,new));self.save()
                with self.assertRaises(guard.ScientificHold):self.inspect()
        self.source.write_text(original);self.save()

    def test_normalizer_does_not_fabricate_generation_time_or_relabel_event(self):
        with self.assertRaisesRegex(RuntimeError,'HOLD_SOURCE_AVAILABILITY_CLOCK_NOT_RETAINED'):
            writer.normalize_rows([{'driver_number':'1'}],self.event,self.gate,self.lane)
        source=list(csv.DictReader(io.StringIO(self.source.read_text())))[0]
        result=writer.normalize_rows([source],self.event,self.gate,self.lane)[0]
        self.assertEqual(result['forecast_timestamp_utc'],source['forecast_timestamp_utc'])
        self.assertEqual(result['forecast_lock_utc'],'');self.assertIn('no separate protected',result['notes'])
        source['event_id']='OTHER'
        with self.assertRaisesRegex(RuntimeError,'HOLD_FORECAST_ROW_IDENTITY'):writer.normalize_rows([source],self.event,self.gate,self.lane)

    def test_immutable_storage_duplicate_conflict_and_partial_restart(self):
        path=self.root/'history/test';files={'source.json':b'original','receipt.json':b'original clock'}
        self.assertTrue(guard.immutable_directory(path,files));mtime=(path/'source.json').stat().st_mtime_ns
        self.assertFalse(guard.immutable_directory(path,files));self.assertEqual((path/'source.json').stat().st_mtime_ns,mtime)
        before=self.bytes()
        with self.assertRaisesRegex(guard.ScientificHold,'HOLD_IMMUTABLE_FORECAST_COLLISION'):guard.immutable_directory(path,dict(files,**{'source.json':b'changed'}))
        self.assertEqual(self.bytes(),before)
        partial=self.root/'history/partial';partial.mkdir();(partial/'source.json').write_bytes(b'original')
        before=self.bytes()
        with self.assertRaisesRegex(guard.ScientificHold,'HOLD_IMMUTABLE_FORECAST_COLLISION'):guard.immutable_directory(partial,files)
        self.assertEqual(self.bytes(),before)

    def test_isolated_candidate_preservation_never_claims_scientific_lock(self):
        # Test seam only: bypass authority in this process to exercise unreachable
        # storage mechanics. No model is invoked or claimed authenticated.
        cg=locker.custody_guard
        with patch.object(cg,'require_forecast_authority'),patch.object(locker,'utcnow',return_value=self.now):
            result=locker.create_bundle(self.root,self.event,'2026','','Synthetic',self.gate,self.lane,self.root,True)
            before=self.bytes();mtime={p:p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()}
            again=locker.create_bundle(self.root,self.event,'2026','','Synthetic',self.gate,self.lane,self.root,True)
            self.assertEqual(again,result);self.assertEqual(before,self.bytes())
            self.assertTrue(all(p.stat().st_mtime_ns==t for p,t in mtime.items()))
            manifest=json.loads((Path(result['history_dir'])/'bundle_lock_manifest.json').read_text())
            self.assertFalse(manifest['blind_validation_eligible']);self.assertFalse(manifest['prediction_locked']);self.assertIsNone(manifest['forecast_lock_utc'])
            self.assertEqual((Path(result['history_dir'])/'forecast_rows.csv').read_bytes(),self.source.read_bytes())
            (Path(result['history_dir'])/'forecast_rows.csv').write_bytes(b'collision');before=self.bytes()
            with self.assertRaisesRegex(RuntimeError,'HOLD_IMMUTABLE_FORECAST_COLLISION'):
                locker.create_bundle(self.root,self.event,'2026','','Synthetic',self.gate,self.lane,self.root,True)
            self.assertEqual(before,self.bytes())

    def test_direct_cli_and_actual_workflow_shells_hold_before_any_forecast_write(self):
        before=self.bytes()
        for name in ('f1-actual-forecast-producer-v1','f1-forecast-bundle-locker-v1','f1-forecast-gate-source-writer-v1'):
            with self.subTest(workflow=name):
                workflow=yaml.safe_load((ROOT/'.github/workflows'/f'{name}.yml').read_text())
                self.assertEqual(workflow['permissions']['contents'],'read')
                steps=next(iter(workflow['jobs'].values()))['steps']
                shell=next(s['run'] for s in steps if s.get('name','').startswith(('Verify scientific execution','Run forecast bundle locker','Run forecast gate source writer')))
                for relative in ('scripts/forecast_bundles/validate_forecast_chain_readiness_v1.py','scripts/forecast_bundles/create_forecast_bundles_v1.py','scripts/forecast_bundles/write_gate_forecast_rows_v1.py'):
                    path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,path)
                env=dict(os.environ,EVENT_ID=self.event,GATE=self.gate,LANE=self.lane,RACE_NAME='Synthetic',ALLOW_STRUCTURAL_PLACEHOLDERS='true',COMMIT_OUTPUTS='true',F1_APPROVED_ENGINE='true',DR002_ACTIVATED='true')
                result=subprocess.run(['bash','-e','-c',shell],cwd=self.root,env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,2,result.stdout+result.stderr);self.assertIn('HOLD_STABLE_ENGINE_NOT_EXECUTED',result.stdout)
                self.assertNotIn('unrecognized arguments',result.stderr)
        self.assertEqual(before,{p:v for p,v in self.bytes().items() if not p.startswith('scripts/')})

    def test_path_traversal_and_symlink_cannot_reach_original_assets(self):
        for value in ('../event','event/name','$(echo leak)'):
            with self.assertRaises(guard.ScientificHold):guard.require_forecast_authority(value,self.gate,self.lane)
        path=self.root/'link';path.symlink_to(self.source)
        with self.assertRaises(guard.ScientificHold):guard.immutable_directory(path,{'x':b'y'})


if __name__=='__main__':unittest.main()
