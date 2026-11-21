"""Execute the gate boundary offline: a research lane is never stable execution."""
import contextlib
import copy
import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/forecast_bundles/orchestrate_forecast_gate_pipeline_v1.py"
spec = importlib.util.spec_from_file_location("recovery_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def catalog():
    # Synthetic IDs deliberately do not pretend to be Las Vegas OpenF1 keys.
    rows = []
    for key, name, start, end in (
        (900001, "Practice 1", "2026-11-20T00:30:00Z", "2026-11-20T01:30:00Z"),
        (900002, "Practice 2", "2026-11-20T04:00:00Z", "2026-11-20T05:00:00Z"),
        (900003, "Practice 3", "2026-11-21T00:30:00Z", "2026-11-21T01:30:00Z"),
        (900004, "Qualifying", "2026-11-21T04:00:00Z", "2026-11-21T05:00:00Z"),
        (900005, "Race", "2026-11-22T04:00:00Z", "2026-11-22T06:00:00Z"),
    ):
        rows.append(dict(session_key=key, meeting_key=900000, year=2026,
                         session_name=name, session_type="Practice" if "Practice" in name else name,
                         date_start=start, date_end=end, location="SIMULATED Las Vegas"))
    return rows


class GateCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in (("ROOT", self.root), ("RUNTIME", self.root / "_runtime/gate"),
                            ("POLICY_PATH", self.root / "missing_policy.json")):
            self.enterContext(patch.object(gate, name, value))

    def run_main(self, args, rows=None, now="2026-11-21T05:30:00Z"):
        with patch.object(sys, "argv", ["gate", *args]), patch.object(gate, "fetch_openf1_sessions", return_value=rows or catalog()), patch.object(gate, "utc_now", return_value=gate.parse_time(now)), contextlib.redirect_stdout(io.StringIO()), patch.object(gate, "run_command") as commands:
            rc = gate.main()
        commands.assert_not_called()
        result = json.loads((gate.RUNTIME / "orchestrator_result.json").read_text())
        self.assertFalse(result["prediction_locked"])
        self.assertFalse(result["stable_engine_executed"])
        self.assertFalse((self.root / "history").exists())
        return rc, result

    def test_all_modes_hold_without_heuristic_writer_or_locker(self):
        for mode in ("auto", "dry_run", "force_validation"):
            with self.subTest(mode=mode):
                rc, result = self.run_main(["--mode", mode])
                self.assertEqual(rc, 2)
                self.assertEqual(result["reason"], "HOLD_STABLE_ENGINE_NOT_EXECUTED")
                self.assertFalse(result["steps"][0]["source_refresh_executed"])

    def test_missing_or_disabled_source_refresh_cannot_bypass_engine_hold(self):
        for enabled in ("true", "false"):
            rc, result = self.run_main(["--run-source-closure", enabled])
            self.assertEqual((rc, result["status"]), (2, "HOLD"))

    def test_existing_three_lane_manifest_is_not_authentic_lock(self):
        event = "synthetic_event"
        before = {}
        for lane in gate.LANES:
            path = self.root / "latest/forecast_bundles" / event / "post_qualifying" / lane / "bundle_lock_manifest.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"blind_validation_eligible":true,"engine_lane":"stable_baseline"}')
            before[path] = path.read_bytes()
        rc, result = self.run_main(["--event-id", event])
        self.assertEqual(result["reason"], "HOLD_EXISTING_BUNDLE_NOT_AUTHENTICATED")
        self.assertEqual(rc, 2)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_restart_cannot_create_a_lock(self):
        for _ in range(2):
            self.assertEqual(self.run_main([])[0], 2)

    def test_post_outcome_cannot_produce_prospective_forecast(self):
        for value in ("race_result", "post_event"):
            rc, result = self.run_main(["--mode", "force_validation", "--gate", value])
            self.assertEqual(result["reason"], "HOLD_POST_OUTCOME_NOT_PROSPECTIVE")

    def test_synthetic_stable_available_claim_is_not_execution_evidence(self):
        (self.root / "Engine_2026-06-07_STABLE").mkdir()
        (self.root / "Engine_2026-06-07_STABLE/receipt.json").write_text('{"executed":true}')
        self.assertEqual(self.run_main([])[1]["reason"], "HOLD_STABLE_ENGINE_NOT_EXECUTED")

    def test_inactive_gate_is_explicit_no_action_not_lock_pass(self):
        rc, result = self.run_main([], now="2026-11-14T12:00:00Z")
        self.assertEqual((rc, result["status"]), (0, "no_action"))
        self.assertEqual(result["scientific_status"], "HOLD_STABLE_ENGINE_NOT_EXECUTED")

    def test_las_vegas_transition_schedule_and_cutoff(self):
        expected = {
            "2026-11-19T12:00:00Z": "pre_weekend",
            "2026-11-20T01:35:00Z": "none",
            "2026-11-20T05:35:00Z": "none",
            "2026-11-21T01:35:00Z": "post_fp3",
            "2026-11-21T05:30:00Z": "post_qualifying",
            "2026-11-22T03:50:00Z": "none",  # cutoff is exclusive
            "2026-11-22T06:15:00Z": "race_result",
        }
        for now, wanted in expected.items():
            with self.subTest(now=now), patch.object(gate, "fetch_openf1_sessions", return_value=catalog()):
                result = gate.detect_gate_from_schedule(2026, gate.parse_time(now), {})
                self.assertEqual(result["gate"], wanted)

    def test_invalid_identity_clock_duplicate_or_partial_catalog_holds(self):
        mutations = [("meeting_key", True), ("session_key", "../1"), ("year", 2025),
                     ("date_start", "2026-11-20T00:00:00"), ("date_end", None)]
        for field, value in mutations:
            rows = catalog()
            rows[0][field] = value
            with self.subTest(field=field):
                rc, result = self.run_main([], rows)
                self.assertEqual((rc, result["status"]), (2, "HOLD"))
        rows = catalog()
        rows.append(copy.deepcopy(rows[0]))
        self.assertEqual(self.run_main([], rows)[0], 2)

    def test_provider_failures_are_actionable_and_not_retried(self):
        for status in (401, 403, 404, 429, 503):
            with self.subTest(status=status), patch.object(gate.urllib.request, "urlopen", side_effect=urllib.error.HTTPError("offline", status, "fixture", {}, None)) as request:
                with self.assertRaisesRegex(gate.ScheduleHold, f"HOLD_SCHEDULE_HTTP_{status}"):
                    gate.fetch_openf1_sessions(2026)
                self.assertEqual(request.call_count, 1)

    def test_cli_isolation_no_approved_execution_surface(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--mode", "force_validation"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.root / "latest").exists())
        self.assertIn("HOLD_STABLE_ENGINE_NOT_EXECUTED", result.stdout)

    def test_workflow_is_read_only_and_upload_is_bounded(self):
        text = (ROOT / ".github/workflows/f1-automated-forecast-gate-orchestrator-v1.yml").read_text()
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("group: f1-main-write-serialization", text)
        for token in ("contents: write", "history/", "latest/", "git add", "git commit", "git push"):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
