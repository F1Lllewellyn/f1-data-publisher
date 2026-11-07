"""Cross-component regression: current-session freshness, not just clean FP3.

No provider requests, workflows, stable model or workbook writes. Tests use a
temporary synthetic source chain and the unchanged modules' public functions.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
EVENT = "2026_1299_brazil_s_o_paulo_interlagos"
SESSION_REL = f"latest/session_data_processor/{EVENT}/practice_3_11407/source_readiness_manifest.json"
SCHEDULE_REL = f"latest/session_data_processor/{EVENT}/session_schedule_snapshot.json"
WORKBOOK_REL = "latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_TEST.xlsx"
FP3 = {
    "meeting_key": 1299, "session_key": 11407, "session_name": "Practice 3",
    "session_type": "Practice", "date_start": "2026-11-07T14:30:00Z",
    "date_end": "2026-11-07T15:30:00Z", "gate": "post_fp3",
}
QUALI = {
    "meeting_key": 1299, "session_key": 11408, "session_name": "Qualifying",
    "session_type": "Qualifying", "date_start": "2026-11-07T18:00:00Z",
    "date_end": "2026-11-07T19:00:00Z",
}


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


dashboard_mod = load_module(
    "sp2026_dashboard", "scripts/dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py"
)
processor_mod = load_module(
    "sp2026_processor", "scripts/session_data_processor/session_data_processor_loop_v1.py"
)
peak_mod = load_module("sp2026_peak", "scripts/ops/f1_peak_elite_orchestrator_v1.py")


class CurrentSessionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fixture()

    def put(self, relative, obj):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj), encoding="utf-8")

    def fixture(self):
        required = ("drivers", "laps", "position", "weather")
        per_source = {
            f"openf1_{key}": {
                "endpoint": key, "role": "required", "blocking": False,
                "rows": 22, "effective_status": "clean", "raw_status": "clean",
            }
            for key in required
        }
        aggregate = {
            "overall_status": "clean", "readiness_quality": "usable_clean",
            "needs_manual_review": False, "blocking_issues": [], "critical_late": [],
            "missing_required_endpoints": [], "critical_endpoints": list(required),
            "per_source": per_source,
        }
        self.put(SESSION_REL, {
            "event_id": EVENT, "session": FP3, "overall_status": "clean",
            "readiness_aggregation": aggregate,
        })
        self.put(SESSION_REL.replace("source_readiness_manifest.json", "forecast_bundle_ledger_snapshot.json"), {
            "event_id": EVENT, "session": FP3, "overall_status": "clean",
        })
        self.put("latest/latest_manifest.json", {
            "event_id": EVENT, "session_key": 11407, "session_name": "Practice 3",
            "overall_status": "clean", "updated_utc": "2026-11-07T17:00:49Z",
            "latest_session_data_processor_manifest": SESSION_REL,
            "session_schedule_snapshot": SCHEDULE_REL,
        })
        self.put("latest/data_readiness.json", {
            "event_id": EVENT, "session": FP3, "overall_status": "clean",
            "readiness_quality": "usable_clean",
            "sources": {name: {"rows": v["rows"], "status": "clean"} for name, v in per_source.items()},
        })
        self.put("latest/combined_source_manifest.json", {
            "event_id": EVENT, "session_key": 11407, "overall_status": "clean",
            "readiness_quality": "usable_clean",
            "source_layers": {"session_data_processor": SESSION_REL},
        })
        self.put("latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json", {
            "source_processor_root": str(Path(SESSION_REL).parent),
            "source_status": "clean", "outputs": [{"path": WORKBOOK_REL}],
        })
        workbook_path = self.root / WORKBOOK_REL
        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        workbook_path.write_bytes(b"synthetic sandbox artifact")
        self.put(SCHEDULE_REL, {
            "schema_version": "meeting_schedule_snapshot_v1",
            "source": "OpenF1 sessions catalog",
            "event_id": EVENT, "meeting_key": 1299,
            "observed_at_utc": "2026-11-07T17:00:48Z",
            "source_fetch": {"ok": True, "status_code": 200},
            "sessions": [FP3, QUALI],
        })

    def observe(self, iso_time):
        t = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return dashboard_mod.discover_state(self.root, reference_time=t)

    def test_fp3_valid_before_qualifying_completed(self):
        d = self.observe("2026-11-07T18:30:00Z")
        self.assertTrue(d["downstream_eligible"], d["readiness_reasons"])
        self.assertEqual(d["expected_session_key"], 11407)

    def test_fp3_clean_but_stale_after_qualifying(self):
        d = self.observe("2026-11-07T20:30:00Z")
        self.assertFalse(d["downstream_eligible"])
        self.assertFalse(d["race_predictions"]["ready_for_use"])
        self.assertFalse(d["fantasy_predictions"]["ready_for_use"])
        self.assertEqual(d["expected_session_key"], 11408)
        self.assertIn("hold_stale_session_newer_completed", d["readiness_reasons"])
        self.assertEqual(d["source_status"], "clean")  # Evidence remains truthful.

    def test_missing_schedule_fail_closed(self):
        (self.root / SCHEDULE_REL).unlink()
        d = self.observe("2026-11-07T18:30:00Z")
        self.assertFalse(d["downstream_eligible"])
        self.assertIn("invalid_session_schedule_provenance", d["readiness_reasons"])

    def test_misbound_schedule_event_fail_closed(self):
        schedule = json.loads((self.root / SCHEDULE_REL).read_text(encoding="utf-8"))
        schedule["event_id"] = "2026_1298_wrong_meeting"
        self.put(SCHEDULE_REL, schedule)
        d = self.observe("2026-11-07T18:30:00Z")
        self.assertFalse(d["downstream_eligible"])
        self.assertIn("invalid_session_schedule_provenance", d["readiness_reasons"])

    def test_invalid_same_meeting_date_fail_closed(self):
        schedule = json.loads((self.root / SCHEDULE_REL).read_text(encoding="utf-8"))
        schedule["sessions"][1]["date_end"] = "invalid"
        self.put(SCHEDULE_REL, schedule)
        d = self.observe("2026-11-07T20:30:00Z")
        self.assertFalse(d["downstream_eligible"])
        self.assertIn("invalid_session_schedule_entry", d["readiness_reasons"])

    def test_future_observation_cannot_prove_past_readiness(self):
        schedule = json.loads((self.root / SCHEDULE_REL).read_text(encoding="utf-8"))
        schedule["observed_at_utc"] = "2026-11-08T05:00:00Z"
        self.put(SCHEDULE_REL, schedule)
        d = self.observe("2026-11-07T20:30:00Z")
        self.assertFalse(d["downstream_eligible"])
        self.assertIn("future_session_schedule_observation", d["readiness_reasons"])


class SnapshotAndOrchestratorTests(unittest.TestCase):
    def test_processor_writes_bounded_meeting_schedule_in_both_custodies(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(processor_mod, "ROOT", Path(tmp)):
                other = {**FP3, "meeting_key": 9999, "session_key": 99999}
                relative = processor_mod.write_session_schedule_snapshot(
                    [FP3, QUALI, other], FP3, EVENT, "20261107T170049Z",
                    catalog_observed_at_utc="2026-11-07T17:00:48Z",
                    sessions_fetch={"ok": True, "status_code": 200}
                )
                self.assertEqual(relative, SCHEDULE_REL)
                snapshot = json.loads((Path(tmp) / relative).read_text(encoding="utf-8"))
                historic = Path(tmp) / "history/session_data_processor" / EVENT / "20261107T170049Z/session_schedule_snapshot.json"
                self.assertEqual(snapshot, json.loads(historic.read_text(encoding="utf-8")))
                self.assertEqual([s["session_key"] for s in snapshot["sessions"]], [11407, 11408])
                self.assertFalse(snapshot["promotion_allowed"])
                self.assertFalse(snapshot["official_final_grid_verified"])

    def test_processor_rejects_invalid_schedule_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(processor_mod, "ROOT", Path(tmp)):
                with self.assertRaises(ValueError):
                    processor_mod.write_session_schedule_snapshot([QUALI], FP3, EVENT, "test")

    def test_optional_peak_failure_not_falsely_green(self):
        with patch.object(
            peak_mod.subprocess, "run",
            return_value=subprocess.CompletedProcess(["synthetic"], 7, stdout="no-source"),
        ):
            outcome = peak_mod.run(Path("."), "synthetic soft failure", ["synthetic"], allow_fail=True)
        self.assertEqual(outcome["returncode"], 7)
        self.assertFalse(outcome["ok"])
        self.assertTrue(outcome["allow_fail"])


if __name__ == "__main__":
    unittest.main()
