#!/usr/bin/env python3
"""Acceptance tests for F1 1B downstream consumer handoff wiring v24."""
from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any, Dict


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_module(repo_root: Path):
    script = repo_root / "scripts" / "session_data_processor" / "f1_1b_downstream_consumer_handoff_v24.py"
    spec = importlib.util.spec_from_file_location("f1_1b_downstream_consumer_handoff_v24", script)
    if not spec or not spec.loader:
        raise RuntimeError(f"Could not load module from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_clean_repo(root: Path, *, material_change: bool = False, race_session: bool = False) -> None:
    event = {"event_id": "2026_1287_spain_barcelona_catalunya", "race_name": "Spain - Barcelona - Catalunya", "session_name": "Race" if race_session else "Practice 2", "session_key": 11301}
    bundle = {
        "schema_version": "f1_1b_output_contract_v20",
        "generated_at_utc": "2026-06-13T03:00:00Z",
        "run_id": "20260613T030000Z",
        "status": "usable_with_optional_context_gaps",
        "source_backed": True,
        "workbook_ready": True,
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "event": event,
        "source": {"status": "clean", "readiness_quality": "usable_with_optional_context_gaps"},
        "workbook": {"status": "clean", "sandbox_workbook": "history/workbook_kpi_refresh_applier/x/F1_Workbook_KPI_SANDBOX.xlsx"},
        "handoffs": {
            "race_predictions": {"ready_for_use": True, "blocked": False, "source_status": "clean", "workbook_source_status": "clean", "readiness_quality": "usable_with_optional_context_gaps"},
            "fantasy_predictions": {"ready_for_use": True, "blocked": False, "source_status": "clean", "workbook_source_status": "clean", "readiness_quality": "usable_with_optional_context_gaps"},
            "race_reports": {"ready_for_readiness_context": True, "ready_for_full_report": race_session, "blocked": False, "source_status": "clean", "workbook_source_status": "clean", "readiness_quality": "usable_with_optional_context_gaps"},
        },
        "signature": "abc123",
    }
    write_json(root / "latest" / "forecast_bundle_ledger" / "latest_bundle_snapshot.json", bundle)
    write_json(root / "latest" / "last_good_state.json", {"schema_version": "f1_1b_last_good_state_v20", "event": event, "run_id": bundle["run_id"], "signature": "abc123", "promotion_allowed": False})
    write_json(root / "latest" / "material_change" / "material_change_report.json", {"schema_version": "f1_1b_material_change_v20", "material_change_detected": material_change, "notification_recommended": material_change, "event": event, "promotion_allowed": False})
    write_json(root / "latest" / "readiness_handoff" / "combined_readiness_handoff.json", {"schema_version": "f1_1b_combined_readiness_handoff_v20", "event": event, "source_status": "clean", "workbook_status": "clean", "readiness_quality": "usable_with_optional_context_gaps", "handoffs": bundle["handoffs"], "promotion_allowed": False})
    write_json(root / "latest" / "1b_output_contract" / "output_contract_report.json", {"schema_version": "f1_1b_output_contract_report_v20", "status": "pass", "source_status": "clean", "workbook_source_status": "clean", "readiness_quality": "usable_with_optional_context_gaps", "last_good_state_updated": True, "promotion_allowed": False})


def seed_blocked_repo(root: Path) -> None:
    event = {"event_id": "blocked_event", "race_name": "Blocked", "session_name": "Practice 1", "session_key": 1}
    write_json(root / "latest" / "forecast_bundle_ledger" / "latest_bundle_snapshot.json", {
        "run_id": "blocked_run",
        "event": event,
        "source_backed": False,
        "workbook_ready": False,
        "source": {"status": "needs_manual_review", "readiness_quality": "unknown"},
        "workbook": {"status": "needs_manual_review"},
        "handoffs": {},
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
    })
    write_json(root / "latest" / "material_change" / "material_change_report.json", {"material_change_detected": True, "notification_recommended": False, "promotion_allowed": False})
    write_json(root / "latest" / "readiness_handoff" / "combined_readiness_handoff.json", {"handoffs": {}, "promotion_allowed": False})
    write_json(root / "latest" / "1b_output_contract" / "output_contract_report.json", {"status": "blocked", "source_status": "needs_manual_review", "workbook_source_status": "needs_manual_review", "promotion_allowed": False})


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_tests(repo_root: Path) -> Dict[str, str]:
    module = load_module(repo_root)
    results: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seed_clean_repo(root, material_change=True, race_session=False)
        report = module.run(root)
        combined = json.loads((root / "latest" / "downstream_consumers" / "combined_downstream_consumer_manifest.json").read_text(encoding="utf-8"))
        race = json.loads((root / "latest" / "downstream_consumers" / "race_predictions" / "consumer_input.json").read_text(encoding="utf-8"))
        fantasy = json.loads((root / "latest" / "downstream_consumers" / "fantasy_predictions" / "consumer_input.json").read_text(encoding="utf-8"))
        reports = json.loads((root / "latest" / "downstream_consumers" / "race_reports" / "consumer_input.json").read_text(encoding="utf-8"))
        assert_true(report["status"] == "pass", "clean repo should pass")
        assert_true(race["consumer_readiness"] == "ready", "race predictions should be ready")
        assert_true(fantasy["consumer_readiness"] == "ready", "fantasy predictions should be ready")
        assert_true(reports["consumer_readiness"] == "context_ready", "practice report should be context ready, not full report ready")
        assert_true(combined["promotion_allowed"] is False and combined["forecast_gate_activated"] is False, "gates must stay false")
        results["clean_practice_consumers_ready"] = "pass"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seed_clean_repo(root, material_change=False, race_session=True)
        module.run(root)
        reports = json.loads((root / "latest" / "downstream_consumers" / "race_reports" / "consumer_input.json").read_text(encoding="utf-8"))
        material = json.loads((root / "latest" / "downstream_consumers" / "combined_downstream_consumer_manifest.json").read_text(encoding="utf-8"))
        assert_true(reports["consumer_readiness"] == "full_report_ready", "race report should be full_report_ready for race session")
        assert_true(material["consumers"]["race_predictions"]["notification_recommended"] is False, "no material change should stay quiet")
        results["race_session_full_report_ready_and_no_spam"] = "pass"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seed_blocked_repo(root)
        report = module.run(root)
        race = json.loads((root / "latest" / "downstream_consumers" / "race_predictions" / "consumer_input.json").read_text(encoding="utf-8"))
        assert_true(report["status"] == "blocked", "blocked repo should remain blocked")
        assert_true(race["blocked"] is True, "race predictions should be blocked")
        assert_true(race["promotion_allowed"] is False and race["forecast_gate_activated"] is False, "blocked gates must stay false")
        results["blocked_source_blocks_consumers"] = "pass"
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    results = run_tests(repo_root)
    out = repo_root / "latest" / "1b_validation" / "v24_downstream_consumer_acceptance_tests.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "f1_1b_v24_downstream_consumer_acceptance", "status": "pass", "tests": results, "promotion_allowed": False, "forecast_gate_activated": False}
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
