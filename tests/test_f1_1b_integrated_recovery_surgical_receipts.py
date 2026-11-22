"""Actual Git history, original API identity and real v16/v24/v25 writers."""
import copy
import json
import os
import subprocess
import unittest
from datetime import timedelta
from unittest.mock import patch
import test_f1_1b_integrated_recovery_reconciliation as base

peak=base.peak
custody=peak.receipt_custody()

class SurgicalReceiptTests(unittest.TestCase):
    def setUp(self):
        self.f=base.ReconciliationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.now=self.f.now
        self.git('init','-q');self.git('config','user.name','Offline fixture');self.git('config','user.email','fixture@example.invalid')
        self.save()

    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.root,check=True,capture_output=True).stdout.decode().strip()

    def save(self):
        self.git('add','--',*[p for p in ('latest','history') if (self.root/p).exists()]);self.git('commit','-qm','offline fixture')

    def reconcile(self,now=None,original=None):
        return self.f.reconcile(now=now,original=original)

    def consume(self):
        self.f.consume()
        receipt=peak.read_json(self.root/custody.CONSUMED,{})
        custody.append_receipt(self.root,receipt,True);self.save()

    def test_actual_writers_and_long_delayed_duplicate_keep_original_receipt(self):
        self.assertEqual(self.reconcile()['action'],'PROCESS')
        self.consume();before=self.f.outputs()
        r=self.reconcile(now=self.now+timedelta(days=2))
        self.assertEqual(r['action'],'NOOP_ALREADY_VERIFIED',r)
        self.assertFalse(r['prediction_locked']);self.assertEqual(before,self.f.outputs())

    def test_newer_mutable_source_cannot_replace_accepted_qualifying(self):
        self.assertEqual(self.reconcile()['action'],'PROCESS');self.consume()
        selector=self.root/'latest/latest_manifest.json'
        selector.write_text('{"session_key":11420,"overall_status":"needs_manual_review"}')
        r=self.reconcile(now=self.now+timedelta(days=1))
        self.assertEqual(r['action'],'NOOP_ALREADY_VERIFIED',r)
        self.assertEqual(r['session_key'],self.f.fixture.status['latest_state']['session_key'])

    def test_duplicate_needs_original_bytes_and_receipt_not_only_run_id(self):
        self.assertEqual(self.reconcile()['action'],'PROCESS');self.consume()
        p=self.root/custody.receipt_path(('1234','1'),True)
        raw=p.read_bytes();p.write_bytes(raw+b' ')
        self.assertEqual(self.reconcile()['action'],'HOLD')
        p.write_bytes(raw)
        output=self.root/'latest/downstream_consumers/race_predictions/consumer_input.json'
        output.write_bytes(output.read_bytes()+b' ')
        self.assertEqual(self.reconcile()['action'],'HOLD')

    def test_committed_history_mutation_and_deletion_fail_closed(self):
        self.assertEqual(self.reconcile()['action'],'PROCESS');self.consume()
        p=self.root/custody.receipt_path(('1234','1'),True)
        p.write_bytes(p.read_bytes()+b' ');self.save()
        self.assertEqual(self.reconcile()['action'],'HOLD')

    def test_first_consumption_retains_freshness_and_source_integrity(self):
        self.assertNotEqual(self.reconcile(now=self.now+timedelta(days=1))['action'],'PROCESS')
        path=self.root/'latest/combined_source_manifest.json';path.write_bytes(path.read_bytes()+b' ')
        self.assertEqual(self.reconcile()['action'],'HOLD')

    def test_source_held_original_is_visible_noop_without_consumer_writes(self):
        status=copy.deepcopy(self.f.fixture.status)
        status.update(downstream_current=False,status='hold_downstream_not_verified',dashboard_readiness_reasons=['FIA_FINAL_GRID_NOT_VERIFIED'])
        base.fixtures.write(self.root/custody.STATUS,status);self.save()
        # Deliberately use the new immutable receipt so the legacy same-run mutation guard is not bypassed.
        custody.append_receipt(self.root,status);self.save()
        before=self.f.outputs();r=self.reconcile()
        self.assertEqual(r['action'],'NOOP_NO_ELIGIBLE_CAPTURE',r)
        self.assertEqual(r['source_status'],'HOLD');self.assertEqual(r['operational_status'],'OPERATIONAL_PASS')
        self.assertEqual(before,self.f.outputs())

    def test_original_api_identity_and_failures_are_not_demoted_to_noop(self):
        for field,value in [('run_attempt',2),('head_sha','b'*40),('conclusion','failure'),('head_branch','other')]:
            self.assertEqual(self.reconcile(original=dict(self.f.original,**{field:value}))['action'],'HOLD')
        import urllib.error
        for code in (401,403,429,503):
            with patch.object(peak,'fetch_original_run',side_effect=urllib.error.HTTPError('fixture',code,'secret',{},None)):
                r=peak.reconcile_bridge_input(self.root,self.now)
                self.assertEqual(r['operational_status'],'OPERATIONAL_FAIL');self.assertNotIn('secret',json.dumps(r))

    def test_immutable_append_is_idempotent_and_collision_protected(self):
        s=self.f.fixture.status;custody.append_receipt(self.root,s);custody.append_receipt(self.root,s)
        with self.assertRaisesRegex(ValueError,'COLLISION'):
            custody.append_receipt(self.root,dict(s,downstream_current=False))
