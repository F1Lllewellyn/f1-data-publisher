#!/usr/bin/env python3
"""Publish source-backed Race/Fantasy readiness dashboard and chat briefs.

This connector is intentionally conservative: it reads existing latest/history artifacts,
creates dashboard state files, and never modifies stable predictions or the canonical workbook.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

SOURCE_USABLE_STATUSES = {"clean", "partial"}
SOURCE_USABLE_QUALITIES = {
    "usable_clean",
    "usable_with_optional_context_gaps",
    "usable_with_required_source_partial",
}
CURRENT_SESSION_MAX_AGE = timedelta(days=7)
FUTURE_CLOCK_SKEW = timedelta(minutes=5)
EVENT_ID_RE = re.compile(r"^(?P<season>[0-9]{4})_(?P<meeting>[1-9][0-9]*)_.+$")


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


def first_present(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def parse_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        return None
    return parsed.astimezone(timezone.utc)


def positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value.strip()):
        return int(value.strip())
    return None


def relpath(path: Optional[Path], root: Path) -> Optional[str]:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def load_object(path: Path) -> Dict[str, Any]:
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def safe_processor_manifest(root: Path, value: Any) -> Optional[Path]:
    if not isinstance(value, str):
        return None
    candidate = root / value
    relative = relpath(candidate, root)
    if (
        relative is None
        or not relative.startswith("latest/session_data_processor/")
        or not relative.endswith("/source_readiness_manifest.json")
    ):
        return None
    return candidate


def workbook_artifact(root: Path, manifest: Dict[str, Any]) -> Optional[Path]:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        return None
    matches: List[Path] = []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        value = item.get("path")
        if not isinstance(value, str) or not value.endswith(".xlsx") or "SANDBOX" not in Path(value).name:
            continue
        candidate = root / value
        if relpath(candidate, root) is not None and candidate.is_file():
            matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


def add_reason(reasons: List[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def discover_state(root: Path, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
    """Build dashboard state from the explicit current-session authority chain.

    Filesystem timestamps are deliberately irrelevant.  ``latest_manifest`` is
    the selector; every other object must bind to its event/session/meeting.
    """
    reference_time = reference_time or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    reference_time = reference_time.astimezone(timezone.utc)

    selector_path = root / "latest" / "latest_manifest.json"
    readiness_path = root / "latest" / "data_readiness.json"
    combined_path = root / "latest" / "combined_source_manifest.json"
    workbook_manifest_path = root / "latest" / "workbook_kpi_refresh_applier" / "workbook_kpi_refresh_manifest.json"

    selector = load_object(selector_path)
    readiness = load_object(readiness_path)
    combined = load_object(combined_path)
    workbook_state = load_object(workbook_manifest_path)
    reasons: List[str] = []

    for label, state in (("selector", selector), ("data_readiness", readiness), ("combined_source", combined)):
        if not state:
            add_reason(reasons, f"missing_or_invalid_{label}_manifest")

    event_id = selector.get("event_id") if isinstance(selector.get("event_id"), str) else None
    event_match = EVENT_ID_RE.fullmatch(event_id or "")
    event_meeting = int(event_match.group("meeting")) if event_match else None
    session_key = positive_int(selector.get("session_key"))
    if event_meeting is None:
        add_reason(reasons, "invalid_authoritative_event_id")
    if session_key is None:
        add_reason(reasons, "invalid_authoritative_session_key")

    session_manifest_path = safe_processor_manifest(root, selector.get("latest_session_data_processor_manifest"))
    if session_manifest_path is None:
        add_reason(reasons, "invalid_authoritative_session_manifest_pointer")
    session_state = load_object(session_manifest_path) if session_manifest_path else {}
    if session_manifest_path and not session_state:
        add_reason(reasons, "missing_or_invalid_session_manifest")
    ledger_path = session_manifest_path.with_name("forecast_bundle_ledger_snapshot.json") if session_manifest_path else None
    ledger = load_object(ledger_path) if ledger_path else {}
    if ledger_path and not ledger:
        add_reason(reasons, "missing_or_invalid_forecast_ledger")

    source_session = session_state.get("session")
    if not isinstance(source_session, dict):
        embedded_ledger = session_state.get("forecast_bundle_ledger_snapshot")
        source_session = embedded_ledger.get("session") if isinstance(embedded_ledger, dict) else None
    source_session = source_session if isinstance(source_session, dict) else {}
    readiness_session = readiness.get("session") if isinstance(readiness.get("session"), dict) else {}
    ledger_session = ledger.get("session") if isinstance(ledger.get("session"), dict) else {}

    identity_objects = (
        ("data_readiness", readiness.get("event_id"), readiness_session),
        ("session_manifest", session_state.get("event_id"), source_session),
        ("forecast_ledger", ledger.get("event_id"), ledger_session),
    )
    for label, candidate_event, candidate_session in identity_objects:
        if candidate_event != event_id:
            add_reason(reasons, f"{label}_event_mismatch")
        if positive_int(candidate_session.get("session_key")) != session_key:
            add_reason(reasons, f"{label}_session_mismatch")
        if positive_int(candidate_session.get("meeting_key")) != event_meeting:
            add_reason(reasons, f"{label}_meeting_mismatch")
        if label != "data_readiness":
            for field in ("date_start", "date_end", "session_name", "session_type"):
                if candidate_session.get(field) != readiness_session.get(field):
                    add_reason(reasons, f"{label}_session_identity_mismatch")

    if selector.get("session_name") != readiness_session.get("session_name"):
        add_reason(reasons, "selector_session_name_mismatch")

    if combined.get("event_id") != event_id:
        add_reason(reasons, "combined_source_event_mismatch")
    if positive_int(combined.get("session_key")) != session_key:
        add_reason(reasons, "combined_source_session_mismatch")
    source_layers = combined.get("source_layers") if isinstance(combined.get("source_layers"), dict) else {}
    if source_layers.get("session_data_processor") != relpath(session_manifest_path, root):
        add_reason(reasons, "combined_source_pointer_mismatch")

    session_start = parse_utc(readiness_session.get("date_start"))
    session_end = parse_utc(readiness_session.get("date_end"))
    selector_updated = parse_utc(selector.get("updated_utc"))
    if session_start is None or session_end is None or session_end < session_start:
        add_reason(reasons, "invalid_session_chronology")
    else:
        if session_end > reference_time + FUTURE_CLOCK_SKEW:
            add_reason(reasons, "session_not_completed")
        if reference_time - session_end > CURRENT_SESSION_MAX_AGE:
            add_reason(reasons, "stale_authoritative_session")
    if selector_updated is None:
        add_reason(reasons, "invalid_selector_timestamp")
    else:
        if selector_updated > reference_time + FUTURE_CLOCK_SKEW:
            add_reason(reasons, "future_selector_timestamp")
        if session_start and selector_updated < session_start:
            add_reason(reasons, "selector_predates_session")

    statuses = {
        norm_status(selector.get("overall_status")),
        norm_status(readiness.get("overall_status")),
        norm_status(combined.get("overall_status")),
        norm_status(session_state.get("overall_status")),
        norm_status(ledger.get("overall_status")),
    }
    if len(statuses) != 1:
        add_reason(reasons, "source_status_mismatch")
    source_status = next(iter(statuses)) if len(statuses) == 1 else "unverified"

    aggregation = session_state.get("readiness_aggregation")
    aggregation = aggregation if isinstance(aggregation, dict) else {}
    quality = norm_status(aggregation.get("readiness_quality"))
    if not aggregation:
        add_reason(reasons, "missing_readiness_aggregation")
    if norm_status(aggregation.get("overall_status")) != source_status:
        add_reason(reasons, "readiness_aggregation_status_mismatch")
    if norm_status(readiness.get("readiness_quality")) != quality or norm_status(combined.get("readiness_quality")) != quality:
        add_reason(reasons, "readiness_quality_mismatch")
    if source_status not in SOURCE_USABLE_STATUSES or quality not in SOURCE_USABLE_QUALITIES:
        add_reason(reasons, f"required_source_status_{source_status}")
    for field in ("blocking_issues", "critical_late", "missing_required_endpoints"):
        value = aggregation.get(field)
        if not isinstance(value, list) or value:
            add_reason(reasons, f"readiness_{field}")
    if aggregation.get("needs_manual_review") is not False:
        add_reason(reasons, "readiness_requires_manual_review")

    per_source = aggregation.get("per_source") if isinstance(aggregation.get("per_source"), dict) else {}
    critical = aggregation.get("critical_endpoints") if isinstance(aggregation.get("critical_endpoints"), list) else []
    observed_required = {
        report.get("endpoint")
        for report in per_source.values()
        if isinstance(report, dict)
        and report.get("role") == "required"
        and report.get("blocking") is False
        and positive_int(report.get("rows")) is not None
        and norm_status(report.get("effective_status")) in SOURCE_USABLE_STATUSES
    }
    if not critical or set(critical) != observed_required:
        add_reason(reasons, "required_source_evidence_unverified")
    readiness_sources = readiness.get("sources") if isinstance(readiness.get("sources"), dict) else {}
    for name, report in per_source.items():
        if not isinstance(report, dict) or report.get("role") != "required":
            continue
        summary = readiness_sources.get(name)
        if (
            not isinstance(summary, dict)
            or positive_int(summary.get("rows")) != positive_int(report.get("rows"))
            or norm_status(summary.get("status")) != norm_status(report.get("raw_status"))
        ):
            add_reason(reasons, "required_source_summary_mismatch")

    identity_or_time_failure = any(
        "mismatch" in reason
        or reason.startswith("missing_or_invalid_")
        or reason.startswith("invalid_authoritative_")
        or reason in {
            "invalid_session_chronology",
            "session_not_completed",
            "stale_authoritative_session",
            "invalid_selector_timestamp",
            "future_selector_timestamp",
            "selector_predates_session",
        }
        for reason in reasons
    )
    source_backed = not reasons

    expected_processor_root = session_manifest_path.parent.as_posix() if session_manifest_path else None
    actual_processor_root = (root / str(workbook_state.get("source_processor_root", ""))).as_posix() if workbook_state else None
    workbook_path = workbook_artifact(root, workbook_state) if workbook_state else None
    workbook_ready = True
    if not workbook_state:
        workbook_ready = False
        add_reason(reasons, "missing_or_invalid_workbook_manifest")
    elif actual_processor_root != expected_processor_root:
        workbook_ready = False
        add_reason(reasons, "workbook_event_session_mismatch")
    if workbook_path is None:
        workbook_ready = False
        add_reason(reasons, "missing_current_workbook_artifact")
    if norm_status(workbook_state.get("source_status")) != source_status:
        workbook_ready = False
        add_reason(reasons, "workbook_source_status_mismatch")

    downstream_eligible = bool(source_backed and workbook_ready)
    verified_identity = bool(not identity_or_time_failure and event_id and session_key and event_meeting)
    event_name = first_present(readiness, ["race_name", "event_name", "meeting_name"], None) if verified_identity else None
    session_name = first_present(readiness_session, ["session_name", "session_type"], None) if verified_identity else None

    dashboard = {
        "generated_at_utc": now_iso(),
        "status": "dashboard_refreshed",
        "source_status": source_status,
        "source_backed": bool(source_backed),
        "commit_allowed": True,
        "diagnostic_publish_allowed": True,
        "downstream_eligible": downstream_eligible,
        "readiness_reasons": reasons or ["verified_current_session_evidence"],
        "event_id": event_id if verified_identity else None,
        "meeting_key": event_meeting if verified_identity else None,
        "session_key": session_key if verified_identity else None,
        "event_name": event_name or "unknown event",
        "session_name": session_name or "unknown session",
        "workbook_artifact": relpath(workbook_path, root),
        "workbook_manifest": relpath(workbook_manifest_path, root) if workbook_state else None,
        "session_manifest": relpath(session_manifest_path, root) if session_state else None,
        "autorepair_report": None,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "race_predictions": {
            "ready_for_use": downstream_eligible,
            "blocked": not downstream_eligible,
            "latest_session_state": source_status,
            "allowed_effect": "confidence/risk/readiness context only; stable P1-P20 not overwritten",
        },
        "fantasy_predictions": {
            "ready_for_use": downstream_eligible,
            "blocked": not downstream_eligible,
            "latest_session_state": source_status,
            "allowed_effect": "readiness/value/risk context only; no automatic fantasy transfer execution",
        },
    }
    return dashboard


def brief(title: str, dashboard: Dict[str, Any], audience: str) -> str:
    ready = "READY" if dashboard.get("downstream_eligible") else "NOT READY"
    lines = [
        f"# {title}",
        "",
        f"Generated UTC: {dashboard['generated_at_utc']}",
        f"Event: {dashboard.get('event_name')}",
        f"Session: {dashboard.get('session_name')}",
        f"Source status: {dashboard.get('source_status')}",
        f"Dashboard readiness: {ready}",
        f"Diagnostic publishing allowed: {str(bool(dashboard.get('diagnostic_publish_allowed'))).lower()}",
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
