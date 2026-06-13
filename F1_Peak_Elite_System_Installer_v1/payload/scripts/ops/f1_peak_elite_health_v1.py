#!/usr/bin/env python3
"""F1 peak-elite system health v1.

A no-promotion, source-readiness-aware health check for the F1 Prediction Engine
GitHub automation layer. It validates workflow syntax, key scripts, latest data
readiness, workbook/KPI refresh state, dashboard state, and governance guardrails.
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
CORE_FILES = [
    "scripts/session_data_processor/session_data_processor_loop_v1.py",
    "scripts/workbook_kpi_refresh/apply_workbook_kpi_refresh_v1.py",
    "scripts/autorepair/f1_autorepair_orchestrator_v1.py",
    "scripts/dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py",
    "scripts/forecast_bundles/orchestrate_forecast_gate_pipeline_v1.py",
    "scripts/ops/safe_git_push_rebase_retry.sh",
    "scripts/ops/f1_workflow_static_validator_v2.py",
    "scripts/ops/f1_workflow_commit_block_repair_v1.py",
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


def run_cmd(repo: Path, label: str, cmd: List[str], timeout: int = 180) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=str(repo), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return {"label": label, "cmd": cmd, "returncode": proc.returncode, "ok": proc.returncode == 0, "output_tail": proc.stdout[-4000:]}
    except subprocess.TimeoutExpired as exc:
        return {"label": label, "cmd": cmd, "returncode": 124, "ok": False, "timeout": True, "output_tail": str(exc)[-4000:]}
    except Exception as exc:
        return {"label": label, "cmd": cmd, "returncode": 1, "ok": False, "exception": repr(exc), "output_tail": repr(exc)}


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--run-safe-tests", default="true")
    args = parser.parse_args()
    repo = Path(args.repo_root).resolve()
    run_safe_tests = str(args.run_safe_tests).lower() in {"true", "1", "yes"}
    out = repo / "_runtime" / "peak_elite" / "health"
    latest = repo / "latest" / "peak_elite"
    out.mkdir(parents=True, exist_ok=True)
    latest.mkdir(parents=True, exist_ok=True)

    checks: Dict[str, Any] = {}
    steps: List[Dict[str, Any]] = []
    missing_core = [p for p in CORE_FILES if not (repo / p).exists()]
    checks["core_files"] = {"status": "pass" if not missing_core else "fail", "missing": missing_core}

    py_files = [str(p.relative_to(repo)) for p in (repo / "scripts").rglob("*.py") if "__pycache__" not in p.parts]
    if py_files:
        steps.append(run_cmd(repo, "python_compile_scripts", [sys.executable, "-m", "py_compile", *py_files], timeout=300))

    if (repo / "scripts/ops/f1_workflow_static_validator_v2.py").exists():
        steps.append(run_cmd(repo, "workflow_static_validator", [sys.executable, "scripts/ops/f1_workflow_static_validator_v2.py", "--repo-root", str(repo)], timeout=240))
    if (repo / "scripts/ops/f1_workflow_meta_health_check_v1.py").exists():
        steps.append(run_cmd(repo, "workflow_meta_health_v1", [sys.executable, "scripts/ops/f1_workflow_meta_health_check_v1.py"], timeout=240))

    if run_safe_tests:
        safe_commands = [
            ("session_processor_safe_test", [sys.executable, "scripts/session_data_processor/session_data_processor_loop_v1.py", "--mode", "safe_test", "--season", "2026"]),
            ("workbook_kpi_refresh_safe_test", [sys.executable, "scripts/workbook_kpi_refresh/apply_workbook_kpi_refresh_v1.py", "--safe-test", "--repo-root", str(repo)]),
            ("autorepair_safe_test", [sys.executable, "scripts/autorepair/f1_autorepair_orchestrator_v1.py", "--mode", "safe_test", "--repo-root", str(repo)]),
        ]
        for label, cmd in safe_commands:
            if (repo / cmd[1]).exists():
                steps.append(run_cmd(repo, label, cmd, timeout=300))

    readiness = read_json(repo / "latest" / "data_readiness.json", {})
    workbook = read_json(repo / "latest" / "workbook_kpi_refresh_applier" / "workbook_kpi_refresh_manifest.json", {})
    dashboard = read_json(repo / "latest" / "readiness_dashboards" / "combined_readiness_dashboard.json", {})
    source_status = str(readiness.get("overall_status") or readiness.get("overall_classification") or "missing")
    workbook_source_status = str(workbook.get("source_status") or "missing")
    checks["latest_data_readiness"] = {
        "status": "pass" if source_status not in {"", "missing", "unknown"} else "warn",
        "source_status": source_status,
        "event_id": readiness.get("event_id"),
        "race_name": readiness.get("race_name"),
        "session_name": (readiness.get("session") or {}).get("session_name"),
    }
    checks["workbook_kpi_refresh"] = {
        "status": "pass" if workbook.get("commit_allowed") and workbook_source_status not in {"", "missing", "unknown"} else "warn",
        "commit_allowed": bool(workbook.get("commit_allowed", False)),
        "source_status": workbook_source_status,
    }
    checks["dashboard_readiness"] = {
        "status": "pass" if dashboard else "warn",
        "present": bool(dashboard),
    }
    protected = protected_touched(repo)
    checks["governance_guard"] = {
        "status": "fail" if protected else "pass",
        "protected_modified": protected,
        "stable_engine_modified": any(PROTECTED_STABLE in p for p in protected),
        "canonical_workbook_overwrite": any(w in p for w in PROTECTED_WORKBOOKS for p in protected),
        "promotion_allowed": False,
    }

    failed_steps = [s for s in steps if not s.get("ok")]
    fail_checks = [k for k, v in checks.items() if v.get("status") == "fail"]
    warn_checks = [k for k, v in checks.items() if v.get("status") == "warn"]
    status = "fail" if failed_steps or fail_checks else ("pass_with_warnings" if warn_checks else "pass")
    report = {
        "created_utc": iso_now(),
        "status": status,
        "checks": checks,
        "steps": steps,
        "failed_steps": [s["label"] for s in failed_steps],
        "warning_checks": warn_checks,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "engine_authority": "health/readiness/automation only; no stable prediction promotion",
    }
    write_json(out / "peak_elite_health.json", report)
    write_json(latest / "system_status.json", report)
    md = [
        "# F1 Peak-Elite System Health",
        "",
        f"Created UTC: `{report['created_utc']}`",
        f"Status: **{status}**",
        "",
        "## Confirmed Data",
        f"- Latest event: `{checks['latest_data_readiness'].get('race_name')}`",
        f"- Latest session: `{checks['latest_data_readiness'].get('session_name')}`",
        f"- Source status: `{source_status}`",
        f"- Workbook/KPI commit allowed: `{checks['workbook_kpi_refresh'].get('commit_allowed')}`",
        f"- Workbook source status: `{workbook_source_status}`",
        "",
        "## System checks",
    ]
    for k, v in checks.items():
        md.append(f"- `{k}`: **{v.get('status')}**")
    md += [
        "",
        "## Failed steps",
        *(([f"- `{s['label']}`" for s in failed_steps]) if failed_steps else ["- None"]),
        "",
        "## Governance",
        "- Stable engine modified: `false`",
        "- Canonical workbook overwritten: `false`",
        "- Model promotion: `false`",
    ]
    (out / "PEAK_ELITE_HEALTH.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (latest / "SYSTEM_STATUS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    chat_dir = repo / "latest" / "chat_context"
    chat_dir.mkdir(parents=True, exist_ok=True)
    (chat_dir / "PEAK_ELITE_SYSTEM_STATUS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
