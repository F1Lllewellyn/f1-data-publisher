"""Surgical Qatar session admission; never calls a provider in tests."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "qatar_packet", ROOT / "scripts/live_capture/f1_qatar_2026_original_packet_custody_v1.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
UTC = dt.timezone.utc


class QatarPacketCustodyTests(unittest.TestCase):
    def test_f1_official_timetable_exact_2026_utc(self):
        starts = [
            ("fp1", "2026-11-27T13:30:00Z"),
            ("fp2", "2026-11-27T17:00:00Z"),
            ("fp3", "2026-11-28T14:30:00Z"),
            ("qualifying", "2026-11-28T18:00:00Z"),
            ("race", "2026-11-29T16:00:00Z"),
        ]
        self.assertEqual([(x[0], x[3]) for x in module.WINDOWS], starts)
        for label, start, end, scheduled in module.WINDOWS:
            with self.subTest(session=label):
                self.assertEqual(module.active_window(module.timestamp(start))["session_label"], label)
                self.assertIsNone(module.active_window(module.timestamp(end)))
                self.assertTrue(module.timestamp(start) < module.timestamp(scheduled)
                                < module.timestamp(end))

    def test_no_provider_outside_scheduled_window(self):
        with tempfile.TemporaryDirectory() as d:
            def never(*args, **kwargs):
                self.fail("Must not record when outside Qatar UTC window")
            result = module.capture(Path(d), at=dt.datetime(2026, 11, 22, tzinfo=UTC),
                                    recorder=never, indexer=never)
            self.assertEqual(result["result"], "HOLD_OUTSIDE_QATAR_2026_WINDOW")
            self.assertEqual(result["original_packet_bytes"], 0)
            self.assertIs(result["forecast_eligible"], False)
            self.assertIs(result["promotion_allowed"], False)

    def test_valid_original_bytes_remain_session_unbound(self):
        raw = b"[2026-11-28T18:06:20.123Z] TimingData SourcePacket\n"
        def recorder(path, minutes):
            self.assertEqual(minutes, 5)
            path.write_bytes(raw)
            return dict(recording_status="completed", auth_credentials_configured=True,
                        recording_started_utc="2026-11-28T18:06:10Z",
                        recording_finished_utc="2026-11-28T18:06:25Z", error=None)
        def indexer(path, dest):
            self.assertEqual(path.read_bytes(), raw)
            dest.write_text("line,topic\n1,TimingData\n")
            return dict(line_count=1, topic_counts={"TimingData": 1})
        with tempfile.TemporaryDirectory() as d:
            result = module.capture(Path(d), at=module.timestamp("2026-11-28T18:06:10Z"),
                                    recorder=recorder, indexer=indexer)
            self.assertEqual(result["result"], "CAPTURED_ORIGINAL_PACKETS_UNBOUND")
            self.assertEqual(result["session_label"], "qualifying")
            self.assertEqual(result["original_packet_bytes"], len(raw))
            self.assertEqual(result["original_packet_sha256"],
                             module.sha256(Path(d) / "original_live_timing_packets.txt"))
            self.assertIsNone(result["provider_session_key"])
            for key in ("source_complete", "production_published", "forecast_eligible",
                        "prediction_locked", "stable_engine_executed", "promotion_allowed"):
                self.assertFalse(result[key])
            self.assertEqual(json.loads((Path(d)/"custody_manifest.json").read_text())["result"],
                             "CAPTURED_ORIGINAL_PACKETS_UNBOUND")

    def test_invalid_auth_wrong_clock_and_empty_are_not_captures(self):
        for override in (
            {"auth_credentials_configured": False},
            {"recording_started_utc": "2026-11-29T18:36:00Z"},
            {"recording_finished_utc": "2026-11-29T18:36:00Z"},
            {"recording_status": "source_feed_handshake_unavailable"},
            {"error": "HOLD_F1_SIGNALR_AUTH_OR_CONNECT_FAILED"},
        ):
            with self.subTest(override=override), tempfile.TemporaryDirectory() as d:
                def recorder(path, minutes):
                    path.write_bytes(b"not enough to confirm trustworthy recording\n")
                    return dict({"recording_status": "completed", "auth_credentials_configured": True,
                        "recording_started_utc": "2026-11-29T16:05:00Z",
                        "recording_finished_utc": "2026-11-29T16:05:05Z", "error": None},
                        **override)
                def indexer(path, dest):
                    return {"line_count": 1, "topic_counts": {"TimingData": 1}}
                result = module.capture(Path(d), at=module.timestamp("2026-11-29T16:05:00Z"),
                                        recorder=recorder, indexer=indexer)
                self.assertEqual(result["result"], "HOLD_ORIGINAL_CAPTURE_UNVERIFIED")
                self.assertFalse(result["source_complete"])

    def test_missing_packet_bytes_and_invalid_clock_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            result = module.capture(Path(d), at=module.timestamp("2026-11-29T16:05:00Z"),
                  recorder=lambda path, minutes: {
                    "recording_status": "completed", "auth_credentials_configured": True,
                    "recording_started_utc": "2026-11-29T16:05:00Z",
                    "recording_finished_utc": "2026-11-29T16:05:05Z", "error": None},
                  indexer=lambda *args: self.fail("indexer must not run on zero-byte input"))
            self.assertEqual(result["result"], "HOLD_ORIGINAL_CAPTURE_UNVERIFIED")
        with self.assertRaises(ValueError):
            module.active_window(dt.datetime(2026, 11, 29, 16, 0))
        with self.assertRaises(ValueError):
            module.capture(Path("unused"), at=module.timestamp("2026-11-29T16:00:00Z"),
                           duration_minutes=200, recorder=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
