"""Source-gap monitoring never weakens the historical archive publish guard."""
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.ops import f1_openf1_scheduled_source_hold_monitor_v1 as monitor


class SourceHoldMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "data").mkdir()
        for name, payload in (
            ("request_log.csv", "endpoint,status\nstarting_grid,http_404\n"),
            ("data/target_sessions.csv", "session_key,is_cancelled\n11234,False\n"),
            ("combined_source_manifest.csv", "lane,result\nstarting_grid,fail\n"),
            ("zero_lane_diagnostics.csv",
             "lane,session_key,status,reason,request_statuses\n"
             "starting_grid,11234,fail,required_session_http_404,http_404\n"),
        ):
            (self.root / name).write_text(payload, encoding="utf-8")
        normal = {
            "source_readiness_promoted": False,
            "prospective_forecast_eligibility_established": False,
            "request_budget": {"deferred_reason": None, "restriction_events": []},
        }
        for field, name in {
            "request_log_sha256": "request_log.csv",
            "target_sessions_sha256": "data/target_sessions.csv",
            "combined_source_manifest_sha256": "combined_source_manifest.csv",
            "zero_lane_diagnostics_sha256": "zero_lane_diagnostics.csv",
        }.items():
            normal[field] = hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        self.manifest = {
            "collection_scope": "historical_season",
            "completed_only": True,
            "publication_eligible": False,
            "source_quality_status": "hold",
            "historical_archive_complete": False,
            "official_final_grid_verified": False,
            "session_discovery_status": "pass",
            "source_quality_reasons": ["required_lane_session_failures:1"],
            "lanes": [{"lane": "starting_grid", "result": "fail"}],
            "fail_count": 1,
            "normal_collection": normal,
        }
        self.save()

    def save(self):
        (self.root / "latest_manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")

    def test_real_historical_no_results_is_visible_nonpublishing_hold(self):
        result = monitor.assess(self.root)
        self.assertEqual(result["status"], "HOLD_HISTORICAL_PROVIDER_404")
        self.assertFalse(result["publication_eligible"])
        self.assertFalse(result["forecast_eligible"])
        self.assertFalse(result["prediction_locked"])

    def test_provider_throttling_remains_operational_failure(self):
        self.manifest["normal_collection"]["request_budget"]["restriction_events"] = [
            "provider_rate_limited_http_429"]
        self.save()
        with self.assertRaises(monitor.UnsafeSourceHold):
            monitor.assess(self.root)

    def test_unexplained_coverage_regression_remains_failure(self):
        self.manifest["source_quality_reasons"].append(
            "completed_session_coverage_regression:11234")
        self.save()
        with self.assertRaises(monitor.UnsafeSourceHold):
            monitor.assess(self.root)

    def test_missing_or_mutated_original_diagnostics_remains_failure(self):
        (self.root / "zero_lane_diagnostics.csv").write_text("corrupt")
        with self.assertRaises(monitor.UnsafeSourceHold):
            monitor.assess(self.root)

    def test_changed_404_to_401_does_not_pass_even_with_rehashed_data(self):
        p = self.root / "zero_lane_diagnostics.csv"
        p.write_text(p.read_text().replace("http_404", "http_401"))
        self.manifest["normal_collection"]["zero_lane_diagnostics_sha256"] = (
            hashlib.sha256(p.read_bytes()).hexdigest())
        self.save()
        with self.assertRaises(monitor.UnsafeSourceHold):
            monitor.assess(self.root)

    def test_do_not_reclassify_missing_weather_as_benign_grid_gap(self):
        p = self.root / "zero_lane_diagnostics.csv"
        p.write_text(p.read_text().replace("starting_grid", "weather"))
        self.manifest["normal_collection"]["zero_lane_diagnostics_sha256"] = (
            hashlib.sha256(p.read_bytes()).hexdigest())
        self.manifest["lanes"][0]["lane"] = "weather"
        self.save()
        with self.assertRaises(monitor.UnsafeSourceHold):
            monitor.assess(self.root)

    def test_grid_404_does_not_hide_missing_required_weather(self):
        p = self.root / "zero_lane_diagnostics.csv"
        p.write_text(
            p.read_text() + "weather,11254,fail,required_session_http_404,http_404\\n"
        )
        self.manifest["normal_collection"]["zero_lane_diagnostics_sha256"] = (
            hashlib.sha256(p.read_bytes()).hexdigest())
        self.manifest["lanes"].append({"lane": "weather", "result": "fail"})
        self.manifest["fail_count"] = 2
        self.manifest["source_quality_reasons"] = ["required_lane_session_failures:2"]
        self.save()
        with self.assertRaises(monitor.UnsafeSourceHold):
            monitor.assess(self.root)

    def test_no_forecast_or_archive_promotion(self):
        self.manifest["normal_collection"]["source_readiness_promoted"] = True
        self.save()
        with self.assertRaises(monitor.UnsafeSourceHold):
            monitor.assess(self.root)

    def test_operator_summary_and_publish_guard_output(self):
        summary = self.root / "summary.md"
        output = self.root / "gha_output"
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary),
                                      "GITHUB_OUTPUT": str(output)}), patch(
                "sys.argv", ["monitor", "--root", str(self.root)]):
            self.assertEqual(monitor.main(), 0)
        self.assertIn("HOLD", summary.read_text())
        self.assertIn("publish_eligible=false", output.read_text())


if __name__ == "__main__":
    unittest.main()
