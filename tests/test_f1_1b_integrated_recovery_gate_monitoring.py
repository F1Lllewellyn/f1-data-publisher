"""The scheduled monitor may pass operationally while all forecast authority holds."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

import test_f1_producer_lock_custody_gate as fixtures

gate = fixtures.gate


class GateMonitoringTests(unittest.TestCase):
    setUp = fixtures.GateCustodyTests.setUp
    run_main = fixtures.GateCustodyTests.run_main

    def dependencies(self):
        for rel in (
            "scripts/forecasts/produce_actual_forecast_rows_v1.py",
            "scripts/forecast_bundles/create_forecast_bundles_v1.py",
            "docs/DR002_PRE2B7G1_STABLE_ENGINE_EXECUTION_SURFACE_2026-10-05.md",
        ):
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixtures.ROOT / rel, dest)

    def test_scheduled_monitor_and_direct_caller_have_identical_scientific_hold(self):
        self.dependencies()
        summary = self.root / "job_summary.md"
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
            strict, original = self.run_main([])
            monitor, result = self.run_main(["--exit-policy", "monitor"])
        self.assertEqual((strict, monitor), (2, 0))
        for key in ("reason", "steps", "scientific_status", "scientific_classification",
                    "forecast_eligible", "prediction_locked", "stable_engine_executed"):
            self.assertEqual(original[key], result[key], key)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["operational_status"], "OPERATIONAL_PASS")
        self.assertFalse(result["forecast_eligible"])
        self.assertIn("SCIENTIFIC_HOLD", summary.read_text())
        self.assertIn("HOLD_STABLE_ENGINE_NOT_EXECUTED", summary.read_text())

    def test_provider_holds_are_visible_nonzero_and_not_retried(self):
        self.dependencies()
        for status in (401, 403, 429, 503):
            with self.subTest(status=status), patch.object(gate, "detect_gate_from_schedule",
                    side_effect=gate.ScheduleHold(f"HOLD_SCHEDULE_HTTP_{status}")) as detect:
                rc, result = self.run_main(["--exit-policy", "monitor"])
            self.assertEqual(rc, 2)
            self.assertEqual(detect.call_count, 1)
            self.assertEqual(result["operational_status"], "OPERATIONAL_FAIL")
            self.assertEqual(result["failure_class"], "EXTERNAL_PROVIDER_RESTRICTION")

    def test_bad_source_identity_and_existing_unverified_lock_do_not_turn_green(self):
        self.dependencies()
        rows = fixtures.catalog()
        rows[0]["session_key"] = "../forged"
        self.assertEqual(self.run_main(["--exit-policy", "monitor"], rows)[0], 2)
        for lane in gate.LANES:
            p = self.root / f"latest/forecast_bundles/synthetic/post_qualifying/{lane}/bundle_lock_manifest.json"
            p.parent.mkdir(parents=True)
            p.write_text('{"executed":true}')
        rc, result = self.run_main(["--exit-policy", "monitor", "--event-id", "synthetic"])
        self.assertEqual(rc, 2)
        self.assertEqual(result["failure_class"], "SOURCE_OR_CUSTODY_NOT_VERIFIED")

    def test_missing_checkout_dependency_is_operational_failure(self):
        rc, result = self.run_main(["--exit-policy", "monitor"])
        self.assertEqual(rc, 2)
        self.assertEqual(result["failure_class"], "IMPLEMENTATION_DEPENDENCY_MISSING")
        self.assertEqual(result["operational_status"], "OPERATIONAL_FAIL")

    def test_unexpected_pipeline_failure_is_not_swallowed(self):
        self.dependencies()
        with patch.object(gate, "run_pipeline", side_effect=RuntimeError("offline fixture")):
            rc, result = self.run_main(["--exit-policy", "monitor"])
        self.assertEqual(rc, 1)
        self.assertEqual(result["failure_class"], "OPERATIONAL_FAILURE")
        self.assertEqual(result["status"], "fail")

    def test_unrecognized_or_partial_pipeline_result_cannot_claim_success(self):
        self.dependencies()
        for steps in ([], [{"returncode": 0}], [{"returncode": 2, "reason": "HOLD_UNKNOWN"}]):
            with self.subTest(steps=steps), patch.object(gate, "run_pipeline", return_value=steps):
                rc, result = self.run_main(["--exit-policy", "monitor"])
            self.assertNotEqual(rc, 0)
            self.assertEqual(result["operational_status"], "OPERATIONAL_FAIL")

    def test_post_outcome_and_restart_never_lock_or_authorize_forecast(self):
        self.dependencies()
        for value in ("race_result", "post_event", "race_result"):
            rc, result = self.run_main(["--mode", "force_validation", "--gate", value, "--exit-policy", "monitor"])
            self.assertEqual(rc, 0)
            self.assertEqual(result["reason"], "HOLD_POST_OUTCOME_NOT_PROSPECTIVE")
            self.assertFalse(result["forecast_eligible"])
            self.assertFalse((self.root / "latest").exists())

    def test_only_scheduled_workflow_uses_monitor_policy_without_error_suppression(self):
        text = (fixtures.ROOT / ".github/workflows/f1-automated-forecast-gate-orchestrator-v1.yml").read_text()
        self.assertIn("github.event_name == 'schedule' && 'monitor' || 'strict'", text)
        self.assertIn('--exit-policy "${EXIT_POLICY}"', text)
        self.assertNotIn("continue-on-error", text)
        self.assertNotIn("|| true", text)


if __name__ == "__main__":
    unittest.main()
