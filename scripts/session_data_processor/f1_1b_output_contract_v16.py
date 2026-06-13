#!/usr/bin/env python3
"""F1 1B Processor Output Contract v16.

Purpose:
- Create Forecast Bundle Ledger snapshots from latest source/workbook readiness.
- Maintain last-good state.
- Produce material-change reports.
- Write Race/Fantasy/Race Reports handoff manifests.

Safety:
- Writes only latest/forecast_bundle_ledger, history/forecast_bundle_ledger,
  latest/readiness_handoff, latest/material_change, latest/last_good_state.json,
  and latest/1b_output_contract.
- Does not touch stable engine files, canonical workbook files, or model promotion state.
- Uses only Python standard library.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = "f1_1b_output_contract_v16"
CLEANISH_SOURCE_STATES = {"clean", "usable", "source_backed", "partial"}
CLEANISH_WORKBOOK_STATES = {"clean", "usable", "source_backed", "refresh_applied", "partial"}

WRITE_PREFIXES = (
    "latest/forecast_bundle_ledger/",
    "history/forecast_bundle_ledger/",
    "latest/readiness_handoff/",
    "latest/material_change/",
    "latest/1b_output_contract/",
)
WRITE_FILES = ("latest/last_good_state.json",)
PROTECTED_MARKERS = (
    "Engine_2026-06-07_STABLE",
    "F1_2026_Prediction_Model_Data_Workbook",
)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_stamp(ts: Optional[dt.datetime] = None) -> str:
    ts = ts or utc_now()
    return ts.strftime("%Y%m%dT%H%M%SZ")


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"value": data}
    except Exception as exc:
        return {"_load_error": str(exc), "_path": str(path)}


def write_json(path: Path, data: Dict[str, Any]) -> None:
    safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def sha256_json(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def safe_write_path(path: Path) -> None:
    norm = path.as_posix()
    if "/.git/" in norm or norm.startswith(".git/") or "\\.git\\" in str(path):
        raise RuntimeError(f"Refusing to write inside .git: {path}")
    for marker in PROTECTED_MARKERS:
        if marker in norm:
            raise RuntimeError(f"Refusing to write protected path containing {marker}: {path}")


def newest(paths: Iterable[Path]) -> Optional[Path]:
    files = [p for p in paths if p.exists() and p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: (p.stat().st_mtime, str(p)))


def find_latest_session_manifest(root: Path) -> Tuple[Optional[Path], Dict[str, Any]]:
    candidates = list((root / "latest" / "session_data_processor").glob("**/source_readiness_manifest.json"))
    p = newest(candidates)
    return p, (load_json(p) if p else {}) or {}


def find_latest_workbook_manifest(root: Path) -> Tuple[Optional[Path], Dict[str, Any]]:
    direct = root / "latest" / "workbook_kpi_refresh_applier" / "workbook_kpi_refresh_manifest.json"
    if direct.exists():
        return direct, load_json(direct) or {}
    candidates = list((root / "latest").glob("**/workbook_kpi_refresh_manifest.json"))
    p = newest(candidates)
    return p, (load_json(p) if p else {}) or {}


def find_latest_dashboard_manifest(root: Path) -> Tuple[Optional[Path], Dict[str, Any]]:
    names = [
        "forecast_fantasy_readiness_dashboard.json",
        "dashboard_state.json",
        "readiness_dashboard.json",
        "forecast_fantasy_readiness_manifest.json",
    ]
    candidates: List[Path] = []
    for name in names:
        candidates += list((root / "latest").glob(f"**/{name}"))
    p = newest(candidates)
    return p, (load_json(p) if p else {}) or {}


def first(data: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def normalize_status(s: Any) -> str:
    if s is None:
        return "unknown"
    return str(s).strip().lower()


def is_cleanish_source(manifest: Dict[str, Any]) -> bool:
    status = normalize_status(first(manifest, ["overall_status", "source_status", "status"]))
    manual = bool(manifest.get("source_needs_manual_review", False))
    quality = normalize_status(manifest.get("readiness_quality"))
    if manual:
        return False
    if status == "clean":
        return True
    if quality == "usable_with_optional_context_gaps":
        return True
    return status in CLEANISH_SOURCE_STATES and status not in {"needs_manual_review", "blocked", "conflicting", "late"}


def is_cleanish_workbook(manifest: Dict[str, Any]) -> bool:
    status = normalize_status(first(manifest, ["workbook_source_status", "source_status", "status"]))
    if status in {"needs_manual_review", "blocked", "conflicting", "late", "unknown"}:
        return False
    return status in CLEANISH_WORKBOOK_STATES or status == "clean"


def classify_handoffs(source_manifest: Dict[str, Any], workbook_manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    source_ok = is_cleanish_source(source_manifest)
    workbook_ok = is_cleanish_workbook(workbook_manifest)
    source_status = first(source_manifest, ["overall_status", "source_status", "status"], "unknown")
    quality = source_manifest.get("readiness_quality", "unknown")
    workbook_status = first(workbook_manifest, ["workbook_source_status", "source_status", "status"], "unknown")
    session_type = str(source_manifest.get("session_type") or source_manifest.get("session_name") or "unknown")
    base = {
        "source_status": source_status,
        "workbook_source_status": workbook_status,
        "readiness_quality": quality,
        "session_type": session_type,
        "source_needs_manual_review": bool(source_manifest.get("source_needs_manual_review", False)),
    }
    race_ready = source_ok and workbook_ok
    fantasy_ready = source_ok and workbook_ok
    # Race reports should consume readiness state, but full report creation should stay gated until post-qualifying/race context exists.
    report_context_ready = source_ok and workbook_ok
    full_report_ready = report_context_ready and any(token in session_type.lower() for token in ["qualifying", "sprint", "race"])
    return {
        "race_predictions": {
            **base,
            "ready_for_use": race_ready,
            "blocked": not race_ready,
            "allowed_effect": "readiness/confidence/risk context only; stable P1-P20 not overwritten",
        },
        "fantasy_predictions": {
            **base,
            "ready_for_use": fantasy_ready,
            "blocked": not fantasy_ready,
            "allowed_effect": "value/risk/readiness context only; no automatic transfer execution",
        },
        "race_reports": {
            **base,
            "ready_for_readiness_context": report_context_ready,
            "ready_for_full_report": full_report_ready,
            "blocked": not report_context_ready,
            "allowed_effect": "report readiness/context only; no Full Report PDF generated automatically",
        },
    }


def build_snapshot(root: Path, run_id: str) -> Dict[str, Any]:
    session_path, session = find_latest_session_manifest(root)
    workbook_path, workbook = find_latest_workbook_manifest(root)
    dashboard_path, dashboard = find_latest_dashboard_manifest(root)

    source_counts = session.get("source_counts") if isinstance(session.get("source_counts"), dict) else {}
    source_statuses = session.get("source_statuses") if isinstance(session.get("source_statuses"), dict) else {}
    optional_gaps = [k for k, v in source_counts.items() if int(v or 0) == 0 and k in {"openf1_starting_grid", "openf1_intervals"}]
    handoffs = classify_handoffs(session, workbook)

    source_ok = is_cleanish_source(session)
    workbook_ok = is_cleanish_workbook(workbook)
    overall_status = "usable" if source_ok and workbook_ok else "blocked"
    if source_ok and workbook_ok and normalize_status(session.get("readiness_quality")) == "usable_with_optional_context_gaps":
        overall_status = "usable_with_optional_context_gaps"

    event_id = first(session, ["event_id"], "unknown_event")
    race_name = first(session, ["race_name", "event_name"], "unknown_event")
    session_name = first(session, ["session_name"], "unknown_session")
    session_key = first(session, ["session_key"], None)

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "run_id": run_id,
        "status": overall_status,
        "source_backed": source_ok,
        "workbook_ready": workbook_ok,
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "event": {
            "event_id": event_id,
            "race_name": race_name,
            "session_name": session_name,
            "session_key": session_key,
        },
        "source": {
            "manifest_path": relpath(session_path, root) if session_path else None,
            "status": first(session, ["overall_status", "source_status", "status"], "unknown"),
            "readiness_quality": session.get("readiness_quality", "unknown"),
            "needs_manual_review": bool(session.get("source_needs_manual_review", False)),
            "source_counts": source_counts,
            "source_statuses": source_statuses,
            "optional_context_gaps": optional_gaps,
        },
        "workbook": {
            "manifest_path": relpath(workbook_path, root) if workbook_path else None,
            "status": first(workbook, ["workbook_source_status", "source_status", "status"], "unknown"),
            "sandbox_workbook": workbook.get("sandbox_workbook") or workbook.get("workbook_artifact"),
            "canonical_workbook_overwrite": bool(workbook.get("canonical_workbook_overwrite", False)),
        },
        "dashboard": {
            "manifest_path": relpath(dashboard_path, root) if dashboard_path else None,
            "status": first(dashboard, ["status"], "unknown"),
        },
        "handoffs": handoffs,
    }
    snapshot["signature"] = sha256_json({
        "status": snapshot["status"],
        "event": snapshot["event"],
        "source": snapshot["source"],
        "workbook": snapshot["workbook"],
        "handoffs": snapshot["handoffs"],
    })
    return snapshot


def detect_material_change(root: Path, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    sig_path = root / "latest" / "material_change" / "last_signature.json"
    previous = load_json(sig_path) or {}
    previous_sig = previous.get("signature")
    current_sig = snapshot.get("signature")
    changed = previous_sig != current_sig
    report = {
        "schema_version": "f1_1b_material_change_v16",
        "generated_at_utc": utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "material_change_detected": changed,
        "previous_signature": previous_sig,
        "current_signature": current_sig,
        "notification_recommended": bool(changed and snapshot.get("source_backed") and snapshot.get("workbook_ready")),
        "change_reason": "signature_changed" if changed else "no_material_change",
        "event": snapshot.get("event", {}),
        "status": snapshot.get("status"),
        "promotion_allowed": False,
    }
    write_json(root / "latest" / "material_change" / "material_change_report.json", report)
    write_json(sig_path, {"signature": current_sig, "updated_at_utc": report["generated_at_utc"], "event": snapshot.get("event", {})})
    return report


def write_outputs(root: Path, snapshot: Dict[str, Any], change_report: Dict[str, Any]) -> Dict[str, Any]:
    event_id = str(snapshot.get("event", {}).get("event_id") or "unknown_event").replace("/", "_").replace(" ", "_")
    run_id = str(snapshot.get("run_id"))
    latest_ledger = root / "latest" / "forecast_bundle_ledger"
    history_ledger = root / "history" / "forecast_bundle_ledger" / event_id / run_id
    handoff_root = root / "latest" / "readiness_handoff"
    output_root = root / "latest" / "1b_output_contract"

    write_json(latest_ledger / "latest_bundle_snapshot.json", snapshot)
    write_json(history_ledger / "bundle_snapshot.json", snapshot)
    write_json(history_ledger / "material_change_report.json", change_report)

    rows = []
    for name, item in snapshot.get("handoffs", {}).items():
        rows.append({"consumer": name, **item})
        write_json(handoff_root / f"{name}_readiness.json", item)
    write_json(handoff_root / "combined_readiness_handoff.json", {
        "schema_version": "f1_1b_combined_readiness_handoff_v16",
        "generated_at_utc": snapshot.get("generated_at_utc"),
        "event": snapshot.get("event"),
        "source_status": snapshot.get("source", {}).get("status"),
        "workbook_status": snapshot.get("workbook", {}).get("status"),
        "handoffs": snapshot.get("handoffs", {}),
        "promotion_allowed": False,
    })
    write_csv(handoff_root / "combined_readiness_handoff.csv", rows)

    if snapshot.get("source_backed") and snapshot.get("workbook_ready"):
        write_json(root / "latest" / "last_good_state.json", {
            "schema_version": "f1_1b_last_good_state_v16",
            "updated_at_utc": snapshot.get("generated_at_utc"),
            "run_id": snapshot.get("run_id"),
            "event": snapshot.get("event"),
            "status": snapshot.get("status"),
            "snapshot_path": relpath(latest_ledger / "latest_bundle_snapshot.json", root),
            "history_snapshot_path": relpath(history_ledger / "bundle_snapshot.json", root),
            "signature": snapshot.get("signature"),
            "promotion_allowed": False,
        })

    contract_report = {
        "schema_version": "f1_1b_output_contract_report_v16",
        "status": "pass" if snapshot.get("source_backed") else "blocked",
        "generated_at_utc": snapshot.get("generated_at_utc"),
        "run_id": snapshot.get("run_id"),
        "ledger_snapshot_created": True,
        "last_good_state_updated": bool(snapshot.get("source_backed") and snapshot.get("workbook_ready")),
        "material_change_detected": change_report.get("material_change_detected"),
        "notification_recommended": change_report.get("notification_recommended"),
        "source_status": snapshot.get("source", {}).get("status"),
        "workbook_source_status": snapshot.get("workbook", {}).get("status"),
        "readiness_quality": snapshot.get("source", {}).get("readiness_quality"),
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "outputs": {
            "latest_bundle_snapshot": relpath(latest_ledger / "latest_bundle_snapshot.json", root),
            "history_bundle_snapshot": relpath(history_ledger / "bundle_snapshot.json", root),
            "material_change_report": "latest/material_change/material_change_report.json",
            "last_good_state": "latest/last_good_state.json",
            "combined_handoff": "latest/readiness_handoff/combined_readiness_handoff.json",
        },
    }
    write_json(output_root / "output_contract_report.json", contract_report)
    return contract_report


def run(repo_root: Path, mode: str = "run_now") -> Dict[str, Any]:
    run_id = utc_stamp()
    snapshot = build_snapshot(repo_root, run_id)
    change = detect_material_change(repo_root, snapshot)
    report = write_outputs(repo_root, snapshot, change)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--mode", default="run_now", choices=["run_now", "safe_test"])
    args = ap.parse_args()
    root = Path(args.repo_root).resolve()
    report = run(root, mode=args.mode)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
