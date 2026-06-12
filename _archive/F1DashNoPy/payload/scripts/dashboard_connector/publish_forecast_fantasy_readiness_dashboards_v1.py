#!/usr/bin/env python3
"""Publish source-backed Race/Fantasy readiness dashboard and chat briefs.

This connector is intentionally conservative: it reads existing latest/history artifacts,
creates dashboard state files, and never modifies stable predictions or the canonical workbook.
"""
from __future__ import annotations
import argparse, csv, json, os, re, shutil, sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SAFE_SOURCE_STATUSES = {"clean", "partial", "late", "conflicting", "needs_manual_review"}
BAD_SOURCE_STATUSES = {"missing", "unknown", "placeholder", "scheduled_not_populated", "not_found"}


def now_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def norm_status(value: Any) -> str:
    s = str(value or "unknown").strip().lower().replace(" ", "_")
    return s or "unknown"


def find_latest_json(root: Path, base: str, names: List[str]) -> Optional[Path]:
    candidates: List[Path] = []
    b = root / base
    if not b.exists():
        return None
    for name in names:
        candidates.extend(b.rglob(name))
    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def find_latest_workbook(root: Path) -> Optional[Path]:
    candidates: List[Path] = []
    for base in [root / "latest" / "workbook_kpi_refresh_applier", root / "history" / "workbook_kpi_refresh_applier"]:
        if base.exists():
            candidates.extend(base.rglob("*.xlsx"))
    candidates = [p for p in candidates if p.is_file() and "SANDBOX" in p.name]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def first_present(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def discover_state(root: Path) -> Dict[str, Any]:
    # Pull newest source facts from workbook refresh, session processor, and autorepair reports.
    workbook_manifest_path = find_latest_json(root, "latest/workbook_kpi_refresh_applier", [
        "workbook_kpi_refresh_manifest.json",
        "refresh_manifest.json",
        "manifest.json",
        "workbook_kpi_refresh_report.json",
    ])
    workbook_state = read_json(workbook_manifest_path) if workbook_manifest_path else {}

    session_manifest_path = find_latest_json(root, "latest/session_data_processor", [
        "data_readiness.json",
        "session_processor_manifest.json",
        "source_readiness_manifest.json",
        "session_validation_report.json",
        "latest_manifest.json",
    ])
    session_state = read_json(session_manifest_path) if session_manifest_path else {}

    autorepair_path = find_latest_json(root, "latest/autorepair", [
        "autorepair_report.json",
        "session_workbook_recovery_report.json",
        "repair_report.json",
    ])
    autorepair_state = read_json(autorepair_path) if autorepair_path else {}

    workbook_path = find_latest_workbook(root)

    source_status = norm_status(first_present(workbook_state, [
        "source_status", "final_workbook_source_status", "overall_status", "overall_classification", "classification", "status"
    ], None))
    if source_status in {"unknown", "missing"}:
        source_status = norm_status(first_present(session_state, ["overall_status", "source_status", "classification", "status"], source_status))
    if source_status in {"unknown", "missing"}:
        source_status = norm_status(first_present(autorepair_state, ["final_workbook_source_status", "source_status", "status"], source_status))

    event_name = first_present(workbook_state, ["event_name", "race_name", "event", "meeting_name"], None)
    if not event_name:
        event_name = first_present(session_state, ["event_name", "race_name", "meeting_name", "circuit_short_name"], None)
    if not event_name and workbook_path:
        # Extract something readable from the generated workbook name.
        m = re.search(r"Refresh_(.*?)_session_", workbook_path.name)
        event_name = m.group(1).replace("_", " ") if m else "latest session"

    session_name = first_present(workbook_state, ["session_name", "session", "session_type"], None)
    if not session_name:
        session_name = first_present(session_state, ["session_name", "session", "session_type"], "latest session")

    source_backed = source_status in SAFE_SOURCE_STATUSES
    commit_allowed = source_backed or bool(workbook_path and source_status not in BAD_SOURCE_STATUSES)

    dashboard = {
        "generated_at_utc": now_iso(),
        "status": "dashboard_refreshed" if commit_allowed else "no_action",
        "source_status": source_status,
        "source_backed": bool(source_backed),
        "commit_allowed": bool(commit_allowed),
        "event_name": event_name or "unknown event",
        "session_name": session_name or "unknown session",
        "workbook_artifact": str(workbook_path).replace(str(root) + os.sep, "") if workbook_path else None,
        "workbook_manifest": str(workbook_manifest_path).replace(str(root) + os.sep, "") if workbook_manifest_path else None,
        "session_manifest": str(session_manifest_path).replace(str(root) + os.sep, "") if session_manifest_path else None,
        "autorepair_report": str(autorepair_path).replace(str(root) + os.sep, "") if autorepair_path else None,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "race_predictions": {
            "ready_for_use": bool(commit_allowed),
            "latest_session_state": source_status,
            "allowed_effect": "confidence/risk/readiness context only; stable P1-P20 not overwritten",
        },
        "fantasy_predictions": {
            "ready_for_use": bool(commit_allowed),
            "latest_session_state": source_status,
            "allowed_effect": "readiness/value/risk context only; no automatic fantasy transfer execution",
        },
    }
    return dashboard


def brief(title: str, dashboard: Dict[str, Any], audience: str) -> str:
    ready = "READY" if dashboard.get("commit_allowed") else "NOT READY"
    lines = [
        f"# {title}",
        "",
        f"Generated UTC: {dashboard['generated_at_utc']}",
        f"Event: {dashboard.get('event_name')}",
        f"Session: {dashboard.get('session_name')}",
        f"Source status: {dashboard.get('source_status')}",
        f"Dashboard readiness: {ready}",
        "",
        "## Governance",
        "- Canonical workbook overwrite: false",
        "- Stable engine modified: false",
        "- Promotion allowed: false",
        "- Use this as latest source/readiness context only.",
        "",
        "## Chat instruction",
    ]
    if audience == "race":
        lines.append("Race Predictions may use this to update readiness, confidence, risk, and source-status notes. Do not silently overwrite stable exact P1-P20.")
    else:
        lines.append("Fantasy Predictions may use this to update source readiness, session risk, and value context. Do not execute fantasy changes automatically.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="run_now")
    ap.add_argument("--runtime-dir", default="_runtime/dashboard_connector")
    args = ap.parse_args()
    root = Path.cwd()
    runtime = root / args.runtime_dir
    runtime.mkdir(parents=True, exist_ok=True)
    stamp = now_id()

    dashboard = discover_state(root)
    latest_dash = root / "latest" / "readiness_dashboards"
    latest_chat = root / "latest" / "chat_context"
    hist_dash = root / "history" / "readiness_dashboards" / stamp
    hist_chat = root / "history" / "chat_context" / stamp
    for p in [latest_dash, latest_chat, hist_dash, hist_chat]:
        p.mkdir(parents=True, exist_ok=True)

    race_state = dict(dashboard.get("race_predictions", {}), generated_at_utc=dashboard["generated_at_utc"], source_status=dashboard["source_status"], event_name=dashboard["event_name"], session_name=dashboard["session_name"])
    fantasy_state = dict(dashboard.get("fantasy_predictions", {}), generated_at_utc=dashboard["generated_at_utc"], source_status=dashboard["source_status"], event_name=dashboard["event_name"], session_name=dashboard["session_name"])

    files = {
        "combined_readiness_dashboard.json": dashboard,
        "race_predictions_readiness_state.json": race_state,
        "fantasy_readiness_state.json": fantasy_state,
    }
    for name, data in files.items():
        (latest_dash / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
        (hist_dash / name).write_text(json.dumps(data, indent=2), encoding="utf-8")

    race_brief = brief("Race Predictions Latest Session Brief", dashboard, "race")
    fantasy_brief = brief("Fantasy Predictions Latest Session Brief", dashboard, "fantasy")
    for base in [latest_chat, hist_chat]:
        (base / "RACE_PREDICTIONS_LATEST_SESSION_BRIEF.md").write_text(race_brief, encoding="utf-8")
        (base / "FANTASY_PREDICTIONS_LATEST_SESSION_BRIEF.md").write_text(fantasy_brief, encoding="utf-8")

    (runtime / "dashboard_connector_result.json").write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    print(json.dumps(dashboard, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
