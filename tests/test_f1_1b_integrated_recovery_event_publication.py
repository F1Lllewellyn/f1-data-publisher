"""Event collector -> original bytes -> isolated ordinary Git publication."""
import contextlib
import datetime as dt
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_openf1_normal_incremental_collection_budget_v1 import m, Router, FakeClock, session
from test_f1_source_closure_publish_guard_v1 import guard, GitFixture, git


class EventPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.git = GitFixture(self.tmp.name)
        self.now = dt.datetime(2026, 10, 26, 12, tzinfo=dt.timezone.utc)
        self.origin = dict(repository='test/repo', head_sha='a' * 40, run_id='123', run_attempt='1')

    def collect(self, name='candidate', now=None):
        root = self.git.clone(name)
        clock = FakeClock(); router = Router([session()])
        argv = ['collector', '--output-root', str(root), '--meeting-key', '1297', '--expected-session-key', '11396',
                '--github-repository', 'test/repo', '--github-sha', 'a' * 40, '--github-run-id', '123', '--github-run-attempt', '1']
        with patch.object(m.requests, 'get', side_effect=router), patch.object(m, 'utc_now', return_value=now or self.now), patch.object(m.time, 'monotonic', side_effect=clock.monotonic), patch.object(m.time, 'sleep', side_effect=clock.sleep), patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(), 0)
        return root, router

    def publish(self, root, **kwargs):
        return guard.run_guard(repo_root=root, remote='origin', branch='main', expected_season=2026,
                               expected_completed_only=True, github_run_id='123', artifact_uploaded_for_run='123',
                               meeting_key='1297', expected_session_key='11396', expected_origin=self.origin,
                               clock=lambda:self.now + dt.timedelta(hours=4), **kwargs)

    def test_real_collector_publication_committed_byte_readback_and_exact_duplicate(self):
        root, _ = self.collect()
        season = self.git.remote_bytes('latest/openf1_lightweight_source_closure/latest_manifest.json')
        result = self.publish(root)
        self.assertEqual(result['status'], 'PUBLISHED_LATEST_AND_HISTORY', result)
        latest = root / 'latest/openf1_event_source_closure/1297'
        for file in latest.rglob('*'):
            if file.is_file() and file.suffix != '.zip':
                self.assertEqual(self.git.remote_bytes(file.relative_to(root).as_posix()), file.read_bytes())
        self.assertEqual(self.git.remote_bytes('latest/openf1_lightweight_source_closure/latest_manifest.json'), season)
        self.assertEqual(self.publish(root)['status'], 'NO_CHANGES')

    def test_incremental_reuse_retains_original_bytes_and_observation_times(self):
        root, _ = self.collect(); self.assertTrue(self.publish(root)['status'].startswith('PUBLISHED'))
        second, router = self.collect('second', self.now + dt.timedelta(hours=1))
        self.assertEqual([ep for ep, _, _ in router.calls], ['sessions'])
        self.assertEqual(self.publish(second)['status'], 'PUBLISHED_LATEST_AND_HISTORY')
        records=json.loads((second/'latest/openf1_event_source_closure/1297/raw_evidence.json').read_text())
        self.assertEqual({r['response_observed_utc'] for r in records if r['endpoint']!='sessions'}, {m._format_utc(self.now)})

    def test_corrupt_source_bytes_cannot_publish(self):
        root,_=self.collect(); raw=next((root/'latest/openf1_event_source_closure/1297/raw').glob('*.json')); raw.write_bytes(b'[]')
        self.assertEqual(self.publish(root)['reason'], 'event_raw_bytes_mismatch')

    def test_wrong_expected_session_and_original_run_fail_closed(self):
        root,_=self.collect(); self.origin['run_attempt']='2'
        self.assertEqual(self.publish(root)['reason'], 'event_origin_mismatch')
        with self.assertRaisesRegex(guard.PublicationHold, 'event_expected_session_mismatch'):
            guard.validate_candidate(root, expected_season=2026, expected_completed_only=True, now=self.now, meeting_key='1297', expected_session_key='1')

    def test_stale_candidate_preserves_newer_remote_and_push_race_holds(self):
        old,_=self.collect('old'); new,_=self.collect('new',self.now+dt.timedelta(hours=1))
        self.assertTrue(self.publish(new)['status'].startswith('PUBLISHED'))
        self.assertEqual(self.publish(old)['status'], 'PUBLISHED_HISTORY_ONLY')
        newer,_=self.collect('newer',self.now+dt.timedelta(hours=2))
        def race():
            other=self.git.clone('racer'); (other/'unrelated.txt').write_text('concurrent\n'); git(other,'add','unrelated.txt');git(other,'commit','-m','race');git(other,'push')
        result=self.publish(newer,before_push=race)
        self.assertEqual(result['reason'],'push_rejected_after_freshness_decision')
        self.assertEqual(result['publication']['push_attempts'],1)

    def test_forged_observation_clock_cannot_be_rehashed_into_valid_custody(self):
        root,_=self.collect(); latest=root/'latest/openf1_event_source_closure/1297'
        records=json.loads((latest/'raw_evidence.json').read_text()); records[0]['response_observed_utc']='2099-01-01T00:00:00Z'
        raw=json.dumps(records).encode(); (latest/'raw_evidence.json').write_bytes(raw)
        manifest=json.loads((latest/'latest_manifest.json').read_text()); manifest['raw_evidence_sha256']=hashlib.sha256(raw).hexdigest()
        sessions=guard._validate_target_sessions(latest/'data/target_sessions.csv',manifest=manifest,generated=self.now,completed_only=True)
        with self.assertRaisesRegex(guard.PublicationHold,'event_raw_clock_after_generation'):
            guard._validate_event_evidence(latest,manifest,sessions,self.now,'11396')

    def test_missing_projected_rows_are_not_declared_complete(self):
        root,_=self.collect(); latest=root/'latest/openf1_event_source_closure/1297'
        weather=latest/'data/openf1_weather.csv'; weather.write_text(weather.read_text().splitlines()[0]+'\n')
        manifest=json.loads((latest/'latest_manifest.json').read_text())
        sessions=guard._validate_target_sessions(latest/'data/target_sessions.csv',manifest=manifest,generated=self.now,completed_only=True)
        with self.assertRaisesRegex(guard.PublicationHold,'event_projection_coverage_loss:weather'):
            guard._validate_event_evidence(latest,manifest,sessions,self.now,'11396')
