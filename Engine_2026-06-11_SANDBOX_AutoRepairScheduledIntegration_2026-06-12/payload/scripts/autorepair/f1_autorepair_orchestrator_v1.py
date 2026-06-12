#!/usr/bin/env python3
"""F1 Auto-Repair Orchestrator v1.

Sandbox-only recovery orchestrator for the current production-readiness gap:
Workbook/KPI refresh has no valid session source -> run Session Data Processor -> rerun Workbook/KPI refresh -> commit only if source-backed.

This script does not modify Engine_2026-06-07_STABLE, does not overwrite the canonical workbook, and does not promote any model layer.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Tuple

PROTECTED_STABLE_ENGINE = "Engine_2026-06-07_STABLE"
PROTECTED_CANONICAL_PATTERNS = [
    "F1_2026_Prediction_Model_Data_Workbook.xlsx",
    "F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx",
]
BLOCKED_SOURCE_STATUSES = {"", "missing", "unknown", "no_action", "not_found", "empty", "placeholder", "scheduled_not_populated"}
COMMIT_ELIGIBLE_SOURCE_STATUSES = {"clean", "partial", "late", "conflicting", "needs_manual_review", "needs-review", "needs_manual"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def rel(repo: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def run_cmd(cmd: List[str], repo: Path, timeout: int = 900) -> Dict[str, Any]:
    started = iso_now()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "started_utc": started,
            "finished_utc": iso_now(),
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-5000:],
            "stderr_tail": proc.stderr[-5000:],
            "ok": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "started_utc": started,
            "finished_utc": iso_now(),
            "returncode": 124,
            "stdout_tail": (exc.stdout or "")[-5000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-5000:] if isinstance(exc.stderr, str) else "",
            "ok": False,
            "timeout": True,
        }
    except Exception as exc:
        return {
            "cmd": cmd,
            "started_utc": started,
            "finished_utc": iso_now(),
            "returncode": 1,
            "stdout_tail": "",
            "stderr_tail": repr(exc),
            "ok": False,
            "exception": repr(exc),
        }


def discover_script(repo: Path, preferred: List[str], name_contains: List[str]) -> Path | None:
    for p in preferred:
        path = repo / p
        if path.exists():
            return path
    scripts = repo / "scripts"
    if scripts.exists():
        for path in scripts.rglob("*.py"):
            low = path.name.lower()
            if all(tok in low for tok in name_contains):
                return path
    return None


def get_workbook_status(repo: Path) -> Dict[str, Any]:
    runtime = read_json(repo / "_runtime" / "workbook_kpi_refresh_status.json", {})
    if runtime:
        return runtime
    latest_manifest = read_json(repo / "latest" / "workbook_kpi_refresh_applier" / "workbook_kpi_refresh_manifest.json", {})
    if latest_manifest:
        return {
            "status": "latest_manifest_found",
            "commit_allowed": bool(latest_manifest.get("commit_allowed", False)),
            "source_status": latest_manifest.get("source_status"),
            "latest_output_root": "latest/workbook_kpi_refresh_applier",
        }
    return {"status": "missing", "commit_allowed": False, "source_status": "missing"}


def get_session_processor_status(repo: Path) -> Dict[str, Any]:
    runtime = read_json(repo / "_runtime" / "session_data_processor" / "session_processor_status.json", {})
    # older/current processor may not write a single runtime status; summarize from latest readiness
    if runtime:
        return runtime
    readiness = read_json(repo / "latest" / "data_readiness.json", {})
    latest_manifest = read_json(repo / "latest" / "latest_manifest.json", {})
    if readiness or latest_manifest:
        return {
            "status": "latest_readiness_found",
            "classification": readiness.get("overall_classification") or readiness.get("classification") or readiness.get("status"),
            "latest_manifest_present": bool(latest_manifest),
            "data_readiness_present": bool(readiness),
        }
    return {"status": "missing"}


def needs_session_repair(workbook_status: Dict[str, Any]) -> bool:
    status = normalize_status(workbook_status.get("status"))
    source_status = normalize_status(workbook_status.get("source_status"))
    reason = normalize_status(workbook_status.get("reason"))
    commit_allowed = bool(workbook_status.get("commit_allowed", False))
    if commit_allowed and source_status in COMMIT_ELIGIBLE_SOURCE_STATUSES:
        return False
    if source_status in BLOCKED_SOURCE_STATUSES:
        return True
    if status in {"missing", "no_action"}:
        return True
    if "source" in reason and ("missing" in reason or "incomplete" in reason or "not_commit" in reason):
        return True
    return False


def protected_touched(repo: Path) -> Tuple[bool, List[str]]:
    # Best-effort git status check. If git unavailable, fall back to file existence only and do not block.
    git = shutil.which("git")
    if not git:
        return False, []
    result = subprocess.run([git, "status", "--porcelain"], cwd=str(repo), text=True, capture_output=True)
    touched = []
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            path = line[3:].strip() if len(line) > 3 else line.strip()
            if not path:
                continue
            low = path.lower()
            if PROTECTED_STABLE_ENGINE.lower() in low:
                touched.append(path)
            for pat in PROTECTED_CANONICAL_PATTERNS:
                if path.endswith(pat) or pat.lower() in low:
                    touched.append(path)
    return bool(touched), touched


def make_report(report: Dict[str, Any]) -> str:
    verdict = report.get("verdict", "Pass with warnings")
    actions = report.get("actions", [])
    action_md = "\n".join([f"- **{a.get('name')}**: {a.get('status')}" for a in actions]) or "- None"
    warnings = report.get("warnings", [])
    warnings_md = "\n".join([f"- {w}" for w in warnings]) or "- None"
    return f"""# F1 Auto-Repair Orchestrator Report

## Verdict

{verdict}

## Scope

- Sandbox branch/layer: `Engine_2026-06-11_SANDBOX_AutoRepairOrchestrator`
- Repair domain: `{report.get('repair_domain')}`
- Run ID: `{report.get('run_id')}`
- Created UTC: `{report.get('created_utc')}`

## What it did

{action_md}

## Final status

- Commit allowed: `{report.get('commit_allowed')}`
- Repair attempted: `{report.get('repair_attempted')}`
- Repair succeeded: `{report.get('repair_succeeded')}`
- Final workbook status: `{report.get('final_workbook_status', {}).get('status')}`
- Final workbook source status: `{report.get('final_workbook_status', {}).get('source_status')}`

## Warnings

{warnings_md}

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**
- Force push: **blocked**

## Plain-English interpretation

This layer automatically recovers the current session-to-workbook gap by running the session data processor before allowing a Workbook/KPI refresh to commit. If source evidence remains missing, it stops safely instead of producing weak workbook artifacts.
"""


def safe_test(repo: Path, out: Path, catalog: Dict[str, Any]) -> Dict[str, Any]:
    session_script = discover_script(repo, catalog["script_discovery"]["session_processor_preferred"], ["session", "processor"])
    workbook_script = discover_script(repo, catalog["script_discovery"]["workbook_applier_preferred"], ["workbook", "refresh"])
    warnings = []
    if not session_script:
        warnings.append("session_processor_script_not_found")
    if not workbook_script:
        warnings.append("workbook_kpi_refresh_script_not_found")
    report = {
        "run_id": utc_now(),
        "created_utc": iso_now(),
        "mode": "safe_test",
        "repair_domain": "session_workbook_recovery",
        "verdict": "Pass" if not warnings else "Pass with warnings",
        "commit_allowed": False,
        "repair_attempted": False,
        "repair_succeeded": False,
        "discovered_scripts": {
            "session_processor": rel(repo, session_script) if session_script else None,
            "workbook_kpi_refresh_applier": rel(repo, workbook_script) if workbook_script else None,
        },
        "warnings": warnings,
        "governance": {
            "canonical_workbook_overwrite": False,
            "stable_engine_modified": False,
            "promotion_allowed": False,
            "delete_authority": False,
        },
        "actions": [{"name": "safe_preflight", "status": "passed" if not warnings else "passed_with_warnings"}],
    }
    write_outputs(repo, out, report)
    return report


def run_now(repo: Path, out: Path, catalog: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    run_id = utc_now()
    actions = []
    warnings = []
    repair_attempted = False
    repair_succeeded = False

    session_script = discover_script(repo, catalog["script_discovery"]["session_processor_preferred"], ["session", "processor"])
    workbook_script = discover_script(repo, catalog["script_discovery"]["workbook_applier_preferred"], ["workbook", "refresh"])
    if not session_script:
        warnings.append("session_processor_script_not_found")
    if not workbook_script:
        warnings.append("workbook_kpi_refresh_script_not_found")

    # First try workbook applier so we know if repair is needed.
    initial_workbook_status = get_workbook_status(repo)
    if workbook_script:
        cmd = [sys.executable, rel(repo, workbook_script), "--repo-root", str(repo)]
        result = run_cmd(cmd, repo, timeout=timeout)
        actions.append({"name": "initial_workbook_kpi_refresh_attempt", "status": "passed" if result["ok"] else "failed", "details": result})
        initial_workbook_status = get_workbook_status(repo)
    else:
        actions.append({"name": "initial_workbook_kpi_refresh_attempt", "status": "skipped_no_script"})

    final_workbook_status = initial_workbook_status
    session_status = get_session_processor_status(repo)

    if needs_session_repair(initial_workbook_status):
        repair_attempted = True
        if session_script:
            cmd = [sys.executable, rel(repo, session_script), "--mode", "run_now", "--season", "2026", "--session-filter", "auto"]
            result = run_cmd(cmd, repo, timeout=timeout)
            actions.append({"name": "repair_run_session_data_processor", "status": "passed" if result["ok"] else "failed", "details": result})
            session_status = get_session_processor_status(repo)
        else:
            actions.append({"name": "repair_run_session_data_processor", "status": "skipped_no_script"})

        if workbook_script:
            cmd = [sys.executable, rel(repo, workbook_script), "--repo-root", str(repo)]
            result = run_cmd(cmd, repo, timeout=timeout)
            actions.append({"name": "repair_rerun_workbook_kpi_refresh", "status": "passed" if result["ok"] else "failed", "details": result})
            final_workbook_status = get_workbook_status(repo)
        else:
            actions.append({"name": "repair_rerun_workbook_kpi_refresh", "status": "skipped_no_script"})

    commit_allowed = bool(final_workbook_status.get("commit_allowed", False))
    final_source_status = normalize_status(final_workbook_status.get("source_status"))
    if commit_allowed and final_source_status not in COMMIT_ELIGIBLE_SOURCE_STATUSES:
        warnings.append(f"commit_blocked_final_source_status_not_eligible={final_source_status}")
        commit_allowed = False
    protected, protected_paths = protected_touched(repo)
    if protected:
        warnings.append("protected_paths_touched:" + ",".join(protected_paths))
        commit_allowed = False
    if repair_attempted and commit_allowed:
        repair_succeeded = True

    verdict = "Pass" if commit_allowed else "Pass with warnings"
    if not workbook_script or not session_script:
        verdict = "Fail"
    if protected:
        verdict = "Fail"

    report = {
        "run_id": run_id,
        "created_utc": iso_now(),
        "mode": "run_now",
        "repair_domain": "session_workbook_recovery",
        "verdict": verdict,
        "commit_allowed": commit_allowed,
        "repair_attempted": repair_attempted,
        "repair_succeeded": repair_succeeded,
        "initial_workbook_status": initial_workbook_status,
        "session_processor_status": session_status,
        "final_workbook_status": final_workbook_status,
        "discovered_scripts": {
            "session_processor": rel(repo, session_script) if session_script else None,
            "workbook_kpi_refresh_applier": rel(repo, workbook_script) if workbook_script else None,
        },
        "warnings": warnings,
        "protected_paths_touched": protected_paths,
        "governance": {
            "canonical_workbook_overwrite": False,
            "stable_engine_modified": False,
            "promotion_allowed": False,
            "delete_authority": False,
            "force_push": False,
        },
        "actions": actions,
    }
    write_outputs(repo, out, report)
    return report


def write_outputs(repo: Path, out: Path, report: Dict[str, Any]) -> None:
    run_id = report.get("run_id") or utc_now()
    latest = repo / "latest" / "autorepair" / "session_workbook_recovery"
    history = repo / "history" / "autorepair" / "session_workbook_recovery" / run_id
    runtime = out
    for d in [latest, history, runtime]:
        d.mkdir(parents=True, exist_ok=True)
    report_md = make_report(report)
    # runtime
    write_json(runtime / "autorepair_status.json", report)
    (runtime / "autorepair_report.md").write_text(report_md, encoding="utf-8")
    (runtime / "commit_allowed.txt").write_text("true" if report.get("commit_allowed") else "false", encoding="utf-8")
    # latest/history
    write_json(history / "autorepair_status.json", report)
    (history / "autorepair_report.md").write_text(report_md, encoding="utf-8")
    shutil.copy2(history / "autorepair_status.json", latest / "autorepair_status.json")
    shutil.copy2(history / "autorepair_report.md", latest / "autorepair_report.md")
    # simple manifest
    manifest = {
        "run_id": run_id,
        "created_utc": report.get("created_utc"),
        "outputs": [],
        "commit_allowed": report.get("commit_allowed", False),
        "sandbox_only": True,
    }
    for p in [history / "autorepair_status.json", history / "autorepair_report.md", latest / "autorepair_status.json", latest / "autorepair_report.md"]:
        if p.exists():
            manifest["outputs"].append({"path": rel(repo, p), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_json(history / "autorepair_manifest.json", manifest)
    shutil.copy2(history / "autorepair_manifest.json", latest / "autorepair_manifest.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="safe_test", choices=["safe_test", "run_now"])
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--catalog", default="configs/autorepair/repair_catalog_v1.json")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    out = repo / "_runtime" / "autorepair" / "session_workbook_recovery"
    catalog = read_json(repo / args.catalog, {})
    if not catalog:
        # fallback if installed under repo root differently
        catalog = read_json(Path(args.catalog), {})
    if not catalog:
        catalog = {
            "script_discovery": {
                "session_processor_preferred": ["scripts/session_data_processor/session_data_processor_loop_v1.py"],
                "workbook_applier_preferred": ["scripts/workbook_kpi_refresh/apply_workbook_kpi_refresh_v1.py"],
            }
        }
    if args.mode == "safe_test":
        report = safe_test(repo, out, catalog)
    else:
        report = run_now(repo, out, catalog, args.timeout)
    # Print enough detail into the GitHub log so the user does not have to
    # download a separate runtime artifact just to know what happened.
    log_summary = {
        "status": report.get("verdict"),
        "commit_allowed": report.get("commit_allowed"),
        "repair_attempted": report.get("repair_attempted"),
        "repair_succeeded": report.get("repair_succeeded"),
        "initial_workbook_status": report.get("initial_workbook_status", {}).get("status"),
        "initial_workbook_source_status": report.get("initial_workbook_status", {}).get("source_status"),
        "final_workbook_status": report.get("final_workbook_status", {}).get("status"),
        "final_workbook_source_status": report.get("final_workbook_status", {}).get("source_status"),
        "warnings": report.get("warnings", []),
        "action_statuses": [{ "name": a.get("name"), "status": a.get("status") } for a in report.get("actions", [])],
        "runtime_report": rel(repo, out / "autorepair_report.md"),
    }
    print(json.dumps(log_summary, indent=2))
    return 0 if report.get("verdict") != "Fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
