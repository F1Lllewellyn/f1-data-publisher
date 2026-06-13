#!/usr/bin/env python3
"""F1 Peak-Elite Orchestrator v1.

One-button orchestration layer for the F1 Prediction Engine GitHub automation
system. It repairs workflow syntax when asked, validates the automation layer,
runs the source-backed session -> workbook/KPI -> readiness chain, and writes a
machine-readable status for ChatGPT/Race/Fantasy chats.

Hard guards: no stable-engine modification, no canonical workbook overwrite, no
model promotion, no forced push, no prediction execution/change by itself.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

PROTECTED_STABLE = "Engine_2026-06-07_STABLE"
PROTECTED_WORKBOOKS = [
    "F1_2026_Prediction_Model_Data_Workbook.xlsx",
    "F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx",
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def run(repo: Path, label: str, cmd: List[str], timeout: int = 1200, allow_fail: bool = False) -> Dict[str, Any]:
    print(f"\n--- {label} ---")
    print(" ".join(cmd))
    started = iso_now()
    try:
        proc = subprocess.run(cmd, cwd=str(repo), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        print(proc.stdout[-8000:])
        return {
            "label": label,
            "cmd": cmd,
            "started_utc": started,
            "finished_utc": iso_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0 or allow_fail,
            "allow_fail": allow_fail,
            "output_tail": proc.stdout[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {"label": label, "cmd": cmd, "started_utc": started, "finished_utc": iso_now(), "returncode": 124, "ok": False, "timeout": True, "output_tail": str(exc)[-4000:]}
    except Exception as exc:
        return {"label": label, "cmd": cmd, "started_utc": started, "finished_utc": iso_now(), "returncode": 1, "ok": False, "exception": repr(exc), "output_tail": repr(exc)}


def protected_touched(repo: Path) -> List[str]:
    git = shutil.which("git")
    if not git:
        return []
    proc = subprocess.run([git, "status", "--porcelain"], cwd=str(repo), text=True, capture_output=True)
    touched: List[str] = []
    for line in proc.stdout.splitlines():
        rel = line[3:].strip() if len(line) > 3 else line.strip()
        if PROTECTED_STABLE.lower() in rel.lower() or any(w.lower() in rel.lower() for w in PROTECTED_WORKBOOKS):
            touched.append(rel)
    return touched


def build_plain_report(result: Dict[str, Any]) -> str:
    steps = result.get("steps", [])
    step_lines = [f"- `{s.get('label')}`: {'PASS' if s.get('ok') else 'FAIL'} (`{s.get('returncode')}`)" for s in steps]
    if not step_lines:
        step_lines = ["- None"]
    latest = result.get("latest_state", {})
    return "\n".join([
        "# F1 Peak-Elite Orchestrator Report",
        "",
        f"Created UTC: `{result.get('created_utc')}`",
        f"Operation: `{result.get('operation')}`",
        f"Status: **{result.get('status')}**",
        "",
        "## Latest source state",
        f"- Race/event: `{latest.get('race_name')}`",
        f"- Session: `{latest.get('session_name')}`",
        f"- Source status: `{latest.get('source_status')}`",
        f"- Workbook source status: `{latest.get('workbook_source_status')}`",
        f"- Workbook commit allowed: `{latest.get('workbook_commit_allowed')}`",
        "",
        "## Steps",
        *step_lines,
        "",
        "## Governance",
        "- Stable engine modified: `false`",
        "- Canonical workbook overwritten: `false`",
        "- Model promotion: `false`",
        "- 2026 no-DRS rule: active by project governance; this layer does not create DRS assumptions",
        "",
        "## Interpretation",
        result.get("plain_english", "No interpretation available."),
        "",
    ])


def latest_state(repo: Path) -> Dict[str, Any]:
    readiness = read_json(repo / "latest" / "data_readiness.json", {})
    workbook = read_json(repo / "latest" / "workbook_kpi_refresh_applier" / "workbook_kpi_refresh_manifest.json", {})
    session = readiness.get("session") if isinstance(readiness.get("session"), dict) else {}
    return {
        "race_name": readiness.get("race_name"),
        "event_id": readiness.get("event_id"),
        "session_name": session.get("session_name"),
        "source_status": readiness.get("overall_status") or readiness.get("overall_classification"),
        "source_needs_manual_review": bool(readiness.get("needs_manual_review", False)),
        "workbook_source_status": workbook.get("source_status"),
        "workbook_commit_allowed": bool(workbook.get("commit_allowed", False)),
        "workbook_artifacts": [o.get("path") for o in workbook.get("outputs", []) if isinstance(o, dict)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--operation", default="full_safe_chain", choices=["health_only", "syntax_repair_only", "full_safe_chain", "full_run_chain", "scheduled_monitor"])
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--session-filter", default="auto")
    parser.add_argument("--run-forecast-gate", default="false")
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    runtime = repo / "_runtime" / "peak_elite" / "orchestrator"
    latest = repo / "latest" / "peak_elite"
    runtime.mkdir(parents=True, exist_ok=True)
    latest.mkdir(parents=True, exist_ok=True)
    steps: List[Dict[str, Any]] = []
    py = sys.executable

    operation = args.operation
    if operation in {"syntax_repair_only", "full_safe_chain", "full_run_chain", "scheduled_monitor"}:
        steps.append(run(repo, "workflow_commit_block_repair", [py, "scripts/ops/f1_workflow_commit_block_repair_v1.py", "--repo-root", str(repo), "--apply"], timeout=300))

    if operation in {"health_only", "syntax_repair_only", "full_safe_chain", "full_run_chain", "scheduled_monitor"}:
        steps.append(run(repo, "workflow_static_validation", [py, "scripts/ops/f1_workflow_static_validator_v2.py", "--repo-root", str(repo)], timeout=300))
        if (repo / "scripts/ops/f1_workflow_meta_health_check_v1.py").exists():
            steps.append(run(repo, "workflow_meta_health_v1", [py, "scripts/ops/f1_workflow_meta_health_check_v1.py"], timeout=300))

    if operation in {"full_safe_chain", "scheduled_monitor"}:
        steps.append(run(repo, "peak_elite_health_safe", [py, "scripts/ops/f1_peak_elite_health_v1.py", "--repo-root", str(repo), "--run-safe-tests", "true"], timeout=600, allow_fail=(operation == "scheduled_monitor")))

    if operation == "full_run_chain":
        steps.append(run(repo, "session_data_processor_run_now", [py, "scripts/session_data_processor/session_data_processor_loop_v1.py", "--mode", "run_now", "--season", str(args.season), "--session-filter", args.session_filter], timeout=1500, allow_fail=True))
        steps.append(run(repo, "workbook_kpi_refresh_apply", [py, "scripts/workbook_kpi_refresh/apply_workbook_kpi_refresh_v1.py", "--repo-root", str(repo)], timeout=900, allow_fail=True))
        steps.append(run(repo, "dashboard_readiness_publish", [py, "scripts/dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py", "--mode", "run_now"], timeout=600, allow_fail=True))
        if str(args.run_forecast_gate).lower() in {"true", "1", "yes"}:
            steps.append(run(repo, "forecast_gate_orchestrator", [py, "scripts/forecast_bundles/orchestrate_forecast_gate_pipeline_v1.py", "--mode", "auto", "--season", str(args.season), "--run-source-closure", "true"], timeout=1800, allow_fail=True))
        steps.append(run(repo, "peak_elite_health_after_run", [py, "scripts/ops/f1_peak_elite_health_v1.py", "--repo-root", str(repo), "--run-safe-tests", "true"], timeout=600, allow_fail=True))

    if operation == "health_only":
        steps.append(run(repo, "peak_elite_health_only", [py, "scripts/ops/f1_peak_elite_health_v1.py", "--repo-root", str(repo), "--run-safe-tests", "true"], timeout=600))

    if (repo / "scripts/ops/f1_peak_elite_cleanup_report_v1.py").exists() and operation in {"full_safe_chain", "full_run_chain", "health_only"}:
        steps.append(run(repo, "cleanup_inventory_report_only", [py, "scripts/ops/f1_peak_elite_cleanup_report_v1.py", "--repo-root", str(repo)], timeout=600, allow_fail=True))

    protected = protected_touched(repo)
    hard_failed = [s for s in steps if not s.get("ok")]
    state = latest_state(repo)
    source_status = str(state.get("source_status") or "missing")
    workbook_status = str(state.get("workbook_source_status") or "missing")
    if protected:
        status = "fail"
        plain = "Protected stable engine or canonical workbook files appear modified. The run is blocked until reviewed."
    elif hard_failed:
        status = "fail"
        plain = "The orchestration layer failed before reaching production-ready state. Review the failed step tails in the runtime artifact."
    elif operation == "syntax_repair_only":
        status = "pass"
        plain = "Workflow syntax repair and validation completed. This fixes the blocker before data-processing work resumes."
    elif source_status in {"missing", "unknown", "", "None"}:
        status = "pass_with_warnings"
        plain = "Automation health is available, but latest source readiness is not populated. Watchers may be running before source data exists."
    elif "manual" in source_status.lower() or "partial" in source_status.lower() or "late" in source_status.lower():
        status = "pass_with_warnings"
        plain = "The processor produced source-backed artifacts, but readiness is not clean. Use as confidence/risk context, not automatic stable-prediction promotion."
    else:
        status = "pass"
        plain = "Workflow health, source readiness, and workbook/KPI handoff are aligned. Stable engine remains protected."

    result = {
        "created_utc": iso_now(),
        "operation": operation,
        "status": status,
        "plain_english": plain,
        "latest_state": state,
        "steps": steps,
        "failed_steps": [s.get("label") for s in hard_failed],
        "protected_modified": protected,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "commit_allowed": False if protected or hard_failed else True,
    }
    write_json(runtime / "peak_elite_orchestrator_result.json", result)
    write_json(latest / "orchestrator_status.json", result)
    report_md = build_plain_report(result)
    (runtime / "PEAK_ELITE_ORCHESTRATOR_REPORT.md").write_text(report_md, encoding="utf-8")
    (latest / "ORCHESTRATOR_STATUS.md").write_text(report_md, encoding="utf-8")
    chat_dir = repo / "latest" / "chat_context"
    chat_dir.mkdir(parents=True, exist_ok=True)
    (chat_dir / "PEAK_ELITE_ORCHESTRATOR_BRIEF.md").write_text(report_md, encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
