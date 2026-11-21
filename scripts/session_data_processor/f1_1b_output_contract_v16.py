#!/usr/bin/env python3
"""F1 1B current-authority output contract with immutable context custody.

Purpose:
- Revalidate the authoritative current session and its exact source/workbook bytes.
- Retain original capture identity and fail closed on missing or stale evidence.
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
import importlib.util
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = "f1_1b_output_contract_v20"
CLEANISH_SOURCE_STATES = {"clean", "usable", "source_backed", "partial"}
CLEANISH_WORKBOOK_STATES = {"clean", "usable", "source_backed", "refresh_applied", "partial"}
PROTECTED_MARKERS = ("Engine_2026-06-07_STABLE", "F1_2026_Prediction_Model_Data_Workbook")


def current_custody(root: Path, now: dt.datetime) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Reverify authoritative current bytes; never rank old green manifests."""
    path = Path(__file__).resolve().parents[1] / "dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py"
    spec = importlib.util.spec_from_file_location("consumer_current_dashboard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = module.discover_state(root, reference_time=now)
    source = load_json(root / state["session_manifest"]) if state.get("session_manifest") else {}
    source = source or {}
    custody = {
        "schema": "current-context-custody-v1",
        "event_id": state.get("event_id"), "meeting_key": state.get("meeting_key"),
        "session_key": state.get("session_key"), "expected_session_key": state.get("expected_session_key"),
        "source_run_id": source.get("run_id"),
        "capture_origin": source.get("capture_origin", {}),
        "source_availability": {name: report.get("observed_at_utc") for name, report in source.get("sources", {}).items() if isinstance(report, dict)},
        "input_fingerprints": state.get("consumed_fingerprints", {}),
        "context_eligible": state.get("downstream_eligible") is True,
        "prediction_locked": False, "stable_engine_executed": False,
    }
    return state, custody


def safe_component(value: Any) -> str:
    text = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise RuntimeError("HOLD_INVALID_OUTPUT_IDENTITY")
    return text


def bound_inputs(root: Path, paths: Dict[str, str]) -> Dict[str, str]:
    result = {}
    for relative in paths.values():
        path = root / relative
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)) or not path.resolve().is_relative_to(root.resolve()):
            raise RuntimeError("HOLD_CONSUMER_INPUT_CUSTODY:" + relative)
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verify_bound_chain(root: Path, documents: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    state, custody = current_custody(root, now)
    if not custody["context_eligible"]:
        raise RuntimeError("HOLD_CURRENT_CONTEXT:" + ",".join(state["readiness_reasons"]))
    run_id = "context_" + sha256_json(custody)[:32]
    for document in documents:
        if document.get("custody") != custody or document.get("run_id") != run_id:
            raise RuntimeError("HOLD_UPSTREAM_CONTEXT_IDENTITY")
        event = document.get("event")
        if event is not None and any(event.get(key) != custody[key] for key in ("event_id", "meeting_key", "session_key")):
            raise RuntimeError("HOLD_UPSTREAM_EVENT_IDENTITY")
    return custody


class OutputBatch:
    """Preflight every historical collision before publishing any latest file."""
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.outputs = {}

    def add(self, path: Path, raw: bytes) -> None:
        safe_write_path(path)
        if not path.resolve().is_relative_to(self.root) or any(p.is_symlink() for p in (path, *path.parents)):
            raise RuntimeError("HOLD_OUTPUT_PATH_CUSTODY")
        if path in self.outputs and self.outputs[path] != raw:
            raise RuntimeError("HOLD_CONFLICTING_OUTPUT_BATCH")
        self.outputs[path] = raw

    def json(self, path: Path, data: Any) -> None:
        self.add(path, (json.dumps(data, indent=2, sort_keys=True) + "\n").encode())

    def text(self, path: Path, data: str) -> None:
        self.add(path, (data.rstrip() + "\n").encode())

    def csv(self, path: Path, rows: List[Dict[str, Any]]) -> None:
        import io
        text = io.StringIO(newline="")
        fields = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(text, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
        self.add(path, text.getvalue().encode())

    def commit(self) -> None:
        historical = lambda p: p.relative_to(self.root).parts[0] == "history"
        for path, raw in self.outputs.items():
            if historical(path) and path.exists() and path.read_bytes() != raw:
                raise RuntimeError("HOLD_IMMUTABLE_HISTORY_COLLISION:" + str(path.relative_to(self.root)))
        for path, raw in sorted(self.outputs.items(), key=lambda item: not historical(item[0])):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_bytes() == raw:
                continue
            if historical(path):
                with path.open("xb") as out:
                    out.write(raw)
            else:
                temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
                with temporary.open("xb") as out:
                    out.write(raw)
                os.replace(temporary, path)


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
    if manual or has_critical_source_gap(manifest) or status in {"needs_manual_review", "blocked", "conflicting", "late", "unknown"}:
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


def has_critical_source_gap(manifest: Dict[str, Any]) -> bool:
    """Return True only when a critical source appears missing/conflicting.

    Optional practice-context gaps such as starting grid and intervals must not
    downgrade an otherwise usable practice session.  This intentionally avoids
    treating absent source_counts as a critical gap, because dashboard-backed
    handoff states may not include endpoint counts.
    """
    if manifest.get("source_identity_error"):
        return True
    # The session processor's own aggregation is more authoritative than a
    # dashboard summary. Current processor manifests put endpoint findings
    # here, not in the older flat source_counts/source_statuses fields.
    aggregation = manifest.get("readiness_aggregation")
    if isinstance(aggregation, dict):
        if aggregation.get("needs_manual_review") or any(aggregation.get(k) for k in
            ("blocking_issues", "critical_late", "missing_required_endpoints")):
            return True
        if normalize_status(aggregation.get("overall_status")) in {"conflicting", "needs_manual_review", "late", "no_data"}:
            return True
    counts = manifest.get("source_counts") if isinstance(manifest.get("source_counts"), dict) else {}
    statuses = manifest.get("source_statuses") if isinstance(manifest.get("source_statuses"), dict) else {}
    session = manifest.get("session") if isinstance(manifest.get("session"), dict) else manifest
    session_type = str(session.get("session_type") or session.get("session_name") or "").lower()
    race_session = "race" in session_type or ("sprint" in session_type and "qualifying" not in session_type)
    optional = {"openf1_intervals"}
    if not race_session:
        optional.add("openf1_starting_grid")
    critical = {"openf1_drivers", "openf1_laps", "openf1_position", "openf1_weather", "openf1_race_control", "openf1_session_result", "openf1_sessions"}
    if race_session:
        critical.add("openf1_starting_grid")
    bad_status = {"late", "missing", "missing_critical", "conflicting", "needs_manual_review", "blocked"}
    for key, value in counts.items():
        if key in optional:
            continue
        if key in critical:
            try:
                if int(value or 0) <= 0:
                    return True
            except Exception:
                return True
    for key, value in statuses.items():
        if key in optional:
            continue
        if key in critical and normalize_status(value) in bad_status:
            return True
    return False


def normalize_effective_source_state(manifest: Dict[str, Any], dashboard: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normalize final source state when evidence proves usable readiness.

    v20 could carry a stale `overall_status=needs_manual_review` into the final
    output even while `readiness_quality=usable_with_optional_context_gaps` and
    dashboard/source-backed evidence showed the run was usable.  v20 normalizes
    that final outward state to clean unless a critical source gap is still present.
    """
    out = dict(manifest or {})
    dash = dashboard or {}
    quality = normalize_status(out.get("readiness_quality") or dash.get("readiness_quality"))
    # source_backed means evidence exists, including evidence requiring review.
    # It is not an assertion that the evidence is clean.
    dashboard_clean = normalize_status(dash.get("source_status")) == "clean"
    source_backed_hint = bool(out.get("source_backed", False)) or dashboard_clean
    out["_v20_source_backed_evidence"] = bool(source_backed_hint)
    usable_quality = quality == "usable_with_optional_context_gaps"
    critical_gap = has_critical_source_gap(out)
    if (usable_quality or dashboard_clean) and not critical_gap:
        out["overall_status"] = "clean"
        out["source_status"] = "clean"
        out["source_needs_manual_review"] = False
        out["readiness_quality"] = "usable_with_optional_context_gaps" if usable_quality or dashboard_clean else quality or "usable"
        out["source_backed"] = True
        out["normalization_applied"] = "v20_source_status_normalized_from_usable_readiness"
    else:
        out["critical_source_gap_detected"] = critical_gap
    return out


def normalize_effective_workbook_state(workbook: Dict[str, Any], source_manifest: Dict[str, Any], dashboard: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normalize workbook state when the processor/dashboard proves usable output.

    This does not overwrite canonical workbooks. It only corrects the machine-
    readable handoff status when a sandbox workbook/artifact is present or the
    dashboard confirms a clean source-backed workbook handoff.
    """
    out = dict(workbook or {})
    dash = dashboard or {}
    source_clean = normalize_status(source_manifest.get("source_status") or source_manifest.get("overall_status")) == "clean"
    usable_quality = normalize_status(source_manifest.get("readiness_quality")) == "usable_with_optional_context_gaps"
    dashboard_artifact = dash.get("workbook_artifact") or dash.get("sandbox_workbook")
    workbook_artifact = out.get("sandbox_workbook") or out.get("workbook_artifact") or dashboard_artifact
    dashboard_clean = normalize_status(dash.get("source_status")) == "clean"
    if source_clean and (bool(source_manifest.get("_v20_source_backed_evidence", False)) or dashboard_clean) and (usable_quality or dashboard_clean) and workbook_artifact:
        out["status"] = "refresh_applied"
        out["source_status"] = "clean"
        out["workbook_source_status"] = "clean"
        out["sandbox_workbook"] = workbook_artifact
        out["canonical_workbook_overwrite"] = False
        out["promotion_allowed"] = False
        out["normalization_applied"] = "v20_workbook_status_normalized_from_usable_readiness"
    return out


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
    path = root / "latest/readiness_dashboards/combined_readiness_dashboard.json"
    return path if path.exists() else None, load_json(path) or {}, []


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
    if dash_status == "clean" and not has_critical_source_gap(out):
        out.setdefault("schema_version", "dashboard_backed_source_state_v20")
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
    state, custody = current_custody(root, utc_now())
    path = root / state["session_manifest"] if state.get("session_manifest") else None
    source = load_json(path) or {}
    if not custody["context_eligible"]:
        source.update(overall_status="blocked", source_needs_manual_review=True,
                      source_identity_error={"reasons": state["readiness_reasons"]})
    return path, source, {"selection_rule": "verified_current_authority_only", "custody": custody}


def find_latest_workbook_manifest(root: Path) -> Tuple[Optional[Path], Dict[str, Any], Dict[str, Any]]:
    state, custody = current_custody(root, utc_now())
    path = root / state["workbook_manifest"] if state.get("workbook_manifest") else None
    workbook = load_json(path) or {}
    if not custody["context_eligible"]:
        workbook.update(status="blocked", source_status="blocked", workbook_source_status="blocked")
    return path, workbook, {"selection_rule": "verified_current_authority_only", "custody": custody}


def classify_handoffs(source_manifest: Dict[str, Any], workbook_manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    source_ok = is_cleanish_source(source_manifest)
    workbook_ok = is_cleanish_workbook(workbook_manifest)
    source_state = first(source_manifest, ["overall_status", "source_status", "status"], "unknown")
    quality = source_manifest.get("readiness_quality", "unknown")
    workbook_state = first(workbook_manifest, ["workbook_source_status", "source_status", "status"], "unknown")
    session_info = source_manifest.get("session") if isinstance(source_manifest.get("session"), dict) else {}
    session_type = str(session_info.get("session_type") or source_manifest.get("session_type") or
                       session_info.get("session_name") or source_manifest.get("session_name") or "unknown")
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

    session = normalize_effective_source_state(session, dashboard)
    workbook = normalize_effective_workbook_state(workbook, session, dashboard)

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
    session_info = session.get("session") if isinstance(session.get("session"), dict) else {}
    session_name = first(session_info, ["session_name"], first(session, ["session_name"], "unknown_session"))
    session_key = first(session_info, ["session_key"], first(session, ["session_key"], None))

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
    snapshot["custody"] = source_selection["custody"]
    snapshot["event"]["meeting_key"] = snapshot["custody"]["meeting_key"]
    snapshot["original_capture_run_id"] = snapshot["custody"]["source_run_id"]
    snapshot["capture_origin"] = snapshot["custody"]["capture_origin"]
    snapshot["run_id"] = "context_" + sha256_json(snapshot["custody"])[:32]
    previous = load_json(root / "history/forecast_bundle_ledger" / safe_component(event_id) / snapshot["run_id"] / "bundle_snapshot.json") or {}
    if previous.get("custody") == snapshot["custody"]:
        snapshot["generated_at_utc"] = previous.get("generated_at_utc", snapshot["generated_at_utc"])
    snapshot["signature"] = sha256_json({"status": snapshot["status"], "event": snapshot["event"], "source": snapshot["source"], "workbook": snapshot["workbook"], "handoffs": snapshot["handoffs"]})
    return snapshot


def detect_material_change(root: Path, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    sig_path = root / "latest" / "material_change" / "last_signature.json"
    previous = load_json(sig_path) or {}
    previous_sig = previous.get("signature")
    current_sig = snapshot.get("signature")
    changed = previous_sig != current_sig
    report = {
        "schema_version": "f1_1b_material_change_v20",
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
    history = root / "history/forecast_bundle_ledger" / safe_component(snapshot["event"]["event_id"]) / safe_component(snapshot["run_id"]) / "material_change_report.json"
    previous_report = load_json(history)
    if previous_report and previous_report.get("current_signature") == current_sig:
        return previous_report
    return report


def write_outputs(root: Path, snapshot: Dict[str, Any], change_report: Dict[str, Any]) -> Dict[str, Any]:
    batch = OutputBatch(root)
    write_json, write_csv = batch.json, batch.csv
    event_id = safe_component(snapshot.get("event", {}).get("event_id") or "unknown_event")
    run_id = safe_component(snapshot.get("run_id"))
    latest_ledger = root / "latest" / "forecast_bundle_ledger"
    history_ledger = root / "history" / "forecast_bundle_ledger" / event_id / run_id
    handoff_root = root / "latest" / "readiness_handoff"
    output_root = root / "latest" / "1b_output_contract"

    write_json(root / "latest/material_change/material_change_report.json", change_report)
    write_json(root / "latest/material_change/last_signature.json", {"signature": snapshot["signature"], "updated_at_utc": change_report["generated_at_utc"], "event": snapshot["event"]})
    write_json(latest_ledger / "latest_bundle_snapshot.json", snapshot)
    write_json(history_ledger / "bundle_snapshot.json", snapshot)
    write_json(history_ledger / "material_change_report.json", change_report)
    write_json(output_root / "input_selection_report.json", snapshot.get("input_selection", {}))

    rows: List[Dict[str, Any]] = []
    for name, item in snapshot.get("handoffs", {}).items():
        rows.append({"consumer": name, **item})
        write_json(handoff_root / f"{name}_readiness.json", item)
    write_json(handoff_root / "combined_readiness_handoff.json", {
        "schema_version": "f1_1b_combined_readiness_handoff_v20",
        "custody": snapshot["custody"],
        "run_id": snapshot["run_id"],
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
            "schema_version": "f1_1b_last_good_state_v20",
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
        "schema_version": "f1_1b_output_contract_report_v20",
        "custody": snapshot["custody"],
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
    _, fresh_custody = current_custody(root, utc_now())
    if fresh_custody != snapshot.get("custody"):
        raise RuntimeError("HOLD_CURRENT_CONTEXT_CHANGED_BEFORE_PUBLICATION")
    batch.commit()
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
    try:
        report = run(root, mode=args.mode)
    except RuntimeError as exc:
        print(json.dumps({"status": "HOLD", "reason": str(exc), "promotion_allowed": False, "prediction_locked": False}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
