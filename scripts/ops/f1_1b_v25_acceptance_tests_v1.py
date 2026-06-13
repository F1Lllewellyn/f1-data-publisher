#!/usr/bin/env python3
"""Acceptance tests for F1 1B consumer context publisher + trigger governor v25."""
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
    script = repo_root / "scripts" / "session_data_processor" / "f1_1b_consumer_context_publisher_v25.py"
    spec = importlib.util.spec_from_file_location("f1_1b_consumer_context_publisher_v25", script)
    if not spec or not spec.loader:
        raise RuntimeError(f"Could not load module from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_v24_outputs(root: Path, *, material_change: bool, blocked: bool = False, race_session: bool = False) -> None:
    event = {
        "event_id": "2026_1287_spain_barcelona_catalunya",
        "race_name": "Spain - Barcelona - Catalunya",
        "session_name": "Race" if race_session else "Practice 2",
        "session_key": 11301,
    }
    source_status = "needs_manual_review" if blocked else "clean"
    workbook_status = "needs_manual_review" if blocked else "clean"
    readiness_quality = "unknown" if blocked else "usable_with_optional_context_gaps"
    base_ready = not blocked
    consumers = {
        "race_predictions": {
            "consumer": "race_predictions",
            "consumer_readiness": "blocked" if blocked else "ready",
            "ready_for_use": base_ready,
            "blocked": blocked,
            "source_status": source_status,
            "workbook_source_status": workbook_status,
            "readiness_quality": readiness_quality,
            "allowed_effect": "readiness context only",
            "disallowed_effect": "no promotion",
        },
        "fantasy_predictions": {
            "consumer": "fantasy_predictions",
            "consumer_readiness": "blocked" if blocked else "ready",
            "ready_for_use": base_ready,
            "blocked": blocked,
            "source_status": source_status,
            "workbook_source_status": workbook_status,
            "readiness_quality": readiness_quality,
            "allowed_effect": "fantasy context only",
            "disallowed_effect": "no automatic transfer",
        },
        "race_reports": {
            "consumer": "race_reports",
            "consumer_readiness": "blocked" if blocked else ("full_report_ready" if race_session else "context_ready"),
            "ready_for_readiness_context": base_ready,
            "ready_for_full_report": bool(base_ready and race_session),
            "blocked": blocked,
            "source_status": source_status,
            "workbook_source_status": workbook_status,
            "readiness_quality": readiness_quality,
            "allowed_effect": "report context only",
            "disallowed_effect": "no automatic PDF generation",
        },
    }
    downstream = {
        "schema_version": "f1_1b_downstream_consumer_wiring_v24",
        "status": "blocked" if blocked else "pass",
        "event": event,
        "run_id": "20260613T040000Z",
        "source_status": source_status,
        "workbook_source_status": workbook_status,
        "readiness_quality": readiness_quality,
        "consumers": consumers,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }
    bundle = {
        "schema_version": "f1_1b_output_contract_v20",
        "status": "blocked" if blocked else "usable_with_optional_context_gaps",
        "event": event,
        "run_id": "20260613T040000Z",
        "source_backed": base_ready,
        "workbook_ready": base_ready,
        "source": {"status": source_status, "readiness_quality": readiness_quality},
        "workbook": {"status": workbook_status},
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
    }
    write_json(root / "latest" / "downstream_consumers" / "combined_downstream_consumer_manifest.json", downstream)
    for name, payload in consumers.items():
        write_json(root / "latest" / "downstream_consumers" / name / "consumer_input.json", payload)
    write_json(root / "latest" / "forecast_bundle_ledger" / "latest_bundle_snapshot.json", bundle)
    write_json(root / "latest" / "last_good_state.json", {"event": event, "run_id": "20260613T040000Z", "promotion_allowed": False})
    write_json(root / "latest" / "material_change" / "material_change_report.json", {"event": event, "material_change_detected": material_change, "notification_recommended": material_change, "promotion_allowed": False})
    write_json(root / "latest" / "readiness_handoff" / "combined_readiness_handoff.json", {"event": event, "source_status": source_status, "workbook_source_status": workbook_status, "readiness_quality": readiness_quality, "promotion_allowed": False})
    write_json(root / "latest" / "1b_output_contract" / "output_contract_report.json", {"status": "blocked" if blocked else "pass", "source_status": source_status, "workbook_source_status": workbook_status, "readiness_quality": readiness_quality, "promotion_allowed": False})


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_tests(repo_root: Path) -> Dict[str, str]:
    module = load_module(repo_root)
    results: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seed_v24_outputs(root, material_change=False, blocked=False, race_session=False)
        report = module.run(root)
        trigger = read_json(root / "latest" / "consumer_trigger_governor" / "trigger_decision.json")
        notify = read_json(root / "latest" / "notification_routing" / "notification_decision.json")
        race_md = root / "latest" / "chat_context" / "race_predictions_context.md"
        boot = read_json(root / "latest" / "downstream_consumers" / "race_predictions" / "consumer_bootstrap.json")
        assert_true(report["status"] == "pass", "ready/no-change report should pass")
        assert_true(trigger["should_notify"] is False, "no material change should stay quiet")
        assert_true(notify["notification_recommended"] is False, "notification should not be recommended")
        assert_true(race_md.exists(), "race context markdown should exist")
        assert_true(boot["read_only"] is True and boot["promotion_allowed"] is False, "bootstrap must be read-only and no promotion")
        results["ready_no_change_quiet_contexts"] = "pass"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seed_v24_outputs(root, material_change=True, blocked=False, race_session=False)
        module.run(root)
        trigger = read_json(root / "latest" / "consumer_trigger_governor" / "trigger_decision.json")
        summary = (root / "latest" / "notification_routing" / "notification_summary.md").read_text(encoding="utf-8")
        assert_true(trigger["should_notify"] is True, "material change should recommend notification")
        assert_true("External notification sent: false" in summary, "routing remains decision-only")
        results["material_change_recommends_decision_only_notification"] = "pass"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seed_v24_outputs(root, material_change=True, blocked=True, race_session=False)
        module.run(root)
        trigger = read_json(root / "latest" / "consumer_trigger_governor" / "trigger_decision.json")
        race_boot = read_json(root / "latest" / "downstream_consumers" / "race_predictions" / "consumer_bootstrap.json")
        assert_true(trigger["status"] == "blocked", "blocked source should keep trigger blocked")
        assert_true(race_boot["action"] == "blocked", "race bootstrap should be blocked")
        assert_true(trigger["promotion_allowed"] is False and trigger["forecast_gate_activated"] is False, "safety gates must remain false")
        results["blocked_source_blocks_consumers"] = "pass"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seed_v24_outputs(root, material_change=False, blocked=False, race_session=True)
        module.run(root)
        report_md = (root / "latest" / "chat_context" / "race_reports_context.md").read_text(encoding="utf-8")
        report_boot = read_json(root / "latest" / "downstream_consumers" / "race_reports" / "consumer_bootstrap.json")
        assert_true("Consumer readiness: full_report_ready" in report_md, "race report context should show full report readiness")
        assert_true(report_boot["consumer_readiness"] == "full_report_ready", "bootstrap should carry full report readiness")
        results["race_session_report_context_carries_full_readiness"] = "pass"
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    results = run_tests(repo_root)
    out = repo_root / "latest" / "1b_validation" / "v25_consumer_context_acceptance_tests.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "f1_1b_v25_consumer_context_acceptance",
        "status": "pass",
        "tests": results,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
