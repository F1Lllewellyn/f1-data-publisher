"""Read-only source canary regressions: synthetic original bytes only, no provider."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "f1_live_session_source_custody_canary_v1",
    ROOT / "scripts/ops/f1_live_session_source_custody_canary_v1.py",
)
canary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(canary)


class OriginalSourceCanaryTests(unittest.TestCase):
    def test_identity_bytes_clocks_and_no_model_writes(self):
        responses = {}
        for endpoint in canary.ENDPOINTS:
            responses[endpoint] = json.dumps([{
                "meeting_key": 1300, "session_key": 11415,
                "endpoint": endpoint, "synthetic": True,
            }], separators=(",", ":")).encode()

        def fake(endpoint, session_key):
            self.assertEqual(session_key, 11415)
            return ("https://api.openf1.org/v1/" + endpoint + "?session_key=11415",
                    200, responses[endpoint], "")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(canary, "retrieve", side_effect=fake):
                result = canary.capture_session(1300, 11415, root, sleep_seconds=0)
            self.assertEqual(result["result"], "VERIFIED_LIVE_PROVIDER_SNAPSHOT_CONTEXT_ONLY")
            self.assertEqual(set(result["verified_row_counts"]), set(canary.ENDPOINTS))
            self.assertFalse(result["forecast_eligible"])
            self.assertFalse(result["production_published"])
            self.assertFalse(result["stable_engine_executed"])
            self.assertFalse(result["prediction_locked"])
            self.assertEqual(len(result["requests"]), 5)
            for row in result["requests"]:
                raw = responses[row["endpoint"]]
                self.assertEqual((root / row["original_response_filename"]).read_bytes(), raw)
                self.assertEqual(row["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertTrue(row["requested_at_utc"].endswith("Z"))
                self.assertTrue(row["observed_at_utc"].endswith("Z"))
                self.assertTrue(row["identity_verified"])
            self.assertFalse((root / "latest").exists())
            self.assertFalse((root / "history").exists())

    def test_failed_required_endpoint_is_retained_and_hold(self):
        def fake(endpoint, session_key):
            if endpoint == "laps":
                return ("https://api.openf1.org/v1/laps?session_key=11415", 401,
                        b"provider denied", "HTTP 401")
            return ("https://api.openf1.org/v1/" + endpoint, 200,
                    b'[{"meeting_key":1300,"session_key":11415}]', "")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(canary, "retrieve", side_effect=fake):
                result = canary.capture_session(1300, 11415, root, sleep_seconds=0)
            self.assertEqual(result["result"], "HOLD_LIVE_SOURCE_SNAPSHOT_INCOMPLETE")
            self.assertEqual((root / "laps_response.bin").read_bytes(), b"provider denied")
            row = next(row for row in result["requests"] if row["endpoint"] == "laps")
            self.assertEqual(row["http_status"], 401)
            self.assertFalse(row["identity_verified"])
            self.assertEqual(row["sha256"], hashlib.sha256(b"provider denied").hexdigest())
            self.assertFalse(result["forecast_eligible"])

    def test_wrong_session_and_rehashed_wrong_meeting_are_not_accepted(self):
        for bad in ({"session_key": 11414, "meeting_key": 1300},
                    {"session_key": 11415, "meeting_key": 1299}):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as td:
                def fake(endpoint, session_key):
                    obj = bad if endpoint == "sessions" else {
                        "session_key": 11415, "meeting_key": 1300
                    }
                    return ("https://api.openf1.org/v1/" + endpoint, 200,
                            json.dumps([obj]).encode(), "")
                with patch.object(canary, "retrieve", side_effect=fake):
                    result = canary.capture_session(1300, 11415, td, sleep_seconds=0)
                self.assertEqual(result["result"], "HOLD_LIVE_SOURCE_SNAPSHOT_INCOMPLETE")
                self.assertEqual(result["requests"][0]["error"], "HOLD_SESSION_OR_MEETING_IDENTITY")

    def test_oversize_response_never_counts_as_complete(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(canary, "MAX_BYTES", 16), \
                 patch.object(canary, "retrieve", return_value=(
                     "https://api.openf1.org/v1/laps", 200, b"x" * 17, "")):
                result = canary.capture_session(1300, 11415, td, sleep_seconds=0)
            self.assertEqual(result["result"], "HOLD_LIVE_SOURCE_SNAPSHOT_INCOMPLETE")
            self.assertTrue(all(r["truncated"] for r in result["requests"]))


if __name__ == "__main__":
    unittest.main()
