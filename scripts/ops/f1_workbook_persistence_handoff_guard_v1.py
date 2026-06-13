#!/usr/bin/env python3
"""Guard workbook/session persistence handoff wiring and runtime artifacts.

This guard is intentionally additive and conservative:
- does not modify Engine_2026-06-07_STABLE;
- does not overwrite canonical workbooks;
- does not promote model logic;
- only audits that source-backed sandbox workbook refresh outputs are durable.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROTECTED_FILENAMES = {
    "Engine_2026-06-07_STABLE",
    "F1_2026_Prediction_Model_Data_Workbook.xlsx",
    "F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx",
}

STATIC_TOKENS: Dict[str, List[str]] = {
    ".github/workflows/f1-peak-elite-control-room-one-click-v1.yml": [
        "latest/session_data_processor/**",
        "history/session_data_processor/**",
        "latest/workbook_kpi_refresh_applier/**",
        "history/workbook_kpi_refresh_applier/**",
        "latest/readiness_dashboards/**",
        "history/readiness_dashboards/**",
        "F1_Workbook_KPI_SANDBOX_*.xlsx",
        "git add -f",
        "PROTECTED_PATTERN",
        "safe_git_push_rebase_retry.sh",
    ],
    ".github/workflows/f1-1b-output-contract-after-control-room-v22.yml": [
        "latest/workbook_kpi_refresh_applier/**",
        "history/workbook_kpi_refresh_applier/**",
        "latest/session_data_processor/**",
        "history/session_data_processor/**",
        "F1_Workbook_KPI_SANDBOX_*.xlsx",
        "git add -f",
        "PROTECTED_PATTERN",
        "safe_git_push_rebase_retry.sh",
    ],
}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_parse_error": str(exc), "_path": str(path)}


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "pass", "clean", "refresh_applied", "dashboard_refreshed"}
    return bool(value)


def git_status(repo: Path) -> List[str]:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(repo), text=True, stderr=subprocess.STDOUT)
    except Exception:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def protected_status_lines(lines: List[str]) -> List[str]:
    bad = []
    for line in lines:
        for protected in PROTECTED_FILENAMES:
            if protected in line:
                bad.append(line)
                break
    return bad


def static_checks(repo: Path) -> Dict[str, Any]:
    checks = []
    issue_count = 0
    for rel, tokens in STATIC_TOKENS.items():
        path = repo / rel
        check = {"workflow": rel, "exists": path.exists(), "missing_tokens": []}
        if not path.exists():
            check["missing_tokens"] = list(tokens)
            issue_count += len(tokens)
        else:
            text = path.read_text(encoding="utf-8-sig")
            for token in tokens:
                if token not in text:
                    check["missing_tokens"].append(token)
            issue_count += len(check["missing_tokens"])
            # hard-block obvious protected force-adds
            protected_force_adds = [name for name in PROTECTED_FILENAMES if f"git add -f {name}" in text]
            if protected_force_adds:
                check["protected_force_add_violation"] = protected_force_adds
                issue_count += len(protected_force_adds)
        checks.append(check)
    return {"status": "pass" if issue_count == 0 else "fail", "issue_count": issue_count, "checks": checks}


def runtime_checks(repo: Path) -> Dict[str, Any]:
    status_paths = [
        repo / "_runtime" / "workbook_kpi_refresh_status.json",
        repo / "latest" / "workbook_kpi_refresh_applier" / "workbook_kpi_refresh_manifest.json",
        repo / "latest" / "readiness_dashboards" / "forecast_fantasy_readiness_dashboard.json",
    ]
    parsed = []
    should_have_workbook = False
    protected_overwrite_requested = False
    for path in status_paths:
        if path.exists():
            data = read_json(path)
            parsed.append({"path": str(path.relative_to(repo)), "data": data})
            if data.get("canonical_workbook_overwrite") is True or data.get("canonical_workbook_modified") is True:
                protected_overwrite_requested = True
            if boolish(data.get("commit_allowed")) or data.get("status") in {"refresh_applied", "dashboard_refreshed"} or boolish(data.get("source_backed")):
                # Only require workbook if this is a workbook refresh or source-backed readiness state.
                should_have_workbook = True
    workbook_roots = [repo / "latest" / "workbook_kpi_refresh_applier", repo / "history" / "workbook_kpi_refresh_applier"]
    sandbox_workbooks = []
    protected_candidates = []
    for wb_root in workbook_roots:
        if wb_root.exists():
            for p in wb_root.glob("**/*"):
                if p.is_file():
                    if p.name in PROTECTED_FILENAMES:
                        protected_candidates.append(str(p.relative_to(repo)))
                    if p.name.startswith("F1_Workbook_KPI_SANDBOX_") and p.suffix.lower() == ".xlsx":
                        sandbox_workbooks.append(str(p.relative_to(repo)))
    status_lines = git_status(repo)
    protected_git_status = protected_status_lines(status_lines)
    issues = []
    if protected_overwrite_requested:
        issues.append("protected_canonical_workbook_overwrite_requested")
    if protected_candidates:
        issues.append("protected_filename_inside_workbook_persistence_paths")
    if protected_git_status:
        issues.append("protected_asset_touched_in_git_status")
    if should_have_workbook and not sandbox_workbooks:
        issues.append("source_backed_workbook_refresh_without_durable_sandbox_workbook")
    return {
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "should_have_workbook": should_have_workbook,
        "latest_sandbox_workbooks": sandbox_workbooks,
        "protected_candidates": protected_candidates,
        "protected_git_status": protected_git_status,
        "parsed_status_files": parsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default="_runtime/workbook_persistence_handoff_guard")
    parser.add_argument("--mode", choices=["static", "runtime", "both"], default="both")
    parser.add_argument("--fail-on-issue", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    runtime_dir = (repo / args.runtime_dir).resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "created_utc": now_utc(),
        "mode": args.mode,
        "canonical_workbook_overwrite_allowed": False,
        "stable_engine_promotion_allowed": False,
        "promotion_allowed": False,
    }
    issue_count = 0
    if args.mode in {"static", "both"}:
        static = static_checks(repo)
        report["static_checks"] = static
        issue_count += int(static.get("issue_count", 0))
    if args.mode in {"runtime", "both"}:
        runtime = runtime_checks(repo)
        report["runtime_checks"] = runtime
        issue_count += int(runtime.get("issue_count", 0))
    report["issue_count"] = issue_count
    report["status"] = "pass" if issue_count == 0 else "fail"

    out = runtime_dir / "workbook_persistence_handoff_guard_report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.fail_on_issue and issue_count:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
