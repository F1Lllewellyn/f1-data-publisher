"""Synthetic authenticated archive tests; no network or source promotion."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from datetime import datetime, timezone

import test_f1_1b_integrated_recovery_artifact as fixture


class EliteTrustTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.tmp)
        self.profile = self.root/'inputs/pre_race'
        self.profile.mkdir(parents=True)
        self.now = datetime(2026,10,30,2,tzinfo=timezone.utc)
        self.expected = dict(event_id='SYNTHETIC_EVENT',meeting_key=900000,session_key=900001)
        self.origin = fixture.verified_run_identity()
        self.doc = dict(schema='elite-source-custody-v1', profile='pre_race',capture_origin=self.origin,**self.expected,sources=[])
        self.members = {'high_frequency_extraction_manifest.csv':b'rows\n2\n',
                        'extraction_checkpoint_summary.json':b'{"feature_rows":2,"selected_session_count":1}'}
        for endpoint in ('drivers','laps','position','weather'):
            row=dict(meeting_key=900000,session_key=900001,date='2026-10-29T23:30:00Z')
            if endpoint != 'weather':row['driver_number']=1
            raw=json.dumps([row]).encode();path='raw/'+endpoint+'.json';self.members[path]=raw
            self.doc['sources'].append(dict(path=path,endpoint=endpoint,sha256=hashlib.sha256(raw).hexdigest(),
                observed_at_utc='2026-10-30T00:55:00Z',http_status=200,rows=1,
                request_url='https://api.openf1.org/v1/'+endpoint+'?session_key=900001'))
        self.row=dict(found=True,verified=True,event_session_provenance_verified=True,artifact_id='101',
            artifact_name=fixture.artifact()['name'],workflow_run_id='5001',workflow_run_attempt='1',
            workflow_run_head_sha='a'*40,workflow_path=self.origin['path'])
        self.enterContext(patch.dict(os.environ,GITHUB_REPOSITORY=fixture.REPO,GITHUB_TOKEN=fixture.TOKEN))
        self.enterContext(patch.object(fixture.CONSUMER,'load_verifier',return_value=fixture.MODULE))
        self.remote=self.enterContext(patch.object(fixture.MODULE,'gh_get_json',side_effect=lambda url,token:self.meta if '/artifacts/' in url else fixture.workflow_run_response()))
        self.pack()

    def pack(self):
        self.members['source_custody.json']=json.dumps(self.doc).encode()
        archive=self.root/'downloads/pre_race_101.zip';archive.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name,raw in self.members.items():
                z.writestr(name,raw);path=self.profile/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        self.meta=fixture.artifact(size=archive.stat().st_size,digest='sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest())

    def verify(self):
        return fixture.CONSUMER.verify_profile_custody('pre_race',self.profile,self.row,self.expected,self.now)

    def test_authenticated_current_context_preserves_original_run_and_clocks(self):
        result=self.verify()
        self.assertTrue(result['context_verified']);self.assertFalse(result['forecast_eligible'])
        self.assertEqual(result['capture_origin'],self.origin)
        self.assertEqual(len(result['source_hashes']),4)
        self.assertEqual(set(result['source_availability'].values()),{'2026-10-30T00:55:00Z'})
        summary=fixture.CONSUMER.profile_summary('pre_race',self.profile,self.row,self.expected,self.now)
        self.assertEqual(summary['status'],'PASS');self.assertFalse(summary['forecast_eligible'])

    def test_found_rows_and_verified_flags_alone_cannot_bypass_authentication(self):
        self.remote.side_effect=fixture.MODULE.ArtifactHold('https://private.example/?token=secret')
        summary=fixture.CONSUMER.profile_summary('pre_race',self.profile,self.row,self.expected,self.now)
        self.assertEqual(summary['status'],'HOLD');self.assertEqual(summary['feature_rows'],0)
        self.assertNotIn('secret',json.dumps(summary))

    def test_quarantine_is_never_read_as_an_input(self):
        self.row['quarantined_to']='quarantine/pre_race'
        with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_SOURCE_PROVENANCE_UNVERIFIED'):self.verify()
        self.remote.assert_not_called()

    def test_wrong_session_profile_or_original_attempt_holds(self):
        for key,value in [('session_key',900002),('profile','post_race'),('capture_origin',dict(self.origin,run_attempt=2))]:
            original=copy.deepcopy(self.doc)
            with self.subTest(key=key):
                self.doc[key]=value;self.pack()
                with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_EVENT_SESSION_OR_ORIGIN'):self.verify()
            self.doc=original

    def test_wrong_cache_run_or_missing_authenticated_digest_holds(self):
        self.row['workflow_run_attempt']='2'
        with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_ORIGINAL_RUN_MISMATCH'):self.verify()
        self.row['workflow_run_attempt']='1';self.meta.pop('digest')
        with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_AUTHENTICATED_ARCHIVE_DIGEST'):self.verify()

    def test_missing_future_or_post_artifact_observation_cannot_be_inferred(self):
        for value in (None,'2026-10-30T01:02:00Z','2026-10-29T22:00:00Z'):
            with self.subTest(value=value):
                self.doc['sources'][0]['observed_at_utc']=value;self.pack()
                with self.assertRaises((RuntimeError,fixture.MODULE.ArtifactHold)):self.verify()

    def test_required_coverage_cannot_be_demoted_by_manifest(self):
        self.doc['sources']=self.doc['sources'][:3];self.pack()
        with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_REQUIRED_SOURCE_COVERAGE'):self.verify()

    def test_rehashed_wrong_driver_or_source_identity_still_holds(self):
        for key,value in [('session_key',900002),('driver_number',99)]:
            with self.subTest(key=key):
                source=self.doc['sources'][1];rows=json.loads(self.members[source['path']]);rows[0][key]=value
                self.members[source['path']]=json.dumps(rows).encode();source['sha256']=hashlib.sha256(self.members[source['path']]).hexdigest();self.pack()
                with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_SOURCE_ROW_IDENTITY|HOLD_ELITE_DRIVER_MEMBERSHIP'):self.verify()
                rows[0].update(session_key=900001,driver_number=1);self.members[source['path']]=json.dumps(rows).encode()

    def test_modified_extraction_and_extra_green_checkpoint_are_rejected(self):
        path=self.profile/'extraction_checkpoint_summary.json';original=path.read_bytes();path.write_text('{"feature_rows":999}')
        with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_EXTRACTED_BYTES'):self.verify()
        path.write_bytes(original);(self.profile/'extra.csv').write_text('rows\n999\n')
        with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_UNBOUND_EXTRACTED_FILES'):self.verify()

    def test_expired_metadata_and_corrupt_cached_archive_hold(self):
        self.meta['expired']=True
        with self.assertRaises(fixture.MODULE.ArtifactHold):self.verify()
        self.meta['expired']=False;path=self.root/'downloads/pre_race_101.zip';raw=path.read_bytes();path.write_bytes(bytes([raw[0]^1])+raw[1:])
        with self.assertRaisesRegex(RuntimeError,'HOLD_ELITE_AUTHENTICATED_ARCHIVE_DIGEST'):self.verify()


if __name__=='__main__':unittest.main()
