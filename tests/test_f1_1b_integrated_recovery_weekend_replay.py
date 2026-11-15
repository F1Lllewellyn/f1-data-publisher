"""Offline synthetic weekend through real processor, XLSX, dashboard and consumers.

Synthetic sessions are never scientific evidence. No provider request, production
publication, protected-model invocation or genuine prospective lock occurs here.
"""
import contextlib
import copy
from datetime import timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

import test_sp2026_integrated_recovery_guard_v1 as fixtures
import test_f1_producer_lock_custody_gate as gate_tests

ROOT = Path(__file__).resolve().parents[1]
processor = fixtures.load_module('weekend_processor', 'scripts/session_data_processor/session_data_processor_loop_v1.py')
workbook = fixtures.load_module('weekend_workbook', 'scripts/workbook_kpi_refresh/apply_workbook_kpi_refresh_v1.py')
dashboard = fixtures.dashboard_mod
peak = fixtures.peak_mod
contract = fixtures.load_module('weekend_contract', 'scripts/session_data_processor/f1_1b_output_contract_v16.py')
downstream = fixtures.load_module('weekend_downstream', 'scripts/session_data_processor/f1_1b_downstream_consumer_handoff_v24.py')
context = fixtures.load_module('weekend_context', 'scripts/session_data_processor/f1_1b_consumer_context_publisher_v25.py')


class WeekendPipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        self.sessions = gate_tests.catalog()
        (self.root/'Engine_2026-06-07_STABLE').write_text('protected immutable sentinel')
        self.protected_sha = hashlib.sha256((self.root/'Engine_2026-06-07_STABLE').read_bytes()).hexdigest()
        for relative in ['configs/session_data_processor/session_data_processor_policy_v1.json',
                         'scripts/session_data_processor/source_readiness_aggregation_v2.py']:
            path=self.root/relative; path.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT/relative, path)
        for name, value in (('ROOT',self.root),('RUNTIME',self.root/'_runtime/session_data_processor'),
                            ('POLICY_PATH',self.root/'configs/session_data_processor/session_data_processor_policy_v1.json')):
            self.enterContext(patch.object(processor,name,value))
        self.output = io.StringIO()

    def payload(self, session, endpoint):
        if endpoint in ('pit','intervals'):
            return []
        return [dict(session_key=session['session_key'], meeting_key=session['meeting_key'],
                     driver_number=i, full_name=f'SYNTHETIC driver {i}', team_name='SYNTHETIC team',
                     date=session['date_start'], lap_number=1, lap_duration=90.0,
                     position=i, duration=90.0, air_temperature=19.0, stint_number=1)
                for i in range(1,23)]

    def capture(self, index, mutate=None):
        session=self.sessions[index]
        now=processor.parse_time(session['date_end'])+timedelta(minutes=35)
        def response(url, **kwargs):
            endpoint=urlparse(url).path.rsplit('/',1)[1]
            rows=self.payload(session, endpoint)
            if mutate: rows=mutate(endpoint, rows)
            return rows, dict(ok=True,status_code=200,bytes=len(json.dumps(rows)))
        with patch.object(processor,'utc_now',return_value=now), \
             patch.object(processor,'fetch_sessions',return_value=(self.sessions,dict(ok=True,status_code=200))), \
             patch.object(processor,'http_json',side_effect=response), \
             patch.object(sys,'argv',['processor','--mode','run_now']), contextlib.redirect_stdout(self.output):
            rc=processor.main()
        self.assertEqual(rc,0)
        self.now=now
        return json.loads((processor.RUNTIME/'session_processor_result.json').read_text())

    def control_room(self):
        with patch.object(workbook,'utc_datetime',return_value=self.now), \
             patch.object(sys,'argv',['workbook','--repo-root',str(self.root)]), contextlib.redirect_stdout(self.output):
            rc=workbook.main()
        state=dashboard.discover_state(self.root,reference_time=self.now)
        fixtures.write(self.root/'latest/readiness_dashboards/combined_readiness_dashboard.json',state)
        return rc,state

    def handoff(self, state):
        paths=['latest/latest_manifest.json','latest/data_readiness.json','latest/combined_source_manifest.json',
               'latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json',
               'latest/readiness_dashboards/combined_readiness_dashboard.json']
        status=dict(operation='full_run_chain',created_utc=self.now.isoformat(),github_run_id='1234',
            github_run_attempt='1',workflow_head_sha='a'*40,downstream_current=state['downstream_eligible'],
            commit_allowed=True,failed_steps=[],latest_state=dict(event_id=state['event_id'],session_key=state['session_key']),
            handoff_fingerprints=peak.byte_fingerprints(self.root,paths+list(state['consumed_fingerprints'])),
            steps=[dict(label=s,ok=True,started_utc=(self.now-timedelta(seconds=1)).isoformat()) for s in
                ('session_data_processor_run_now','workbook_kpi_refresh_apply','dashboard_readiness_publish')])
        fixtures.write(self.root/'latest/peak_elite/orchestrator_status.json',status)
        marker=self.root/'_runtime/1b_output_contract/start.marker'; marker.parent.mkdir(parents=True,exist_ok=True); marker.touch(); os.utime(marker,(1,1))
        with patch.object(contract,'utc_now',return_value=self.now), \
             patch.object(downstream,'utc_now_iso',return_value=self.now.isoformat()), \
             patch.object(context,'utc_now_iso',return_value=self.now.isoformat()), contextlib.redirect_stdout(self.output):
            contract.run(self.root); downstream.run(self.root); context.run(self.root)
        return peak.verify_bridge_output(self.root,reference_time=self.now)

    def assert_scientific_hold(self, gate='post_qualifying'):
        mod=gate_tests.gate
        with patch.object(mod,'ROOT',self.root),patch.object(mod,'RUNTIME',self.root/'_runtime/gate'), \
             patch.object(mod,'POLICY_PATH',self.root/'missing_policy.json'), \
             patch.object(sys,'argv',['gate','--mode','force_validation','--gate',gate]), \
             patch.object(mod,'utc_now',return_value=self.now),patch.object(mod,'run_command') as run, \
             contextlib.redirect_stdout(self.output):
            rc=mod.main()
        run.assert_not_called(); self.assertEqual(rc,2)
        r=json.loads((self.root/'_runtime/gate/orchestrator_result.json').read_text())
        self.assertFalse(r['prediction_locked']); self.assertFalse(r['stable_engine_executed'])
        self.assertFalse((self.root/'latest/forecast_bundles').exists())
        self.assertEqual(hashlib.sha256((self.root/'Engine_2026-06-07_STABLE').read_bytes()).hexdigest(),self.protected_sha)

    def test_all_five_sessions_real_workbook_and_consumers_stop_at_correct_scientific_hold(self):
        for i,session in enumerate(self.sessions):
            with self.subTest(session=session['session_name']):
                capture=self.capture(i); rc,state=self.control_room()
                self.assertEqual(state['session_key'],session['session_key'])
                if i<4:
                    self.assertEqual(rc,0,self.output.getvalue())
                    self.assertTrue(state['downstream_eligible'],state['readiness_reasons'])
                    receipt=self.handoff(state)
                    self.assertEqual(receipt['status'],'VERIFIED_CONTEXT_ONLY',receipt)
                    manifest=json.loads((self.root/'latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json').read_text())
                    self.assertTrue(any(o['path'].endswith('.xlsx') for o in manifest['outputs']))
                else:
                    self.assertFalse(state['downstream_eligible'])
                    self.assertEqual(capture['overall_status'],'needs_manual_review')
                self.assert_scientific_hold('race_result' if i==4 else 'post_qualifying')

    def test_new_session_failure_cannot_keep_previous_green_workbook_ready(self):
        self.capture(2); self.assertTrue(self.control_room()[1]['downstream_eligible'])
        self.capture(3, lambda endpoint,rows: [] if endpoint=='weather' else rows)
        self.assertFalse(self.control_room()[1]['downstream_eligible'])
        self.assert_scientific_hold()

    def test_wrong_event_source_and_partial_capture_fail_closed(self):
        def wrong(endpoint,rows):
            if endpoint=='drivers': rows[0]['meeting_key']=123
            return rows
        self.capture(0,wrong)
        self.assertFalse(self.control_room()[1]['downstream_eligible'])
        self.assert_scientific_hold()

    def test_restart_history_collision_does_not_overwrite_original_capture(self):
        self.capture(0)
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in (self.root/'history').rglob('*') if p.is_file()}
        with self.assertRaises(FileExistsError): self.capture(0)
        self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in (self.root/'history').rglob('*') if p.is_file()})
