"""Issue #367 live authenticated raw packet custody: no-provider regressions."""
from __future__ import annotations
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/live_capture"))
spec = importlib.util.spec_from_file_location(
    "vegas_source_probe", ROOT / "scripts/live_capture/f1_vegas_2026_live_packet_probe_v1.py"
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
UTC = dt.timezone.utc


class SourceProbeContracts(unittest.TestCase):
    def test_qualifying_and_race_exact_2026_windows_only(self):
        checks = [
            ((2026,11,21,3,51),None),
            ((2026,11,21,3,52),"qualifying"),
            ((2026,11,21,4,3),"qualifying"),
            ((2026,11,21,5,14),"qualifying"),
            ((2026,11,21,5,15),None),
            ((2026,11,22,3,51),None),
            ((2026,11,22,3,52),"race"),
            ((2026,11,22,6,34),"race"),
            ((2026,11,22,6,35),None),
            ((2027,11,21,4,3),None),
        ]
        for date, expected in checks:
            with self.subTest(date=date):
                data = probe.observe_window(dt.datetime(*date,tzinfo=UTC))
                self.assertEqual(data["session_label"] if data else None, expected)
                if data:
                    self.assertEqual(data["meeting_key"],1300)
                    self.assertEqual(data["session_key"],11416 if expected=="qualifying" else 11420)

    def test_naive_clock_does_not_select_live_window(self):
        with self.assertRaises(ValueError):
            probe.observe_window(dt.datetime(2026,11,21,4,0))

    def test_outside_window_no_network_or_historical_change(self):
        with tempfile.TemporaryDirectory() as td:
            def never(*args):
                self.fail("Cannot record outside exact event window")
            result = probe.capture(Path(td)/"source", at=dt.datetime(2026,11,20,21,0,tzinfo=UTC),
                                   recorder=never, indexer=never)
            self.assertEqual(result["result"],"HOLD_NOT_IN_EXACT_2026_SESSION_WINDOW")
            self.assertFalse((Path(td)/"latest").exists())
            self.assertFalse((Path(td)/"history").exists())
            self.assertEqual(result["original_packet_bytes"],0)
            self.assertFalse(result["forecast_eligible"])

    def test_original_bytes_sha256_and_source_only_status(self):
        raw=b'[2026-11-21T04:02:00.000Z] TimingData PacketSample\n'
        def fake_recorder(path, minutes):
            self.assertEqual(minutes,5)
            path.write_bytes(raw)
            return {"recording_status":"completed","recording_started_utc":"2026-11-21T04:02:00Z",
                    "recording_finished_utc":"2026-11-21T04:02:05Z",
                    "auth_credentials_configured":True,"error":None}
        def fake_indexer(raw_path,index_path):
            self.assertEqual(raw_path.read_bytes(),raw)
            index_path.write_text("line_number,topic_hint\n1,TimingData\n")
            return {"line_count":1,"topic_counts":{"TimingData":1}}
        with tempfile.TemporaryDirectory() as td:
            result=probe.capture(Path(td)/"artifacts",at=dt.datetime(2026,11,21,4,2,tzinfo=UTC),
                                 recorder=fake_recorder,indexer=fake_indexer)
            self.assertEqual(result["result"],"LIVE_ORIGINAL_SIGNALR_PACKET_BYTES_CONTEXT_ONLY")
            self.assertEqual(result["original_packet_bytes"],len(raw))
            self.assertEqual((Path(td)/"artifacts/original_live_timing_packets.txt").read_bytes(),raw)
            self.assertEqual(result["original_packet_sha256"],probe.sha256_file(
                Path(td)/"artifacts/original_live_timing_packets.txt"))
            self.assertEqual(result["session_identity_status"],"SCHEDULE_CONTEXT_ONLY_NOT_PROVIDER_VERIFIED")
            for key in ("production_published","source_complete","forecast_eligible",
                        "stable_engine_executed","prediction_locked"):
                self.assertIs(result[key],False)
            self.assertEqual(json.loads((Path(td)/"artifacts/custody_manifest.json").read_text())["result"],
                             result["result"])

    def test_empty_or_partial_error_capture_remains_hold_and_retained(self):
        for status,raw in (("source_feed_handshake_unavailable",b""),
                           ("recording_error",b"partial TimingData\n")):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as td:
                def fake_recorder(path,minutes):
                    if raw:path.write_bytes(raw)
                    return {"recording_status":status,"error":"HOLD_EXPERIMENTAL_SOURCE_UNAVAILABLE"}
                def fake_indexer(raw_path,index_path):
                    return {"line_count":1,"topic_counts":{"TimingData":1}}
                result=probe.capture(Path(td)/"source",at=dt.datetime(2026,11,22,4,23,tzinfo=UTC),
                                     recorder=fake_recorder,indexer=fake_indexer)
                self.assertEqual(result["result"],"HOLD_LIVE_ORIGINAL_SIGNALR_PACKETS_UNVERIFIED")
                self.assertEqual(result["original_packet_bytes"],len(raw))
                self.assertEqual(result["session_key"],11420)
                self.assertFalse(result["forecast_eligible"])
                self.assertFalse((Path(td)/"history").exists())
                self.assertFalse((Path(td)/"latest").exists())


if __name__=="__main__":
    unittest.main()
