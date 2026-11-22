"""Source/session admission, independent of workflow green or diagnostic writes."""
import copy
import unittest
from datetime import timedelta
from unittest.mock import patch
import test_f1_1b_integrated_recovery_peak_handoff as fixtures

guard = fixtures.fixtures.load_module('surgical_gate', 'scripts/ops/f1_canonical_chain_guard_v27.py')

class SurgicalAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.PeakHandoffTests(); self.f.setUp()
        self.addCleanup(self.f.doCleanups); self.f.observe()
        self.session = dict(session_key=self.f.status['latest_state']['session_key'], meeting_key=1300,
            date_start=(self.f.now-timedelta(hours=2)).isoformat(),
            date_end=(self.f.now-timedelta(hours=1)).isoformat(), session_name='Qualifying')

    def gate(self, sessions=None, meta=None):
        return guard.scheduled_admission(self.f.root, self.f.now,
            (sessions if sessions is not None else [self.session], meta or {'ok': True}))

    def test_completed_source_noop_then_new_provider_session_runs(self):
        self.assertEqual(self.gate()['action'], 'NOOP_ALREADY_PROCESSED')
        newer = dict(self.session, session_key=999999, date_end=self.f.now.isoformat())
        self.assertEqual(self.gate([self.session, newer])['action'], 'RUN')

    def test_diagnostic_hold_is_not_consumer_authority(self):
        auth = fixtures.peak_mod.execution_authority('full_run_chain', [], [], [], False)
        self.assertTrue(auth['diagnostic_commit_allowed'])
        self.assertFalse(auth['consumer_eligible']); self.assertFalse(auth['scientific_eligible'])
        self.f.observe(dict(self.f.status, downstream_current=False))
        self.assertEqual(self.gate()['action'], 'HOLD_NO_NEW_ELIGIBLE_SOURCE')

    def test_new_source_receipt_runs_but_unannounced_byte_change_fails(self):
        p = self.f.root/'latest/combined_source_manifest.json'
        p.write_bytes(p.read_bytes()+b' ')
        self.assertEqual(self.gate()['operational_status'], 'OPERATIONAL_FAIL')
        selector = self.f.root/'latest/latest_manifest.json'
        selector.write_bytes(selector.read_bytes()+b' ')
        self.assertEqual(self.gate()['action'], 'RUN')  # runtime verifier must authenticate the new receipt

    def test_missing_ambiguous_and_provider_failure_do_not_run(self):
        self.assertEqual(self.gate([])['action'], 'HOLD_PROVIDER')
        self.assertEqual(self.gate([self.session, self.session])['action'], 'HOLD_NO_NEW_ELIGIBLE_SOURCE')
        for code in (401,403,429,503):
            self.assertEqual(self.gate(meta={'ok':False,'status_code':code})['operational_status'], 'OPERATIONAL_FAIL')

    def test_implementation_failure_cannot_be_context_verified(self):
        for hard,soft in (([{}],[]),([],[{}])):
            r=fixtures.peak_mod.execution_authority('full_run_chain',[],hard,soft,True)
            self.assertEqual(r['operational_execution'],'OPERATIONAL_FAIL')
            self.assertFalse(r['consumer_eligible'])

    def test_actual_workflow_obeys_gate_and_keeps_provider_serialization(self):
        import yaml
        w=yaml.safe_load((fixtures.ROOT/'.github/workflows/f1-peak-elite-control-room-one-click-v1.yml').read_text())
        steps=w['jobs']['peak-elite-control-room']['steps']
        for s in steps:
            if s['name'] in ('Run peak-elite orchestrator','Verify workbook/session persistence handoff') or 'git commit' in s.get('run',''):
                self.assertIn("steps.admission.outputs.action == 'RUN'",s['if'])
        self.assertEqual(w['concurrency']['group'],'f1-main-write-serialization')
