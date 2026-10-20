#!/usr/bin/env python3
"""Focused fail-closed regression tests for the readiness dashboard publisher."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "dashboard_connector" / "publish_forecast_fantasy_readiness_dashboards_v1.py"
SPEC = importlib.util.spec_from_file_location("dashboard_publisher", MODULE_PATH)
assert SPEC and SPEC.loader
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
EVENT_ID = "2026_1297_united_states_austin_austin"
SESSION_KEY = 11390
PROCESSOR = f"latest/session_data_processor/{EVENT_ID}/practice_2_{SESSION_KEY}"


def write_json(root: Path, relative: str, value: object) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def fixture_payloads() -> dict[str, dict]:
    session = {
        "date_start": "2026-10-18T10:00:00+00:00",
        "date_end": "2026-10-18T11:00:00+00:00",
        "gate": "post_fp2",
        "meeting_key": 1297,
        "session_key": SESSION_KEY,
        "session_name": "Practice 2",
        "session_type": "Practice",
    }
    required = {
        f"openf1_{endpoint}": {
            "endpoint": endpoint,
            "role": "required",
            "raw_status": "clean",
            "effective_status": "clean",
            "classification": "critical_clean",
            "rows": 20,
            "blocking": False,
            "reason": "required_source_clean",
            "missing_required_columns": [],
            "anomalies": [],
        }
        for endpoint in ("drivers", "laps", "position", "weather")
    }
    ledger = {
        "schema_version": "forecast_bundle_ledger_session_snapshot_v1",
        "created_utc": "2026-10-18T11:15:00Z",
        "event_id": EVENT_ID,
        "overall_status": "clean",
        "promotion_allowed": False,
        "race_name": "United States - Austin",
        "recommended_forecast_action": "refresh readiness/confidence/risk state only",
        "session": session,
    }
    aggregation = {
        "schema_version": "source_readiness_aggregation_v2",
        "overall_status": "clean",
        "readiness_quality": "usable_clean",
        "needs_manual_review": False,
        "critical_endpoints": ["drivers", "laps", "position", "weather"],
        "missing_required_endpoints": [],
        "blocking_issues": [],
        "critical_late": [],
        "critical_partial": [],
        "optional_context_gaps": [],
        "per_source": required,
    }
    source_manifest = {
        "schema_version": "session_processor_result_v2",
        "created_utc": "2026-10-18T11:15:00Z",
        "event_id": EVENT_ID,
        "race_name": "United States - Austin",
        "session": session,
        "overall_status": "clean",
        "readiness_aggregation": aggregation,
        "forecast_bundle_ledger_snapshot": ledger,
    }
    selector = {
        "schema_version": "latest_manifest_v2_session_processor",
        "event_id": EVENT_ID,
        "session_key": SESSION_KEY,
        "session_name": "Practice 2",
        "overall_status": "clean",
        "latest_session_data_processor_manifest": f"{PROCESSOR}/source_readiness_manifest.json",
        "updated_utc": "2026-10-18T11:15:00Z",
    }
    readiness = {
        "schema_version": "data_readiness_v2_session_processor",
        "event_id": EVENT_ID,
        "race_name": "United States - Austin",
        "session": session,
        "overall_status": "clean",
        "readiness_quality": "usable_clean",
        "sources": {name: {"rows": value["rows"], "status": "clean"} for name, value in required.items()},
        "updated_utc": "2026-10-18T11:15:00Z",
    }
    combined = {
        "schema_version": "combined_source_manifest_v2_session_processor",
        "event_id": EVENT_ID,
        "session_key": SESSION_KEY,
        "overall_status": "clean",
        "readiness_quality": "usable_clean",
        "source_layers": {"session_data_processor": f"{PROCESSOR}/source_readiness_manifest.json"},
        "updated_utc": "2026-10-18T11:15:00Z",
    }
    workbook = {
        "created_utc": "2026-10-18T11:20:00Z",
        "commit_allowed": True,
        "source_status": "clean",
        "source_processor_root": PROCESSOR,
        "outputs": [
            {
                "path": "history/workbook_kpi_refresh_applier/20261018T112000Z/F1_Workbook_KPI_SANDBOX_Refresh_Austin_session.xlsx",
                "sha256": "synthetic",
            }
        ],
    }
    return {
        "selector": selector,
        "readiness": readiness,
        "combined": combined,
        "source": source_manifest,
        "ledger": ledger,
        "workbook": workbook,
    }


def install_fixture(root: Path, payloads: dict[str, dict] | None = None) -> dict[str, dict]:
    payloads = copy.deepcopy(payloads or fixture_payloads())
    write_json(root, "latest/latest_manifest.json", payloads["selector"])
    write_json(root, "latest/data_readiness.json", payloads["readiness"])
    write_json(root, "latest/combined_source_manifest.json", payloads["combined"])
    write_json(root, f"{PROCESSOR}/source_readiness_manifest.json", payloads["source"])
    write_json(root, f"{PROCESSOR}/forecast_bundle_ledger_snapshot.json", payloads["ledger"])
    write_json(root, "latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json", payloads["workbook"])
    workbook = root / payloads["workbook"]["outputs"][0]["path"]
    workbook.parent.mkdir(parents=True, exist_ok=True)
    workbook.write_bytes(b"synthetic workbook")
    return payloads


def set_overall_status(payloads: dict[str, dict], status: str) -> None:
    for name in ("selector", "readiness", "combined", "source", "ledger"):
        payloads[name]["overall_status"] = status
    payloads["workbook"]["source_status"] = status
    payloads["source"]["readiness_aggregation"]["overall_status"] = status


class DashboardEventSelectionReadinessTests(unittest.TestCase):
    def test_newer_historical_mtime_cannot_displace_authoritative_current_event(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            install_fixture(root)
            historical = write_json(
                root,
                "latest/session_data_processor/2026_1308_bahrain_kuala_lumpur_kuala_lumpur/race_11731/source_readiness_manifest.json",
                {"event_id": "2026_1308_bahrain_kuala_lumpur_kuala_lumpur", "overall_status": "clean"},
            )
            os.utime(historical, (2_000_000_000, 2_000_000_000))

            result = publisher.discover_state(root, NOW)

            self.assertEqual(result["event_id"], EVENT_ID)
            self.assertEqual(result["event_name"], "United States - Austin")
            self.assertTrue(result["race_predictions"]["ready_for_use"])

    def test_missing_current_event_evidence_is_not_ready_without_historical_fallback(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            install_fixture(root)
            (root / "latest" / "latest_manifest.json").unlink()
            historical = write_json(root, "latest/session_data_processor/historical/source_readiness_manifest.json", {"overall_status": "clean"})
            os.utime(historical, (2_000_000_000, 2_000_000_000))

            result = publisher.discover_state(root, NOW)

            self.assertEqual(result["event_name"], "unknown event")
            self.assertFalse(result["source_backed"])
            self.assertFalse(result["downstream_eligible"])

    def test_session_or_meeting_identity_mismatch_is_not_ready(self):
        for field, value, expected_reason in (
            ("session_key", 99999, "data_readiness_session_mismatch"),
            ("meeting_key", 9999, "data_readiness_meeting_mismatch"),
        ):
            with self.subTest(field=field), TemporaryDirectory() as td:
                root = Path(td)
                payloads = fixture_payloads()
                payloads["readiness"]["session"][field] = value
                install_fixture(root, payloads)
                result = publisher.discover_state(root, NOW)
                self.assertFalse(result["downstream_eligible"])
                self.assertIn(expected_reason, result["readiness_reasons"])

    def test_needs_manual_review_never_becomes_ready_for_use(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            payloads = fixture_payloads()
            set_overall_status(payloads, "needs_manual_review")
            aggregation = payloads["source"]["readiness_aggregation"]
            aggregation["readiness_quality"] = "blocked_manual_review_required_source"
            aggregation["needs_manual_review"] = True
            aggregation["blocking_issues"] = [{"endpoint": "weather", "reason": "required_source_needs_manual_review"}]
            install_fixture(root, payloads)

            result = publisher.discover_state(root, NOW)

            self.assertFalse(result["source_backed"])
            self.assertFalse(result["race_predictions"]["ready_for_use"])
            self.assertFalse(result["fantasy_predictions"]["ready_for_use"])

    def test_missing_conflicting_and_late_required_evidence_remains_blocked(self):
        cases = (
            ("missing", "not_ready_no_data", "readiness_missing_required_endpoints"),
            ("conflicting", "blocked_conflicting_required_source", "readiness_blocking_issues"),
            ("late", "not_ready_required_source_late", "readiness_critical_late"),
        )
        for status, quality, reason in cases:
            with self.subTest(status=status), TemporaryDirectory() as td:
                root = Path(td)
                payloads = fixture_payloads()
                set_overall_status(payloads, status)
                aggregation = payloads["source"]["readiness_aggregation"]
                aggregation["readiness_quality"] = quality
                if status == "missing":
                    aggregation["missing_required_endpoints"] = ["weather"]
                elif status == "conflicting":
                    aggregation["blocking_issues"] = [{"endpoint": "weather", "reason": "required_source_conflicting"}]
                else:
                    aggregation["critical_late"] = [{"endpoint": "weather", "reason": "required_source_late_or_empty"}]
                install_fixture(root, payloads)
                result = publisher.discover_state(root, NOW)
                self.assertFalse(result["downstream_eligible"])
                self.assertIn(reason, result["readiness_reasons"])

    def test_verified_clean_current_session_is_ready(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            install_fixture(root)
            result = publisher.discover_state(root, NOW)
            self.assertTrue(result["source_backed"])
            self.assertTrue(result["downstream_eligible"])
            self.assertEqual(result["readiness_reasons"], ["verified_current_session_evidence"])

    def test_explicit_required_partial_policy_is_honoured(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            payloads = fixture_payloads()
            set_overall_status(payloads, "partial")
            aggregation = payloads["source"]["readiness_aggregation"]
            aggregation["readiness_quality"] = "usable_with_required_source_partial"
            weather = aggregation["per_source"]["openf1_weather"]
            weather.update({
                "raw_status": "partial",
                "effective_status": "partial",
                "classification": "critical_partial",
                "reason": "required_source_partial_but_usable",
                "missing_required_columns": ["humidity"],
            })
            aggregation["critical_partial"] = [{"endpoint": "weather", "reason": "required_source_partial_but_usable"}]
            payloads["readiness"]["readiness_quality"] = "usable_with_required_source_partial"
            payloads["readiness"]["sources"]["openf1_weather"]["status"] = "partial"
            payloads["combined"]["readiness_quality"] = "usable_with_required_source_partial"
            install_fixture(root, payloads)

            result = publisher.discover_state(root, NOW)

            self.assertTrue(result["source_backed"])
            self.assertTrue(result["downstream_eligible"])

    def test_diagnostic_publish_permission_does_not_imply_forecast_eligibility(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            payloads = fixture_payloads()
            set_overall_status(payloads, "needs_manual_review")
            aggregation = payloads["source"]["readiness_aggregation"]
            aggregation["readiness_quality"] = "blocked_manual_review_required_source"
            aggregation["needs_manual_review"] = True
            aggregation["blocking_issues"] = [{"endpoint": "weather"}]
            install_fixture(root, payloads)
            result = publisher.discover_state(root, NOW)
            self.assertTrue(result["commit_allowed"])
            self.assertTrue(result["diagnostic_publish_allowed"])
            self.assertFalse(result["downstream_eligible"])

    def test_issue_309_capture_workflow_is_outside_publisher_effects(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            install_fixture(root)
            workflow = root / ".github/workflows/f1-openf1-lightweight-source-closure.yml"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_bytes(b"protected Issue 309 workflow sentinel\n")
            before = hashlib.sha256(workflow.read_bytes()).hexdigest()
            publisher.discover_state(root, NOW)
            after = hashlib.sha256(workflow.read_bytes()).hexdigest()
            self.assertEqual(after, before)

    def test_october_19_historical_workbook_and_stale_selector_fail_closed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            payloads = fixture_payloads()
            singapore = "2026_1296_singapore_marina_bay_singapore"
            singapore_processor = f"latest/session_data_processor/{singapore}/race_11388"
            for state in (payloads["selector"], payloads["readiness"], payloads["combined"], payloads["source"], payloads["ledger"]):
                state["event_id"] = singapore
            for state in (payloads["readiness"]["session"], payloads["source"]["session"], payloads["ledger"]["session"]):
                state.update({"meeting_key": 1296, "session_key": 11388, "date_start": "2026-10-11T12:00:00Z", "date_end": "2026-10-11T14:00:00Z", "session_name": "Race", "session_type": "Race"})
            payloads["selector"].update({
                "session_key": 11388,
                "updated_utc": "2026-10-12T19:47:51Z",
                "latest_session_data_processor_manifest": f"{singapore_processor}/source_readiness_manifest.json",
            })
            payloads["readiness"]["race_name"] = "Singapore - Marina Bay - Singapore"
            payloads["combined"].update({"session_key": 11388, "source_layers": {"session_data_processor": f"{singapore_processor}/source_readiness_manifest.json"}})
            payloads["workbook"].update({
                "source_status": "needs_manual_review",
                "source_processor_root": "latest/session_data_processor/2026_1308_bahrain_kuala_lumpur_kuala_lumpur/race_11731",
            })

            write_json(root, "latest/latest_manifest.json", payloads["selector"])
            write_json(root, "latest/data_readiness.json", payloads["readiness"])
            write_json(root, "latest/combined_source_manifest.json", payloads["combined"])
            write_json(root, f"{singapore_processor}/source_readiness_manifest.json", payloads["source"])
            write_json(root, f"{singapore_processor}/forecast_bundle_ledger_snapshot.json", payloads["ledger"])
            write_json(root, "latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json", payloads["workbook"])
            workbook = root / payloads["workbook"]["outputs"][0]["path"]
            workbook.parent.mkdir(parents=True, exist_ok=True)
            workbook.write_bytes(b"historical Bahrain workbook")

            result = publisher.discover_state(root, NOW)

            self.assertEqual(result["event_name"], "unknown event")
            self.assertFalse(result["source_backed"])
            self.assertFalse(result["downstream_eligible"])
            self.assertIn("stale_authoritative_session", result["readiness_reasons"])
            self.assertIn("workbook_event_session_mismatch", result["readiness_reasons"])


if __name__ == "__main__":
    unittest.main()
