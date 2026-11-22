"""Read-only offline adversarial tests for the Qatar original packet watchdog."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/live_capture"))
spec = importlib.util.spec_from_file_location(
    "qatar_watch", ROOT / "scripts/live_capture/f1_qatar_2026_packet_watchdog_v1.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
UTC = dt.timezone.utc


class QatarWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 27, 15, 40, tzinfo=UTC)
        self.run = {
            "created_at": "2026-11-27T13:43:00Z",
            "status": "completed", "conclusion": "success",
            "event": "schedule", "head_branch": "main",
            "path": watch.WORKFLOW_PATH,
            "head_repository": {"full_name": watch.REPO},
            "id": 123456, "run_attempt": 1,
        }
        self.original = b"[2026-11-27T13:43:12Z] TimingData RealPacket\n"
        self.manifest = {
            "schema": "qatar-2026-original-live-packet-custody-v1",
            "session_label": "fp1", "result": "CAPTURED_ORIGINAL_PACKETS_UNBOUND",
            "provider_session_key": None, "source_complete": False,
            "forecast_eligible": False, "prediction_locked": False,
            "promotion_allowed": False, "recording_clock_valid": True,
            "original_packet_bytes": len(self.original), "packet_lines": 1,
            "original_packet_sha256": hashlib.sha256(self.original).hexdigest(),
        }

    def archive(self, modified=None, raw=None):
        manifest = dict(self.manifest, **(modified or {}))
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as z:
            z.writestr("custody_manifest.json", json.dumps(manifest))
            z.writestr("original_live_timing_packets.txt",
                       self.original if raw is None else raw)
        return output.getvalue()

    def fetch(self, url, *, token):
        self.assertEqual(token, "test-token")
        if url.endswith("runs?per_page=100"):
            return json.dumps({"workflow_runs": [self.run]}).encode()
        if url.endswith("artifacts?per_page=100"):
            return json.dumps({"artifacts": [
                {"name": "f1-qatar-2026-original-packets-123456-1",
                 "id": 999, "expired": False}]}).encode()
        if url.endswith("artifacts/999/zip"):
            return self.archive()
        self.fail("unexpected source " + url)

    def test_verified_original_run_and_nonzero_zip_proves_only_packets(self):
        result = watch.assess(now=self.now, token="test-token", fetch=self.fetch)
        self.assertEqual(result["status"], "ORIGINAL_PACKETS_RETAINED_SESSION_UNBOUND")
        self.assertEqual(result["original_run_id"], 123456)
        self.assertFalse(result["source_complete"])
        self.assertFalse(result["forecast_eligible"])

    def test_not_due_does_not_call_api(self):
        def never(*args, **kwargs): self.fail("early watchdog cannot fetch")
        self.assertEqual(watch.assess(now=dt.datetime(2026,11,22,tzinfo=UTC),
                                      fetch=never)["status"], "HOLD_WATCHDOG_NOT_DUE")

    def test_missing_run_wrong_identity_or_failed_job_remain_actionable(self):
        for override in (
            {"conclusion": "failure"},
            {"status": "in_progress"},
            {"event": "pull_request"},
            {"head_branch": "experimental"},
            {"path": "unknown"},
            {"head_repository": {"full_name": "attacker/repo"}},
            {"created_at": "2026-11-27T15:01:00Z"},
            {"run_attempt": 0},
        ):
            with self.subTest(override=override):
                altered = dict(self.run, **override)
                def fake(url, *, token):
                    if url.endswith("runs?per_page=100"):
                        return json.dumps({"workflow_runs": [altered]}).encode()
                    self.fail("invalid run must not request artifacts")
                self.assertEqual(watch.assess(now=self.now, token="test-token",
                                            fetch=fake)["status"],
                                 "FAIL_NO_AUTHENTIC_ORIGINAL_CAPTURE_IN_SESSION")

    def test_missing_auth_is_failure_not_source_hold(self):
        with self.assertRaisesRegex(ValueError, "FAIL_GITHUB_AUTH_UNAVAILABLE"):
            watch.get(watch.BASE+"/actions/runs", token="")
        with self.assertRaisesRegex(ValueError, "FAIL_GITHUB_URL_SCOPE"):
            watch.get("https://attacker.example/artifact", token="test-token")

    def test_bad_digest_zero_bytes_wrong_source_flags_never_pass(self):
        alterations = (
            ({"session_label": "race"}, None),
            ({"result": "READY"}, None),
            ({"original_packet_bytes": 0}, None),
            ({"original_packet_sha256": "0"*64}, None),
            ({"forecast_eligible": True}, None),
            ({"source_complete": True}, None),
            ({"provider_session_key": 11420}, None),
            ({"packet_lines": 0}, None),
            ({}, b""),
            ({}, b"mutated data"),
        )
        for changed, raw in alterations:
            with self.subTest(changed=changed, raw=raw):
                self.assertFalse(watch.artifact_verified(self.archive(changed, raw), "fp1"))

    def test_missing_artifact_causes_failure_even_on_green_workflow(self):
        def fake(url, *, token):
            if url.endswith("runs?per_page=100"):
                return json.dumps({"workflow_runs": [self.run]}).encode()
            return json.dumps({"artifacts": []}).encode()
        self.assertEqual(watch.assess(now=self.now, token="test-token",
                                      fetch=fake)["status"],
                         "FAIL_NO_AUTHENTIC_ORIGINAL_CAPTURE_IN_SESSION")


if __name__ == "__main__":
    unittest.main()
