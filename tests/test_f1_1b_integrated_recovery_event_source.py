"""Full collector execution with synthetic, explicitly scoped provider responses."""
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_openf1_normal_incremental_collection_budget_v1 import m, Router, FakeClock, Response, session


class EventSourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.now = dt.datetime(2026, 10, 26, 12, tzinfo=dt.UTC)
        self.rows = [session(11395, meeting_key=1296), session(11396)]

    def collect(self, *, meeting='1297', expected='11396', now=None, handler=None):
        router = Router(self.rows, handler)
        clock = FakeClock()
        argv = ['collector', '--output-root', str(self.root), '--meeting-key', meeting,
                '--expected-session-key', expected]
        with patch.object(m.requests, 'get', side_effect=router), patch.object(m, 'utc_now', return_value=now or self.now), patch.object(m.time, 'monotonic', side_effect=clock.monotonic), patch.object(m.time, 'sleep', side_effect=clock.sleep), patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
            rc = m.main()
        root = self.root / 'latest/openf1_event_source_closure' / meeting
        return rc, json.loads((root / 'latest_manifest.json').read_text()), router, root

    def test_event_collection_ignores_other_event_and_keeps_archive_hold_separate(self):
        rc, manifest, router, root = self.collect()
        self.assertEqual(rc, 0)
        self.assertTrue(manifest['publication_eligible'])
        self.assertEqual(manifest['target_session_count'], 1)
        self.assertFalse(manifest['historical_archive_complete'])
        self.assertFalse(manifest['normal_collection']['prospective_forecast_eligibility_established'])
        self.assertFalse((self.root / 'latest/openf1_lightweight_source_closure').exists())
        self.assertTrue(all(str(p.get('session_key')) == '11396' for ep, p, _ in router.calls if ep != 'sessions'))
        self.assertTrue(manifest['scientific_readiness'].startswith('HOLD_'))
        rc, second, router, _ = self.collect(now=self.now + dt.timedelta(hours=1))
        self.assertEqual(rc, 0)
        self.assertEqual([ep for ep, _, _ in router.calls], ['sessions'])
        self.assertEqual(second['normal_collection']['reused_session_count'], 1)

    def test_no_session_or_wrong_expected_session_never_becomes_complete(self):
        for meeting, expected in [('9999', '11396'), ('1297', '99999')]:
            with self.subTest(meeting=meeting):
                rc, manifest, _, _ = self.collect(meeting=meeting, expected=expected)
                self.assertEqual(rc, 1)
                self.assertFalse(manifest['publication_eligible'])

    def test_historical_delay_keeps_expected_session_in_hold(self):
        rc, manifest, router, _ = self.collect(now=dt.datetime(2026, 10, 25, 21, 15, tzinfo=dt.UTC))
        self.assertEqual(rc, 1)
        self.assertIn('event_session_historical_window_pending:11396', manifest['source_quality_reasons'])
        self.assertEqual([ep for ep, _, _ in router.calls], ['sessions'])

    def test_unknown_driver_and_future_row_are_rejected(self):
        for corruption in ('driver', 'clock'):
            def handler(ep, p):
                if ep == 'position':
                    return Response(data=[dict(session_key=11396, meeting_key=1297,
                        driver_number=999 if corruption == 'driver' else 44,
                        date='2099-01-01T00:00:00Z' if corruption == 'clock' else '2026-10-25T20:00:00Z')])
            with self.subTest(corruption=corruption):
                rc, manifest, _, _ = self.collect(handler=handler, now=self.now + dt.timedelta(hours=corruption == 'clock'))
                self.assertEqual(rc, 1)
                self.assertTrue(any('event_driver_' in r or 'event_row_clock_' in r for r in manifest['source_quality_reasons']))

    def test_provider_errors_remain_actionable_hold_without_retry_storm(self):
        for i, code in enumerate((401, 403, 404, 429, 503)):
            with self.subTest(code=code):
                rc, manifest, router, _ = self.collect(now=self.now + dt.timedelta(hours=i), handler=lambda ep, p: Response(status_code=code, text='provider failure') if ep == 'weather' else None)
                self.assertEqual(rc, 1)
                self.assertFalse(manifest['publication_eligible'])
                self.assertLessEqual(len(router.calls), 10)

    def test_duplicate_timestamp_cannot_overwrite_historical_capture(self):
        self.collect()
        before = {p: p.read_bytes() for p in (self.root / 'history').rglob('*') if p.is_file()}
        with self.assertRaises(FileExistsError):
            self.collect()
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_malformed_event_scope_fails_before_network(self):
        with patch.object(m.requests, 'get') as request, patch('sys.argv', ['collector', '--meeting-key', '../main']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                m.main()
        request.assert_not_called()
