#!/usr/bin/env python3
"""F1 Forecast/Fantasy Readiness Dashboard Connector v1.

Sandbox-only connector that reads latest Session Data Processor, Workbook/KPI Refresh,
Auto-Repair, and Forecast Bundle artifacts, then publishes simple dashboard state files
for Race Predictions and Fantasy chats.

It never overwrites the canonical workbook, never changes Engine_2026-06-07_STABLE,
and never promotes model layers.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

ALLOWED_SOURCE_STATUSES = {"clean", "partial", "late", "conflicting", "needs_manual_review"}
BLOCKED_SOURCE_STATUSES = {"missing", "unknown", "placeholder", "scheduled_not_populated", "empty"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_latest_file(root: Path, patterns: Iterable[str]) -> Optional[Path]:
    candidates: List[Path] = []
    for pat in patterns:
        candidates.extend([p for p in root.glob(pat) if p.is_file()])
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def newest_dir_with_any(root: Path, required_any: Iterable[str]) -> Optional[Path]:
    if not root.exists():
        return None
    candidates = []
    for d in root.rglob("*"):
        if not d.is_dir():
            continue
        names = {p.name for p in d.iterdir() if p.is_file()}
        if any(req in names for req in required_any):
            candidates.append(d)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def first_value(*vals: Any, default: Any = None) -> Any:
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return default


def flatten_candidate_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for d in dicts:
        for k, v in d.items():
            if k not in out and v not in (None, "", [], {}):
                out[k] = v
    return out


def read_first_csv_row(path: Optional[Path]) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return next(reader, {})
    except Exception:
        return {}


def discover_sources(repo: Path) -> Dict[str, Any]:
    latest = repo / "latest"
    wb_root = latest / "workbook_kpi_refresh_applier"
    session_root = latest / "session_data_processor"
    autorepair_root = latest / "autorepair" / "session_workbook_recovery"

    wb_dir = newest_dir_with_any(wb_root, ["dashboard_source_manifest.json", "workbook_kpi_refresh_status.json", "workbook_kpi_refresh_manifest.json"]) or wb_root
    session_dir = newest_dir_with_any(session_root, ["workbook_kpi_readiness.json", "workbook_kpi_readiness.csv", "source_classification.json", "processor_manifest.json"])
    autorepair_dir = newest_dir_with_any(autorepair_root, ["autorepair_report.json", "autorepair_status.json"]) or autorepair_root

    data_readiness_path = latest / "data_readiness.json"
    latest_manifest_path = latest / "latest_manifest.json"
    combined_manifest_path = latest / "combined_source_manifest.json"

    wb_json_paths = []
    if wb_root.exists():
        wb_json_paths.extend(wb_root.rglob("*.json"))
    wb_json_data = {}
    for p in sorted(wb_json_paths, key=lambda x: x.stat().st_mtime, reverse=True)[:12]:
        d = read_json(p)
        # merge shallow, most recent first
        wb_json_data = flatten_candidate_dicts(wb_json_data, d)

    session_json_data = {}
    if session_dir:
        for p in sorted(session_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            d = read_json(p)
            session_json_data = flatten_candidate_dicts(session_json_data, d)
    session_csv_row = read_first_csv_row((session_dir / "workbook_kpi_readiness.csv") if session_dir else None)

    data_readiness = read_json(data_readiness_path)
    latest_manifest = read_json(latest_manifest_path)
    combined_manifest = read_json(combined_manifest_path)
    autorepair = {}
    if autorepair_dir.exists():
        ar = find_latest_file(autorepair_dir, ["*.json", "**/*.json"])
        if ar:
            autorepair = read_json(ar)

    latest_workbook = find_latest_file(wb_root, ["*.xlsx", "**/*.xlsx"])
    forecast_ledger = find_latest_file(repo, ["latest/**/forecast_bundle_ledger_snapshot.json", "history/**/forecast_bundle_ledger_snapshot.json", "latest/forecast_bundles/**/*.json", "history/forecast_bundles/**/*.json"])

    combined = flatten_candidate_dicts(wb_json_data, session_json_data, session_csv_row, data_readiness, latest_manifest, combined_manifest, autorepair)

    source_status = str(first_value(
        combined.get("source_status"), combined.get("overall_status"), combined.get("overall_classification"),
        combined.get("classification"), combined.get("status"), default="unknown"
    )).strip()
    if source_status == "refresh_applied":
        # This is a workbook action status, not source readiness. Fall back to session status.
        source_status = str(first_value(session_json_data.get("overall_status"), session_json_data.get("source_status"), default="unknown"))

    event_name = first_value(
        combined.get("event_name"), combined.get("meeting_name"), combined.get("race_name"),
        combined.get("event"), combined.get("grand_prix"), default="unknown_event"
    )
    session_name = first_value(
        combined.get("session_name"), combined.get("session_type"), combined.get("session"), default="unknown_session"
    )
    session_key = first_value(combined.get("session_key"), combined.get("session_id"), default="unknown")
    round_number = first_value(combined.get("round_number"), combined.get("round"), default="unknown")

    return {
        "source_status": source_status,
        "event_name": str(event_name),
        "session_name": str(session_name),
        "session_key": str(session_key),
        "round_number": str(round_number),
        "latest_workbook_path": str(latest_workbook.relative_to(repo)) if latest_workbook else None,
        "latest_session_processor_path": str(session_dir.relative_to(repo)) if session_dir else None,
        "latest_autorepair_path": str(autorepair_dir.relative_to(repo)) if autorepair_dir.exists() else None,
        "data_readiness_path": str(data_readiness_path.relative_to(repo)) if data_readiness_path.exists() else None,
        "latest_manifest_path": str(latest_manifest_path.relative_to(repo)) if latest_manifest_path.exists() else None,
        "combined_source_manifest_path": str(combined_manifest_path.relative_to(repo)) if combined_manifest_path.exists() else None,
        "forecast_bundle_ledger_path": str(forecast_ledger.relative_to(repo)) if forecast_ledger else None,
        "combined_source_fields": combined,
        "data_readiness_hash": sha256_file(data_readiness_path) if data_readiness_path.exists() else None,
    }


def determine_material_change(repo: Path, current: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    previous_path = repo / "latest" / "readiness_dashboards" / "combined_readiness_dashboard.json"
    previous = read_json(previous_path) if previous_path.exists() else {}
    comparable = {
        "event_name": current["event_name"],
        "session_name": current["session_name"],
        "session_key": current["session_key"],
        "source_status": current["source_status"],
        "latest_workbook_path": current["latest_workbook_path"],
        "latest_session_processor_path": current["latest_session_processor_path"],
        "data_readiness_hash": current["data_readiness_hash"],
    }
    prev_comp = previous.get("material_change_signature", {})
    return comparable != prev_comp, {"previous": prev_comp, "current": comparable}


def build_state(repo: Path, sources: Dict[str, Any], mode: str) -> Dict[str, Any]:
    source_status = sources["source_status"]
    source_backed = source_status in ALLOWED_SOURCE_STATUSES
    missing_blocked = source_status in BLOCKED_SOURCE_STATUSES or not sources.get("latest_workbook_path")
    material_change, diff = determine_material_change(repo, sources)

    if mode == "safe_test":
        status = "safe_test_pass"
        commit_allowed = False
    elif missing_blocked:
        status = "no_action"
        commit_allowed = False
    else:
        status = "dashboard_refreshed"
        # dashboard updates are useful only when state changed; no-op otherwise.
        commit_allowed = bool(material_change)

    race_gate = "ready_with_warnings" if source_backed else "blocked_missing_source"
    fantasy_gate = "ready_with_warnings" if source_backed else "blocked_missing_source"
    if source_status == "clean":
        race_gate = fantasy_gate = "ready"

    return {
        "generated_at_utc": iso_now(),
        "status": status,
        "source_status": source_status,
        "source_backed": source_backed,
        "commit_allowed": commit_allowed,
        "material_change": bool(material_change),
        "material_change_diff": diff,
        "material_change_signature": diff["current"],
        "event": {
            "event_name": sources["event_name"],
            "session_name": sources["session_name"],
            "session_key": sources["session_key"],
            "round_number": sources["round_number"],
        },
        "race_predictions": {
            "readiness_state": race_gate,
            "latest_session_state_available": source_backed,
            "recommended_chat_action": "Use latest workbook/KPI sandbox readiness state as source context; do not overwrite stable P1-P20.",
            "stable_engine_overwrite_allowed": False,
            "confidence_adjustment_allowed": True,
            "exact_order_overwrite_allowed": False,
        },
        "fantasy": {
            "readiness_state": fantasy_gate,
            "latest_session_state_available": source_backed,
            "recommended_chat_action": "Use latest session readiness to adjust risk, confidence, value/watch flags; do not imply official model promotion.",
            "transfer_recommendation_allowed": source_backed,
            "chip_recommendation_allowed": source_backed,
        },
        "artifacts": {
            "latest_workbook_path": sources.get("latest_workbook_path"),
            "latest_session_processor_path": sources.get("latest_session_processor_path"),
            "latest_autorepair_path": sources.get("latest_autorepair_path"),
            "data_readiness_path": sources.get("data_readiness_path"),
            "latest_manifest_path": sources.get("latest_manifest_path"),
            "combined_source_manifest_path": sources.get("combined_source_manifest_path"),
        },
        "forecast_bundle_ledger": {
            "snapshot_path": sources.get("forecast_bundle_ledger_path"),
            "discipline_state": "linked" if sources.get("forecast_bundle_ledger_path") else "not_found_optional_warning",
        },
        "governance": {
            "canonical_workbook_overwrite": False,
            "stable_engine_modified": False,
            "promotion_allowed": False,
            "delete_old_files_allowed": False,
            "sandbox_only": True,
        },
    }


def md_dashboard(state: Dict[str, Any]) -> str:
    e = state["event"]
    art = state["artifacts"]
    return f"""# F1 Forecast/Fantasy Readiness Dashboard

Generated UTC: {state['generated_at_utc']}

## Executive Summary

Status: **{state['status']}**  
Source status: **{state['source_status']}**  
Material change: **{state['material_change']}**  
Commit allowed: **{state['commit_allowed']}**

## Latest session state

| Field | Value |
|---|---|
| Event | {e['event_name']} |
| Session | {e['session_name']} |
| Session key | {e['session_key']} |
| Round | {e['round_number']} |

## Race Predictions readiness

State: **{state['race_predictions']['readiness_state']}**

Use the latest session state as context for confidence, risk, and scenario flags. Do **not** overwrite stable exact P1-P20 output from this dashboard alone.

## Fantasy readiness

State: **{state['fantasy']['readiness_state']}**

Use the latest session state for fantasy risk, value, watch/avoid, and transfer-readiness context.

## Linked artifacts

| Artifact | Path |
|---|---|
| Sandbox workbook | {art.get('latest_workbook_path')} |
| Session processor | {art.get('latest_session_processor_path')} |
| Auto-Repair | {art.get('latest_autorepair_path')} |
| Data readiness | {art.get('data_readiness_path')} |
| Latest manifest | {art.get('latest_manifest_path')} |
| Combined source manifest | {art.get('combined_source_manifest_path')} |
| Forecast Bundle Ledger | {state['forecast_bundle_ledger'].get('snapshot_path')} |

## Governance

- Canonical workbook overwrite: **False**
- Stable engine modified: **False**
- Promotion allowed: **False**
- Sandbox only: **True**
"""


def race_brief(state: Dict[str, Any]) -> str:
    e = state["event"]
    return f"""# Race Predictions Latest Session Brief

Latest source-backed session state: **{state['source_backed']}**  
Source status: **{state['source_status']}**  
Event/session: **{e['event_name']} / {e['session_name']}**  
Session key: **{e['session_key']}**

Use this readiness state to inform confidence, risk flags, scenario branches, and source-readiness notes.

Do not overwrite Engine_2026-06-07_STABLE exact P1-P20 from this dashboard alone.

Linked sandbox workbook: `{state['artifacts'].get('latest_workbook_path')}`
"""


def fantasy_brief(state: Dict[str, Any]) -> str:
    e = state["event"]
    return f"""# Fantasy Predictions Latest Session Brief

Latest source-backed session state: **{state['source_backed']}**  
Source status: **{state['source_status']}**  
Event/session: **{e['event_name']} / {e['session_name']}**  
Session key: **{e['session_key']}**

Use this readiness state for fantasy transfer readiness, chip timing context, value/watch flags, and risk notes.

Do not treat this as model promotion. Keep stable and experimental lanes separate.

Linked sandbox workbook: `{state['artifacts'].get('latest_workbook_path')}`
"""


def publish(repo: Path, mode: str, runtime_dir: Path) -> Dict[str, Any]:
    sources = discover_sources(repo)
    state = build_state(repo, sources, mode)

    runtime_dir.mkdir(parents=True, exist_ok=True)
    write_json(runtime_dir / "dashboard_connector_status.json", state)
    write_text(runtime_dir / "dashboard_connector_report.md", md_dashboard(state))
    write_json(runtime_dir / "commit_allowed.json", {"commit_allowed": bool(state["commit_allowed"]), "status": state["status"], "source_status": state["source_status"]})

    if mode == "safe_test":
        return state

    if state["status"] == "no_action":
        return state

    ts = utc_now()
    latest_root = repo / "latest" / "readiness_dashboards"
    history_root = repo / "history" / "readiness_dashboards" / ts
    chat_root = repo / "latest" / "chat_context"
    for root in (latest_root, history_root, chat_root):
        root.mkdir(parents=True, exist_ok=True)

    outputs = {
        latest_root / "combined_readiness_dashboard.json": state,
        latest_root / "race_predictions_readiness_state.json": {"generated_at_utc": state["generated_at_utc"], **state["race_predictions"], "event": state["event"], "source_status": state["source_status"], "artifacts": state["artifacts"], "governance": state["governance"]},
        latest_root / "fantasy_readiness_state.json": {"generated_at_utc": state["generated_at_utc"], **state["fantasy"], "event": state["event"], "source_status": state["source_status"], "artifacts": state["artifacts"], "governance": state["governance"]},
        history_root / "combined_readiness_dashboard.json": state,
    }
    for path, data in outputs.items():
        write_json(path, data)

    md = md_dashboard(state)
    write_text(latest_root / "combined_readiness_dashboard.md", md)
    write_text(history_root / "combined_readiness_dashboard.md", md)
    write_text(latest_root / "race_predictions_latest_session_brief.md", race_brief(state))
    write_text(latest_root / "fantasy_latest_session_brief.md", fantasy_brief(state))
    write_text(chat_root / "RACE_PREDICTIONS_LATEST_SESSION_BRIEF.md", race_brief(state))
    write_text(chat_root / "FANTASY_PREDICTIONS_LATEST_SESSION_BRIEF.md", fantasy_brief(state))

    manifest = {
        "generated_at_utc": state["generated_at_utc"],
        "status": state["status"],
        "source_status": state["source_status"],
        "material_change": state["material_change"],
        "outputs": [],
        "governance": state["governance"],
    }
    for p in sorted(list(latest_root.glob("*")) + list(chat_root.glob("*_LATEST_SESSION_BRIEF.md"))):
        if p.is_file():
            manifest["outputs"].append({"path": str(p.relative_to(repo)), "sha256": sha256_file(p)})
    write_json(latest_root / "dashboard_manifest.json", manifest)
    write_json(history_root / "dashboard_manifest.json", manifest)
    write_json(latest_root / "material_state_change.json", {"material_change": state["material_change"], "diff": state["material_change_diff"]})
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=["safe_test", "run_now"], default="run_now")
    parser.add_argument("--runtime-dir", default="_runtime/dashboard_connector")
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    state = publish(repo, args.mode, Path(args.runtime_dir))
    print(json.dumps({
        "status": state["status"],
        "source_status": state["source_status"],
        "source_backed": state["source_backed"],
        "material_change": state["material_change"],
        "commit_allowed": state["commit_allowed"],
        "event": state["event"],
        "stable_engine_modified": state["governance"]["stable_engine_modified"],
        "canonical_workbook_overwrite": state["governance"]["canonical_workbook_overwrite"],
        "promotion_allowed": state["governance"]["promotion_allowed"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
