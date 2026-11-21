"""Issue #367 post-release live feed runner and fail-closed capture regression tests.

These tests exercise the real module and output preservation using simulated raw
SignalR packets. They do not call a provider or assert actual source availability.
"""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/live_capture/run_live_source_feed_capture.py"
WORKFLOW_PATH = ROOT / ".github/workflows/f1-live-source-feed-capture-experimental.yml"
spec = importlib.util.spec_from_file_location("live_feed_capture_under_test", MODULE_PATH)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class LiveFeedRepairTests(unittest.TestCase):
    def test_runner_is_modern_signalr_core_and_does_not_block_main_serialization(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("runs-on: ubuntu-24.04", text)
        self.assertIn('python-version: "3.11"', text)
        self.assertIn("group: f1-experimental-live-source-feed", text)
        self.assertIn("fastf1==3.9.2", text)
        self.assertIn("F1_USERNAME: ${{ secrets.F1_USERNAME }}", text)
        self.assertIn("F1_PASSWORD: ${{ secrets.F1_PASSWORD }}", text)
        self.assertNotIn("group: f1-main-write-serialization", text)
        self.assertIn("cancel-in-progress: false", text)

    def exercise(self, reason, should_capture, recording_status="not_started",
                 raw=b"", expected=0):
        policy = {
            "schema_version": "test-only",
            "module_name": "synthetic-fixture",
            "guardrails": {},
            "team_radio_policy": "opportunistic_only",
            "outputs": {
                "latest_dir": "latest/live_source_feed_capture",
                "history_dir": "history/live_source_feed_capture",
                "raw_capture_filename": "live_timing_raw.txt",
                "manifest_filename": "live_source_feed_capture_manifest.json",
                "readiness_filename": "live_source_feed_capture_readiness.json",
                "packet_index_filename": "live_source_feed_packet_index.csv",
                "capture_report_filename": "live_source_feed_capture_report.md",
                "zip_filename": "live_source_feed_capture_package.zip",
            }
        }
        decision = {
            "should_capture": should_capture,
            "reason": reason,
            "session_label": "synthetic_fp3",
            "duration_minutes": 1,
            "session_key": 11415,
            "meeting_key": 1300,
        }
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            config = base / "policy.json"
            config.write_text(json.dumps(policy), encoding="utf-8")
            original_cwd = Path.cwd()

            def synthetic_record(path, duration):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                return {
                    "recording_status": recording_status,
                    "recording_attempted": True,
                    "recording_started_utc": "2026-11-21T00:30:00Z",
                    "recording_finished_utc": "2026-11-21T00:31:00Z",
                    "duration_minutes_requested": duration,
                }

            try:
                os.chdir(base)
                with patch.object(capture, "choose_active_window", return_value=decision), \
                     patch.object(capture, "record_live_timing", side_effect=synthetic_record), \
                     patch.object(sys, "argv", [
                         "capture", "--policy", str(config),
                         "--capture-mode", "auto_window",
                         "--github-run-id", "synthetic-not-a-github-run",
                     ]), contextlib.redirect_stdout(__import__("io").StringIO()):
                    exit_code = capture.main()
                self.assertEqual(exit_code, expected)
                historical = list((base / "history/live_source_feed_capture").glob("*/live_source_feed_capture_readiness.json"))
                self.assertEqual(len(historical), 1)
                readiness = json.loads(historical[0].read_text(encoding="utf-8"))
                self.assertEqual(readiness["verdict"] == "Fail", expected != 0)
                latest_raw = base / "latest/live_source_feed_capture/live_timing_raw.txt"
                if expected != 0:
                    self.assertFalse(latest_raw.exists(), "Failed capture must not replace latest source evidence")
                if expected == 0 and should_capture and recording_status == "completed" and raw:
                    self.assertEqual(latest_raw.read_bytes(), raw)
            finally:
                os.chdir(original_cwd)

    def test_scheduled_empty_completed_capture_is_failure(self):
        self.exercise("active_schedule_window", True, "completed", b"", 1)

    def test_scheduled_import_failure_is_failure(self):
        self.exercise("active_schedule_window", True, "fastf1_import_failed", b"", 1)

    def test_missing_f1tv_auth_fails_without_attempted_source(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"F1_USERNAME": "", "F1_PASSWORD": ""}), \
             patch.object(capture, "get_package_version", return_value="3.9.2"), \
             patch.object(capture.subprocess, "run") as exec_source:
            result = capture.record_live_timing(Path(td) / "raw.txt", 1)
            self.assertEqual(result["recording_status"], "f1_auth_missing")
            self.assertEqual(result["error"], "HOLD_F1TV_AUTH_NOT_CONFIGURED")
            self.assertFalse(result["recording_attempted"])
            self.assertFalse(result["auth_credentials_configured"])
            exec_source.assert_not_called()
        self.exercise("active_schedule_window", True, "f1_auth_missing", b"", 1)

    def test_obsolete_fastf1_is_explicitly_rejected_before_source(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"F1_USERNAME": "synthetic@example.invalid",
                                     "F1_PASSWORD": "SYNTHETIC_NOT_A_SECRET"}), \
             patch.object(capture, "get_package_version", return_value="3.6.1"), \
             patch.object(capture.subprocess, "run") as exec_source:
            result = capture.record_live_timing(Path(td) / "raw.txt", 1)
            self.assertEqual(result["recording_status"], "fastf1_version_unsupported")
            self.assertEqual(result["error"], "HOLD_FASTF1_SIGNALR_CORE_VERSION")
            exec_source.assert_not_called()

    def test_authenticated_child_records_real_bytes_without_leaking_secrets(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"F1_USERNAME": "synthetic@example.invalid",
                                     "F1_PASSWORD": "SYNTHETIC_NOT_A_SECRET"}), \
             patch.object(capture, "get_package_version", return_value="3.9.2"):
            path = Path(td) / "raw.txt"
            def fake_run(args, **kwargs):
                self.assertEqual(args[0], sys.executable)
                self.assertIn("SignalRClient", args[2])
                self.assertNotIn("SYNTHETIC_NOT_A_SECRET", str(args))
                self.assertEqual(kwargs["timeout"], 60)
                path.write_bytes(b"synthetic-signalr-original-packets")
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")
            with patch.object(capture.subprocess, "run", side_effect=fake_run):
                result = capture.record_live_timing(path, 1)
            self.assertEqual(result["recording_status"], "completed")
            self.assertTrue(result["recording_attempted"])
            self.assertTrue(result["fastf1_import_ok"])
            self.assertTrue(result["auth_credentials_configured"])
            self.assertEqual(path.read_bytes(), b"synthetic-signalr-original-packets")
            self.assertNotIn("SYNTHETIC_NOT_A_SECRET", json.dumps(result))

    def test_timeboxed_child_retains_flushed_original_bytes(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"F1_USERNAME": "synthetic@example.invalid",
                                     "F1_PASSWORD": "SYNTHETIC_NOT_A_SECRET"}), \
             patch.object(capture, "get_package_version", return_value="3.9.2"):
            path = Path(td) / "raw.txt"
            def timeout(args, **kwargs):
                path.write_bytes(b"bounded-original-packets")
                raise subprocess.TimeoutExpired(cmd=args, timeout=60)
            with patch.object(capture.subprocess, "run", side_effect=timeout):
                result = capture.record_live_timing(path, 1)
            self.assertEqual(result["recording_status"], "completed")
            self.assertTrue(result["timeboxed"])
            self.assertEqual(path.read_bytes(), b"bounded-original-packets")

    def test_auth_error_does_not_log_private_child_output(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"F1_USERNAME": "synthetic@example.invalid",
                                     "F1_PASSWORD": "SYNTHETIC_NOT_A_SECRET"}), \
             patch.object(capture, "get_package_version", return_value="3.9.2"), \
             patch.object(capture.subprocess, "run", return_value=subprocess.CompletedProcess(
                 [], 1, b"private-subprocess-output", b"token=SYNTHETIC_NOT_A_SECRET")):
            result = capture.record_live_timing(Path(td) / "raw.txt", 1)
            self.assertEqual(result["recording_status"], "source_feed_handshake_unavailable")
            self.assertEqual(result["error"], "HOLD_F1_SIGNALR_AUTH_OR_CONNECT_FAILED")
            self.assertNotIn("SYNTHETIC_NOT_A_SECRET", json.dumps(result))

    def test_scheduled_handshake_unavailable_is_failure(self):
        self.exercise("active_schedule_window", True, "source_feed_handshake_unavailable", b"", 1)

    def test_provider_lookup_failure_is_failure(self):
        self.exercise("schedule_lookup_failed: HTTP 429", False, expected=1)

    def test_no_active_window_is_not_an_invented_capture(self):
        self.exercise("no_active_capture_window", False, expected=0)

    def test_manual_infrastructure_validation_does_not_require_feed(self):
        self.exercise("manual_dispatch_infrastructure_only", False, expected=0)

    def test_verified_nonempty_synthetic_recording_updates_latest(self):
        self.exercise("active_schedule_window", True, "completed",
                      b'{"topic":"TimingData","synthetic":true}\\n', 0)

    def test_partial_failed_recording_is_archived_but_not_promoted(self):
        self.exercise("active_schedule_window", True, "recording_error",
                      b'{"partial":true}\\n', 1)


    def test_failed_capture_diagnostic_status_is_uploaded_and_committed(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("latest/live_source_feed_capture_status/**", workflow)
        self.assertIn("for folder in latest/live_source_feed_capture latest/live_source_feed_capture_status history/live_source_feed_capture", workflow)
        self.assertIn('git add -- "$folder"', workflow)

    def test_run_attempt_archive_duplicate_is_noop_and_conflict_is_hold(self):
        policy = {"outputs": {
            "latest_dir": "latest/live_source_feed_capture",
            "history_dir": "history/live_source_feed_capture"}}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "work"
            source.mkdir()
            raw = source / "live_timing_raw.txt"
            raw.write_bytes(b"first-original-capture")
            old_cwd = Path.cwd()
            fixed = capture.dt.datetime(2026, 11, 21, 0, 30, tzinfo=capture.UTC)
            try:
                os.chdir(root)
                with patch.object(capture, "now_utc", return_value=fixed):
                    first = capture.copy_to_latest_and_history(
                        source, policy, "Las_Vegas_Practice_3", False,
                        {"github_run_id": "789", "github_run_attempt": "1", "verdict": "Fail"})
                    hist = Path(first["history_output_dir"])
                    original = (hist / raw.name).read_bytes()
                    original_mtime = (hist / raw.name).stat().st_mtime_ns
                    second = capture.copy_to_latest_and_history(
                        source, policy, "Las_Vegas_Practice_3", False,
                        {"github_run_id": "789", "github_run_attempt": "1", "verdict": "Fail"})
                    self.assertEqual(first["history_output_dir"], second["history_output_dir"])
                    self.assertEqual((hist / raw.name).read_bytes(), original)
                    self.assertEqual((hist / raw.name).stat().st_mtime_ns, original_mtime)
                    raw.write_bytes(b"conflicting-retry")
                    with self.assertRaisesRegex(RuntimeError, "HOLD_IMMUTABLE_LIVE_CAPTURE_HISTORY_COLLISION"):
                        capture.copy_to_latest_and_history(
                            source, policy, "Las_Vegas_Practice_3", False,
                            {"github_run_id": "789", "github_run_attempt": "1", "verdict": "Fail"})
                    self.assertEqual((hist / raw.name).read_bytes(), original)
                    other = capture.copy_to_latest_and_history(
                        source, policy, "Las_Vegas_Practice_3", False,
                        {"github_run_id": "790", "github_run_attempt": "1", "verdict": "Fail"})
                    self.assertNotEqual(first["history_output_dir"], other["history_output_dir"])
                    self.assertEqual((hist / raw.name).read_bytes(), original)
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
