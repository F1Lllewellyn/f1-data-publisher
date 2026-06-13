#!/usr/bin/env python3
"""F1 1B Processor Output Contract v19 wiring fix.

Purpose:
- Prefer the newest clean/usable processor readiness state instead of stale blocked manifests.
- Allow dashboard readiness handoff to provide authoritative source/workbook state when it is newer/cleaner.
- Create Forecast Bundle Ledger snapshots, last-good state, material-change reports, and downstream handoffs.

Safety:
- Writes only latest/forecast_bundle_ledger, history/forecast_bundle_ledger,
  latest/readiness_handoff, latest/material_change, latest/1b_output_contract,
  and latest/last_good_state.json.
- Does not touch stable engine files, canonical workbook files, .git, or model promotion state.
- Uses only Python standard library.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = "f1_1b_output_contract_v19"
CLEANISH_SOURCE_STATES = {"clean", "usable", "source_backed", "partial"}
CLEANISH_WORKBOOK_STATES = {"clean", "usable", "source_backed", "refresh_applied", "partial"}
PROTECTED_MARKERS = ("Engine_2026-06-07_STABLE", "F1_2026_Prediction_Model_Data_Workbook")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_stamp(ts: Optional[dt.datetime] = None) -> str:
    return (ts or utc_now()).strftime("%Y%m%dT%H%M%SZ")


def relpath(path: Optional[Path], root: Path) -> Optional[str]:
    if not path:
        return None
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path or not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"value": data}
    except Exception as exc:
        return {"_load_error": str(exc), "_path": str(path)}


def safe_write_path(path: Path) -> None:
    parts = set(path.parts)
    if ".git" in parts:
        raise RuntimeError(f"Refusing to write inside .git: {path}")
    norm = path.as_posix()
    for marker in PROTECTED_MARKERS:
        if marker in norm:
            raise RuntimeError(f"Refusing to write protected path containing {marker}: {path}")


def write_json(path: Path, data: Dict[str, Any]) -> None:
    safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: List[str] = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def sha256_json(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def first(data: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def normalize_status(s: Any) -> str:
    return "unknown" if s is None else str(s).strip().lower()


def parse_run_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def source_status(data: Dict[str, Any]) -> str:
    return normalize_status(first(data, ["overall_status", "source_status", "status"]))


def workbook_status(data: Dict[str, Any]) -> str:
    return normalize_status(first(data, ["workbook_source_status", "source_status", "status"]))


def is_cleanish_source(manifest: Dict[str, Any]) -> bool:
    status = source_status(manifest)
    manual = bool(manifest.get("source_needs_manual_review", False))
    quality = normalize_status(manifest.get("readiness_quality"))
    if manual:
        return False
    if status == "clean":
        return True
    if quality == "usable_with_optional_context_gaps":
        return True
    return status in CLEANISH_SOURCE_STATES and status not in {"needs_manual_review", "blocked", "conflicting", "late", "unknown"}


def is_cleanish_workbook(manifest: Dict[str, Any]) -> bool:
    status = workbook_status(manifest)
    if status in {"needs_manual_review", "blocked", "conflicting", "late", "unknown"}:
        return False
    return status in CLEANISH_WORKBOOK_STATES or status == "clean"


def status_score_source(data: Dict[str, Any]) -> int:
    if not data:
        return -100
    status = source_status(data)
    quality = normalize_status(data.get("readiness_quality"))
    score = 0
    if bool(data.get("source_needs_manual_review", False)):
        score -= 80
    if status == "clean": score += 100
    elif status in {"usable", "source_backed"}: score += 85
    elif status == "partial": score += 40
    elif status in {"needs_manual_review", "blocked", "conflicting", "late"}: score -= 50
    if quality == "usable_with_optional_context_gaps": score += 30
    if data.get("source_counts"): score += 5
    return score


def status_score_workbook(data: Dict[str, Any]) -> int:
    if not data:
        return -100
    status = workbook_status(data)
    score = 0
    if status == "clean": score += 100
    elif status in {"refresh_applied", "usable", "source_backed"}: score += 85
    elif status == "partial": score += 40
    elif status in {"needs_manual_review", "blocked", "conflicting", "late", "unknown"}: score -= 50
    if data.get("sandbox_workbook") or data.get("workbook_artifact"): score += 10
    return score


def newest_by_score(paths: Iterable[Path], root: Path, kind: str) -> Tuple[Optional[Path], Dict[str, Any], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    best: Tuple[int, str, str, Optional[Path], Dict[str, Any]] = (-999, "", "", None, {})
    for p in paths:
        data = load_json(p) or {}
        score = status_score_source(data) if kind == "source" else status_score_workbook(data)
        run_id = parse_run_id(data.get("run_id") or data.get("generated_at_utc") or data.get("created_utc"))
        mtime = ""
        try:
            mtime = str(int(p.stat().st_mtime))
        except Exception:
            pass
        rows.append({"path": relpath(p, root), "score": score, "status": source_status(data) if kind == "source" else workbook_status(data), "run_id": run_id})
        key = (score, run_id, mtime, p, data)
        if key[:3] > best[:3]:
            best = key
    return best[3], best[4], rows


def find_latest_dashboard_manifest(root: Path) -> Tuple[Optional[Path], Dict[str, Any], List[Dict[str, Any]]]:
    names = [
        "combined_readiness_dashboard.json",
        "forecast_fantasy_readiness_dashboard.json",
        "dashboard_state.json",
        "readiness_dashboard.json",
        "forecast_fantasy_readiness_manifest.json",
    ]
    candidates: List[Path] = []
    for name in names:
        candidates += list((root / "latest").glob(f"**/{name}"))
    rows: List[Dict[str, Any]] = []
    best: Tuple[int, str, str, Optional[Path], Dict[str, Any]] = (-999, "", "", None, {})
    for p in candidates:
        data = load_json(p) or {}
        score = 0
        if normalize_status(data.get("source_status")) == "clean": score += 100
        if bool(data.get("source_backed", False)): score += 50
        if data.get("session_manifest"): score += 20
        if data.get("workbook_manifest"): score += 20
        if data.get("workbook_artifact"): score += 10
        run_id = parse_run_id(data.get("run_id") or data.get("generated_at_utc") or data.get("created_utc"))
        mtime = str(int(p.stat().st_mtime)) if p.exists() else ""
        rows.append({"path": relpath(p, root), "score": score, "source_status": data.get("source_status"), "source_backed": data.get("source_backed"), "run_id": run_id})
        key = (score, run_id, mtime, p, data)
        if key[:3] > best[:3]:
            best = key
    return best[3], best[4], rows


def path_from_manifest_ref(root: Path, ref: Any) -> Optional[Path]:
    if not ref or not isinstance(ref, str):
        return None
    p = Path(ref)
    if not p.is_absolute():
        p = root / p
    return p if p.exists() else None


def apply_dashboard_source_overlay(source: Dict[str, Any], dashboard: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(source or {})
    dash_status = normalize_status(dashboard.get("source_status"))
    if dash_status == "clean" or bool(dashboard.get("source_backed", False)):
        out.setdefault("schema_version", "dashboard_backed_source_state_v19")
        out["overall_status"] = dashboard.get("source_status", "clean")
        out["source_status"] = dashboard.get("source_status", "clean")
        out["source_needs_manual_review"] = False
        out["readiness_quality"] = "usable_with_optional_context_gaps"
        sess = dashboard.get("session_name")
        if isinstance(sess, dict):
            out.setdefault("session_key", sess.get("session_key"))
            out.setdefault("session_name", sess.get("session_name"))
            out.setdefault("session_type", sess.get("session_type"))
            out.setdefault("gate", sess.get("gate"))
        out.setdefault("race_name", dashboard.get("event_name") or dashboard.get("race_name"))
    return out


def apply_dashboard_workbook_overlay(workbook: Dict[str, Any], dashboard: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(workbook or {})
    if normalize_status(dashboard.get("source_status")) == "clean" and dashboard.get("workbook_artifact"):
        out["status"] = "refresh_applied"
        out["source_status"] = "clean"
        out["workbook_source_status"] = "clean"
        out.setdefault("sandbox_workbook", dashboard.get("workbook_artifact"))
        out.setdefault("canonical_workbook_overwrite", False)
        out.setdefault("promotion_allowed", False)
    return out


def find_latest_session_manifest(root: Path) -> Tuple[Optional[Path], Dict[str, Any], Dict[str, Any]]:
    dashboard_path, dashboard, dash_rows = find_latest_dashboard_manifest(root)
    candidates: List[Path] = list((root / "latest" / "session_data_processor").glob("**/source_readiness_manifest.json"))
    dp = path_from_manifest_ref(root, dashboard.get("session_manifest"))
    if dp and dp not in candidates:
        candidates.append(dp)
    source_path, source, rows = newest_by_score(candidates, root, "source")
    # If dashboard says the same processor chain is clean/source-backed, use it as readiness authority.
    # This prevents older stale source_readiness_manifest.json files from downgrading the output contract.
    if dashboard and (normalize_status(dashboard.get("source_status")) == "clean" or bool(dashboard.get("source_backed", False))):
        source = apply_dashboard_source_overlay(source, dashboard)
    selection = {
        "dashboard_path": relpath(dashboard_path, root),
        "dashboard_candidates": dash_rows,
        "selected_source_manifest": relpath(source_path, root),
        "source_candidates": rows,
        "selection_rule": "prefer_clean_dashboard_backed_state_then_best_source_manifest",
    }
    return source_path, source, selection


def find_latest_workbook_manifest(root: Path) -> Tuple[Optional[Path], Dict[str, Any], Dict[str, Any]]:
    dashboard_path, dashboard, dash_rows = find_latest_dashboard_manifest(root)
    candidates: List[Path] = []
    direct = root / "latest" / "workbook_kpi_refresh_applier" / "workbook_kpi_refresh_manifest.json"
    if direct.exists():
        candidates.append(direct)
    candidates += list((root / "latest").glob("**/workbook_kpi_refresh_manifest.json"))
    dp = path_from_manifest_ref(root, dashboard.get("workbook_manifest"))
    if dp and dp not in candidates:
        candidates.append(dp)
    workbook_path, workbook, rows = newest_by_score(candidates, root, "workbook")
    if dashboard:
        workbook = apply_dashboard_workbook_overlay(workbook, dashboard)
    selection = {
        "dashboard_path": relpath(dashboard_path, root),
        "dashboard_candidates": dash_rows,
        "selected_workbook_manifest": relpath(workbook_path, root),
        "workbook_candidates": rows,
        "selection_rule": "prefer_clean_dashboard_backed_workbook_state_then_best_workbook_manifest",
    }
    return workbook_path, workbook, selection


def classify_handoffs(source_manifest: Dict[str, Any], workbook_manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    source_ok = is_cleanish_source(source_manifest)
    workbook_ok = is_cleanish_workbook(workbook_manifest)
    source_state = first(source_manifest, ["overall_status", "source_status", "status"], "unknown")
    quality = source_manifest.get("readiness_quality", "unknown")
    workbook_state = first(workbook_manifest, ["workbook_source_status", "source_status", "status"], "unknown")
    session_type = str(source_manifest.get("session_type") or source_manifest.get("session_name") or "unknown")
    base = {
        "source_status": source_state,
        "workbook_source_status": workbook_state,
        "readiness_quality": quality,
        "session_type": session_type,
        "source_needs_manual_review": bool(source_manifest.get("source_needs_manual_review", False)),
    }
    ready = source_ok and workbook_ok
    report_context_ready = ready
    full_report_ready = report_context_ready and any(t in session_type.lower() for t in ["qualifying", "sprint", "race"])
    return {
        "race_predictions": {**base, "ready_for_use": ready, "blocked": not ready, "allowed_effect": "readiness/confidence/risk context only; stable P1-P20 not overwritten"},
        "fantasy_predictions": {**base, "ready_for_use": ready, "blocked": not ready, "allowed_effect": "value/risk/readiness context only; no automatic transfer execution"},
        "race_reports": {**base, "ready_for_readiness_context": report_context_ready, "ready_for_full_report": full_report_ready, "blocked": not report_context_ready, "allowed_effect": "report readiness/context only; no Full Report PDF generated automatically"},
    }


def build_snapshot(root: Path, run_id: str) -> Dict[str, Any]:
    session_path, session, source_selection = find_latest_session_manifest(root)
    workbook_path, workbook, workbook_selection = find_latest_workbook_manifest(root)
    dashboard_path, dashboard, dash_rows = find_latest_dashboard_manifest(root)

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
    race_name = first(session, ["race_name", "event_name"], dashboard.get("event_name", "unknown_event") if dashboard else "unknown_event")
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
        "event": {"event_id": event_id, "race_name": race_name, "session_name": session_name, "session_key": session_key},
        "source": {
            "manifest_path": relpath(session_path, root),
            "status": first(session, ["overall_status", "source_status", "status"], "unknown"),
            "readiness_quality": session.get("readiness_quality", "unknown"),
            "needs_manual_review": bool(session.get("source_needs_manual_review", False)),
            "source_counts": source_counts,
            "source_statuses": source_statuses,
            "optional_context_gaps": optional_gaps,
        },
        "workbook": {
            "manifest_path": relpath(workbook_path, root),
            "status": first(workbook, ["workbook_source_status", "source_status", "status"], "unknown"),
            "sandbox_workbook": workbook.get("sandbox_workbook") or workbook.get("workbook_artifact"),
            "canonical_workbook_overwrite": bool(workbook.get("canonical_workbook_overwrite", False)),
        },
        "dashboard": {"manifest_path": relpath(dashboard_path, root), "status": first(dashboard, ["status"], "unknown"), "source_status": dashboard.get("source_status") if dashboard else None, "source_backed": dashboard.get("source_backed") if dashboard else None},
        "input_selection": {"source": source_selection, "workbook": workbook_selection, "dashboard_candidates": dash_rows},
        "handoffs": handoffs,
    }
    snapshot["signature"] = sha256_json({"status": snapshot["status"], "event": snapshot["event"], "source": snapshot["source"], "workbook": snapshot["workbook"], "handoffs": snapshot["handoffs"]})
    return snapshot


def detect_material_change(root: Path, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    sig_path = root / "latest" / "material_change" / "last_signature.json"
    previous = load_json(sig_path) or {}
    previous_sig = previous.get("signature")
    current_sig = snapshot.get("signature")
    changed = previous_sig != current_sig
    report = {
        "schema_version": "f1_1b_material_change_v19",
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
    write_json(output_root / "input_selection_report.json", snapshot.get("input_selection", {}))

    rows: List[Dict[str, Any]] = []
    for name, item in snapshot.get("handoffs", {}).items():
        rows.append({"consumer": name, **item})
        write_json(handoff_root / f"{name}_readiness.json", item)
    write_json(handoff_root / "combined_readiness_handoff.json", {
        "schema_version": "f1_1b_combined_readiness_handoff_v19",
        "generated_at_utc": snapshot.get("generated_at_utc"),
        "event": snapshot.get("event"),
        "source_status": snapshot.get("source", {}).get("status"),
        "workbook_status": snapshot.get("workbook", {}).get("status"),
        "readiness_quality": snapshot.get("source", {}).get("readiness_quality"),
        "handoffs": snapshot.get("handoffs", {}),
        "promotion_allowed": False,
    })
    write_csv(handoff_root / "combined_readiness_handoff.csv", rows)

    last_good_updated = bool(snapshot.get("source_backed") and snapshot.get("workbook_ready"))
    if last_good_updated:
        write_json(root / "latest" / "last_good_state.json", {
            "schema_version": "f1_1b_last_good_state_v19",
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
        "schema_version": "f1_1b_output_contract_report_v19",
        "status": "pass" if snapshot.get("source_backed") else "blocked",
        "generated_at_utc": snapshot.get("generated_at_utc"),
        "run_id": snapshot.get("run_id"),
        "ledger_snapshot_created": True,
        "last_good_state_updated": last_good_updated,
        "material_change_detected": change_report.get("material_change_detected"),
        "notification_recommended": change_report.get("notification_recommended"),
        "source_status": snapshot.get("source", {}).get("status"),
        "workbook_source_status": snapshot.get("workbook", {}).get("status"),
        "readiness_quality": snapshot.get("source", {}).get("readiness_quality"),
        "input_selection": snapshot.get("input_selection", {}),
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "outputs": {
            "latest_bundle_snapshot": relpath(latest_ledger / "latest_bundle_snapshot.json", root),
            "history_bundle_snapshot": relpath(history_ledger / "bundle_snapshot.json", root),
            "material_change_report": "latest/material_change/material_change_report.json",
            "last_good_state": "latest/last_good_state.json" if last_good_updated else None,
            "combined_handoff": "latest/readiness_handoff/combined_readiness_handoff.json",
            "input_selection_report": "latest/1b_output_contract/input_selection_report.json",
        },
    }
    write_json(output_root / "output_contract_report.json", contract_report)
    return contract_report


def run(repo_root: Path, mode: str = "run_now") -> Dict[str, Any]:
    run_id = utc_stamp()
    snapshot = build_snapshot(repo_root, run_id)
    change = detect_material_change(repo_root, snapshot)
    return write_outputs(repo_root, snapshot, change)


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
