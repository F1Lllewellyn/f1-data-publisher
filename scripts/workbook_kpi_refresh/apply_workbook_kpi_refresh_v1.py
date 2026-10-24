#!/usr/bin/env python3
"""
F1 Workbook/KPI Refresh Applier v1.1 Strict Source Status Guard

Purpose:
- Convert Session Data Processor outputs into dated sandbox workbook/KPI refresh artifacts.
- Never overwrite the canonical workbook.
- Never alter Engine_2026-06-07_STABLE.
- Never promote a model layer.
- Never delete old files.

This script is repo-native and GitHub Actions safe. It writes only to:
- latest/workbook_kpi_refresh_applier/
- history/workbook_kpi_refresh_applier/<run_id>/

If a source workbook is provided, the script copies it first and appends sandbox sheets to the copy.
If not provided, it creates a lightweight sandbox workbook artifact containing readiness and audit tabs.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

try:
    import openpyxl
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
except Exception as exc:  # pragma: no cover
    print(f"ERROR: missing spreadsheet dependency: {exc}", file=sys.stderr)
    sys.exit(22)

PROTECTED_STABLE_ENGINE = "Engine_2026-06-07_STABLE"
DIAGNOSTIC_SOURCE_STATUSES = {
    "clean",
    "partial",
    "late",
    "conflicting",
    "needs_manual_review",
}
DOWNSTREAM_SOURCE_STATUSES = {"clean", "partial"}
DOWNSTREAM_READINESS_QUALITIES = {
    "usable_clean",
    "usable_with_optional_context_gaps",
    "usable_with_required_source_partial",
}
CURRENT_SESSION_MAX_AGE = dt.timedelta(days=7)
FUTURE_CLOCK_SKEW = dt.timedelta(minutes=5)
AUTHORITY_TIMESTAMP_SPAN = dt.timedelta(minutes=5)
EVENT_ID_RE = re.compile(r"^(?P<season>[0-9]{4})_(?P<meeting>[1-9][0-9]*)_.+$")
SESSION_IDENTITY_FIELDS = (
    "meeting_key",
    "session_key",
    "session_name",
    "session_type",
    "date_start",
    "date_end",
)
REQUIRED_SESSION_FILES = (
    "sandbox_workbook_update_plan.json",
    "workbook_kpi_readiness.json",
    "workbook_kpi_readiness.csv",
    "forecast_bundle_ledger_snapshot.json",
)


def utc_datetime() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def utc_now() -> str:
    return utc_datetime().strftime("%Y%m%dT%H%M%SZ")

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = []
        for row in rows:
            for k in row.keys():
                if k not in keys:
                    keys.append(k)
        fieldnames = keys or ["status"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if status in {"needs_review", "needs_manual"}:
        return "needs_manual_review"
    return status


def nonblank_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_utc(value: Any) -> Optional[dt.datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        return None
    return parsed.astimezone(dt.timezone.utc)


def positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value.strip()):
        return int(value.strip())
    return None


def nonnegative_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value.strip())
    return None


def add_reason(reasons: List[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def repo_relative(path: Optional[Path], repo: Path) -> Optional[str]:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def load_required_object(path: Path, label: str, reasons: List[str]) -> Dict[str, Any]:
    try:
        value = read_json(path)
    except (OSError, json.JSONDecodeError, UnicodeError):
        add_reason(reasons, f"missing_or_invalid_{label}")
        return {}
    if not isinstance(value, dict):
        add_reason(reasons, f"missing_or_invalid_{label}")
        return {}
    return value


def fixed_repo_file(repo: Path, relative: str, label: str, reasons: List[str]) -> Optional[Path]:
    path = repo / relative
    if repo_relative(path, repo) != relative or not path.is_file():
        add_reason(reasons, f"missing_or_unsafe_{label}")
        return None
    try:
        if path.stat().st_size == 0:
            add_reason(reasons, f"missing_or_unsafe_{label}")
            return None
    except OSError:
        add_reason(reasons, f"missing_or_unsafe_{label}")
        return None
    return path


def safe_processor_manifest(repo: Path, value: Any, reasons: List[str]) -> Optional[Path]:
    """Resolve only the exact repository-contained authoritative processor pointer."""
    if not isinstance(value, str) or not value:
        add_reason(reasons, "invalid_authoritative_session_manifest_pointer")
        return None
    if "\\" in value:
        add_reason(reasons, "invalid_authoritative_session_manifest_pointer")
        return None
    pure = PurePosixPath(value)
    raw_parts = value.split("/")
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in raw_parts):
        add_reason(reasons, "invalid_authoritative_session_manifest_pointer")
        return None
    parts = pure.parts
    if (
        len(parts) < 5
        or parts[:2] != ("latest", "session_data_processor")
        or parts[-1] != "source_readiness_manifest.json"
    ):
        add_reason(reasons, "invalid_authoritative_session_manifest_pointer")
        return None
    candidate = repo.joinpath(*parts)
    if repo_relative(candidate, repo) != value or not candidate.is_file():
        add_reason(reasons, "invalid_authoritative_session_manifest_pointer")
        return None
    try:
        if candidate.stat().st_size == 0:
            add_reason(reasons, "invalid_authoritative_session_manifest_pointer")
            return None
    except OSError:
        add_reason(reasons, "invalid_authoritative_session_manifest_pointer")
        return None
    return candidate


def session_file(repo: Path, session_root: Path, name: str, reasons: List[str]) -> Optional[Path]:
    path = session_root / name
    if repo_relative(path, repo) != f"{repo_relative(session_root, repo)}/{name}" or not path.is_file():
        add_reason(reasons, f"missing_or_unsafe_{name}")
        return None
    try:
        if path.stat().st_size == 0:
            add_reason(reasons, f"missing_or_unsafe_{name}")
            return None
    except OSError:
        add_reason(reasons, f"missing_or_unsafe_{name}")
        return None
    return path


def canonical_session(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def authority_fingerprints(paths: Dict[str, Optional[Path]], repo: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for path in paths.values():
        relative = repo_relative(path, repo)
        if path is not None and relative is not None and path.is_file():
            result[relative] = sha256_file(path)
    return dict(sorted(result.items()))


def build_authority_state(repo: Path, reference_time: Optional[dt.datetime] = None) -> Dict[str, Any]:
    """Validate the sole active-session authority chain without filesystem discovery.

    ``latest/latest_manifest.json`` selects one exact processor manifest.  No
    directory scan, filename ordering, mtime, or historical fallback participates.
    """
    reference_time = reference_time or utc_datetime()
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=dt.timezone.utc)
    reference_time = reference_time.astimezone(dt.timezone.utc)
    reasons: List[str] = []
    eligibility_reasons: List[str] = []

    paths: Dict[str, Optional[Path]] = {
        "selector": fixed_repo_file(repo, "latest/latest_manifest.json", "selector", reasons),
        "data_readiness": fixed_repo_file(repo, "latest/data_readiness.json", "data_readiness", reasons),
        "combined_source": fixed_repo_file(repo, "latest/combined_source_manifest.json", "combined_source", reasons),
    }
    selector = load_required_object(paths["selector"], "selector", reasons) if paths["selector"] else {}
    data_readiness = load_required_object(paths["data_readiness"], "data_readiness", reasons) if paths["data_readiness"] else {}
    combined = load_required_object(paths["combined_source"], "combined_source", reasons) if paths["combined_source"] else {}

    pointer = selector.get("latest_session_data_processor_manifest")
    processor_manifest = safe_processor_manifest(repo, pointer, reasons)
    paths["source_readiness"] = processor_manifest
    session_root = processor_manifest.parent if processor_manifest else None
    if session_root:
        for name in REQUIRED_SESSION_FILES:
            paths[name] = session_file(repo, session_root, name, reasons)
    else:
        for name in REQUIRED_SESSION_FILES:
            paths[name] = None

    source_readiness = load_required_object(processor_manifest, "source_readiness_manifest", reasons) if processor_manifest else {}
    plan = load_required_object(paths["sandbox_workbook_update_plan.json"], "workbook_update_plan", reasons) if paths["sandbox_workbook_update_plan.json"] else {}
    workbook_readiness = load_required_object(paths["workbook_kpi_readiness.json"], "workbook_kpi_readiness", reasons) if paths["workbook_kpi_readiness.json"] else {}
    ledger = load_required_object(paths["forecast_bundle_ledger_snapshot.json"], "forecast_bundle_ledger", reasons) if paths["forecast_bundle_ledger_snapshot.json"] else {}
    readiness_rows: List[Dict[str, Any]] = []
    csv_path = paths["workbook_kpi_readiness.csv"]
    if csv_path:
        try:
            readiness_rows = read_csv_rows(csv_path)
        except (OSError, csv.Error, UnicodeError):
            add_reason(reasons, "missing_or_invalid_workbook_kpi_readiness_csv")
    if not readiness_rows:
        add_reason(reasons, "missing_or_invalid_workbook_kpi_readiness_csv")

    event_id = selector.get("event_id") if isinstance(selector.get("event_id"), str) else None
    event_match = EVENT_ID_RE.fullmatch(event_id or "")
    meeting_key = int(event_match.group("meeting")) if event_match else None
    session_key = positive_int(selector.get("session_key"))
    if meeting_key is None:
        add_reason(reasons, "invalid_authoritative_event_id")
    if session_key is None:
        add_reason(reasons, "invalid_authoritative_session_key")
    if processor_manifest and event_id:
        pointer_parts = PurePosixPath(str(pointer)).parts
        if len(pointer_parts) < 3 or pointer_parts[2] != event_id:
            add_reason(reasons, "authoritative_pointer_event_mismatch")

    readiness_session = canonical_session(data_readiness.get("session"))
    source_session = canonical_session(source_readiness.get("session"))
    workbook_session = canonical_session(workbook_readiness.get("session"))
    ledger_session = canonical_session(ledger.get("session"))
    for field in ("session_name", "session_type"):
        if not nonblank_string(readiness_session.get(field)):
            add_reason(reasons, f"invalid_authoritative_{field}")
    identity_objects = (
        ("data_readiness", data_readiness.get("event_id"), readiness_session),
        ("source_readiness", source_readiness.get("event_id"), source_session),
        ("workbook_kpi_readiness", workbook_readiness.get("event_id"), workbook_session),
        ("forecast_bundle_ledger", ledger.get("event_id"), ledger_session),
    )
    for label, candidate_event, candidate_session in identity_objects:
        if candidate_event != event_id:
            add_reason(reasons, f"{label}_event_mismatch")
        if positive_int(candidate_session.get("session_key")) != session_key:
            add_reason(reasons, f"{label}_session_mismatch")
        if positive_int(candidate_session.get("meeting_key")) != meeting_key:
            add_reason(reasons, f"{label}_meeting_mismatch")
        for field in SESSION_IDENTITY_FIELDS[2:]:
            if candidate_session.get(field) != readiness_session.get(field):
                add_reason(reasons, f"{label}_session_identity_mismatch")

    if not nonblank_string(selector.get("session_name")):
        add_reason(reasons, "invalid_selector_session_name")
    elif selector.get("session_name") != readiness_session.get("session_name"):
        add_reason(reasons, "selector_session_name_mismatch")
    if combined.get("event_id") != event_id:
        add_reason(reasons, "combined_source_event_mismatch")
    if positive_int(combined.get("session_key")) != session_key:
        add_reason(reasons, "combined_source_session_mismatch")
    source_layers = combined.get("source_layers") if isinstance(combined.get("source_layers"), dict) else {}
    if source_layers.get("session_data_processor") != pointer:
        add_reason(reasons, "combined_source_pointer_mismatch")

    statuses = {
        label: normalize_status(value)
        for label, value in (
            ("selector", selector.get("overall_status")),
            ("data_readiness", data_readiness.get("overall_status")),
            ("combined_source", combined.get("overall_status")),
            ("source_readiness", source_readiness.get("overall_status")),
            ("workbook_kpi_readiness", workbook_readiness.get("overall_status")),
            ("forecast_bundle_ledger", ledger.get("overall_status")),
        )
    }
    if len(set(statuses.values())) != 1:
        add_reason(reasons, "source_status_mismatch")
    source_status = next(iter(statuses.values())) if len(set(statuses.values())) == 1 else "unverified"
    if source_status not in DIAGNOSTIC_SOURCE_STATUSES:
        add_reason(reasons, f"source_status_not_diagnostic_publishable:{source_status}")

    aggregation = source_readiness.get("readiness_aggregation")
    if not isinstance(aggregation, dict):
        aggregation = {}
        add_reason(reasons, "missing_readiness_aggregation")
    quality_values = {
        normalize_status(data_readiness.get("readiness_quality")),
        normalize_status(combined.get("readiness_quality")),
        normalize_status(source_readiness.get("readiness_quality")),
        normalize_status(aggregation.get("readiness_quality")),
    }
    if len(quality_values) != 1:
        add_reason(reasons, "readiness_quality_mismatch")
    readiness_quality = next(iter(quality_values)) if len(quality_values) == 1 else "unverified"
    if normalize_status(aggregation.get("overall_status")) != source_status:
        add_reason(reasons, "readiness_aggregation_status_mismatch")

    manual_review_flags = {
        "data_readiness.needs_manual_review": data_readiness.get("needs_manual_review"),
        "data_readiness.source_needs_manual_review": data_readiness.get("source_needs_manual_review"),
        "combined_source.source_needs_manual_review": combined.get("source_needs_manual_review"),
        "source_readiness.source_needs_manual_review": source_readiness.get("source_needs_manual_review"),
        "readiness_aggregation.needs_manual_review": aggregation.get("needs_manual_review"),
    }
    malformed_manual_flags = [
        label for label, value in manual_review_flags.items() if not isinstance(value, bool)
    ]
    manual_review_required = any(value is True for value in manual_review_flags.values())
    if malformed_manual_flags:
        for label in malformed_manual_flags:
            add_reason(reasons, f"missing_or_invalid_manual_review_flag:{label}")
        add_reason(eligibility_reasons, "manual_review_authority_unverified")
    elif len(set(manual_review_flags.values())) != 1:
        add_reason(reasons, "manual_review_flag_mismatch")
        add_reason(eligibility_reasons, "manual_review_authority_conflicting")
    elif manual_review_required:
        add_reason(eligibility_reasons, "readiness_requires_manual_review")

    if source_status in DOWNSTREAM_SOURCE_STATUSES and manual_review_required:
        add_reason(reasons, "downstream_source_status_conflicts_with_manual_review")
    if source_status == "needs_manual_review" and not manual_review_required:
        add_reason(reasons, "manual_review_status_without_authority_flag")

    embedded_ledger = source_readiness.get("forecast_bundle_ledger_snapshot")
    if not isinstance(embedded_ledger, dict) or embedded_ledger != ledger:
        add_reason(reasons, "embedded_forecast_ledger_mismatch")
    workbook_update = source_readiness.get("workbook_kpi_update")
    expected_workbook_readiness = (
        f"{repo_relative(session_root, repo)}/workbook_kpi_readiness.json"
        if session_root and repo_relative(session_root, repo)
        else None
    )
    if (
        not isinstance(workbook_update, dict)
        or workbook_update.get("path") != expected_workbook_readiness
    ):
        add_reason(reasons, "source_workbook_readiness_pointer_mismatch")

    for field in ("blocking_issues", "critical_late", "missing_required_endpoints", "critical_endpoints"):
        if not isinstance(aggregation.get(field), list):
            add_reason(reasons, f"malformed_readiness_{field}")
    if aggregation.get("blocking_issues"):
        add_reason(eligibility_reasons, "readiness_blocking_issues")
    if aggregation.get("critical_late"):
        add_reason(eligibility_reasons, "readiness_critical_late")
    if aggregation.get("missing_required_endpoints"):
        add_reason(eligibility_reasons, "readiness_missing_required_endpoints")
    per_source = aggregation.get("per_source") if isinstance(aggregation.get("per_source"), dict) else {}
    critical = aggregation.get("critical_endpoints") if isinstance(aggregation.get("critical_endpoints"), list) else []
    observed_required = {
        report.get("endpoint")
        for report in per_source.values()
        if isinstance(report, dict)
        and report.get("role") == "required"
        and report.get("blocking") is False
        and positive_int(report.get("rows")) is not None
        and normalize_status(report.get("effective_status")) in DOWNSTREAM_SOURCE_STATUSES
    }
    if not critical or set(critical) != observed_required:
        add_reason(eligibility_reasons, "required_source_evidence_unverified")
    readiness_sources = data_readiness.get("sources") if isinstance(data_readiness.get("sources"), dict) else {}
    for name, report in per_source.items():
        if not isinstance(report, dict) or report.get("role") != "required":
            continue
        summary = readiness_sources.get(name)
        if (
            not isinstance(summary, dict)
            or positive_int(summary.get("rows")) != positive_int(report.get("rows"))
            or normalize_status(summary.get("status")) != normalize_status(report.get("raw_status"))
        ):
            add_reason(reasons, "required_source_summary_mismatch")

    workbook_sources = workbook_readiness.get("sources") if isinstance(workbook_readiness.get("sources"), dict) else {}
    source_manifest_sources = source_readiness.get("sources") if isinstance(source_readiness.get("sources"), dict) else {}
    if set(workbook_sources) != set(source_manifest_sources) or set(workbook_sources) != set(readiness_sources):
        add_reason(reasons, "source_summary_set_mismatch")
    for name, summary in workbook_sources.items():
        processor_summary = source_manifest_sources.get(name)
        readiness_summary = readiness_sources.get(name)
        expected_rows = nonnegative_int(summary.get("rows")) if isinstance(summary, dict) else None
        if (
            expected_rows is None
            or not isinstance(processor_summary, dict)
            or not isinstance(readiness_summary, dict)
            or nonnegative_int(processor_summary.get("rows")) != expected_rows
            or nonnegative_int(readiness_summary.get("rows")) != expected_rows
            or normalize_status(processor_summary.get("status")) != normalize_status(summary.get("status"))
            or normalize_status(readiness_summary.get("status")) != normalize_status(summary.get("status"))
        ):
            add_reason(reasons, "source_summary_content_mismatch")
    csv_sources: Dict[str, Dict[str, Any]] = {}
    for row in readiness_rows:
        name = row.get("endpoint") or row.get("source")
        if not isinstance(name, str) or not name or name in csv_sources:
            add_reason(reasons, "workbook_kpi_csv_source_identity_invalid")
            continue
        csv_sources[name] = row
    if set(csv_sources) != set(workbook_sources):
        add_reason(reasons, "workbook_kpi_csv_source_set_mismatch")
    for name, summary in workbook_sources.items():
        row = csv_sources.get(name)
        summary_rows = nonnegative_int(summary.get("rows")) if isinstance(summary, dict) else None
        row_rows = nonnegative_int(row.get("rows")) if isinstance(row, dict) else None
        if (
            not isinstance(summary, dict)
            or not isinstance(row, dict)
            or summary_rows is None
            or row_rows is None
            or summary_rows != row_rows
            or normalize_status(summary.get("status")) != normalize_status(row.get("status"))
        ):
            add_reason(reasons, "workbook_kpi_csv_source_summary_mismatch")

    session_start = parse_utc(readiness_session.get("date_start"))
    session_end = parse_utc(readiness_session.get("date_end"))
    if session_start is None or session_end is None or session_end < session_start:
        add_reason(reasons, "invalid_session_chronology")
    else:
        if session_end > reference_time + FUTURE_CLOCK_SKEW:
            add_reason(reasons, "session_not_completed")
        if reference_time - session_end > CURRENT_SESSION_MAX_AGE:
            add_reason(reasons, "stale_authoritative_session")

    timestamp_specs = (
        ("selector", selector.get("updated_utc")),
        ("data_readiness", data_readiness.get("updated_utc")),
        ("combined_source", combined.get("updated_utc")),
        ("source_readiness", source_readiness.get("created_utc")),
        ("workbook_kpi_readiness", workbook_readiness.get("created_utc")),
        ("forecast_bundle_ledger", ledger.get("created_utc")),
        ("workbook_update_plan", plan.get("created_utc")),
    )
    timestamps: List[dt.datetime] = []
    for label, value in timestamp_specs:
        parsed = parse_utc(value)
        if parsed is None:
            add_reason(reasons, f"invalid_{label}_timestamp")
            continue
        timestamps.append(parsed)
        if parsed > reference_time + FUTURE_CLOCK_SKEW:
            add_reason(reasons, f"future_{label}_timestamp")
        if session_end and parsed < session_end:
            add_reason(reasons, f"{label}_predates_session_completion")
    if timestamps and max(timestamps) - min(timestamps) > AUTHORITY_TIMESTAMP_SPAN:
        add_reason(reasons, "authority_timestamp_span_exceeded")

    if source_status not in DOWNSTREAM_SOURCE_STATUSES:
        add_reason(eligibility_reasons, f"required_source_status_{source_status}")
    if readiness_quality not in DOWNSTREAM_READINESS_QUALITIES:
        add_reason(eligibility_reasons, f"readiness_quality_{readiness_quality}")

    fingerprints = authority_fingerprints(paths, repo)
    diagnostic_publish_allowed = not reasons and source_status in DIAGNOSTIC_SOURCE_STATUSES
    downstream_eligible = diagnostic_publish_allowed and not eligibility_reasons
    return {
        "valid": diagnostic_publish_allowed,
        "reasons": reasons,
        "eligibility_reasons": eligibility_reasons,
        "event_id": event_id,
        "meeting_key": meeting_key,
        "session_key": session_key,
        "session": readiness_session,
        "source_status": source_status,
        "readiness_quality": readiness_quality,
        "manual_review_flags": manual_review_flags,
        "manual_review_required": manual_review_required,
        "diagnostic_publish_allowed": diagnostic_publish_allowed,
        "downstream_eligible": downstream_eligible,
        "session_root": session_root,
        "source_manifest_pointer": pointer if isinstance(pointer, str) else None,
        "paths": paths,
        "objects": {
            "selector": selector,
            "data_readiness": data_readiness,
            "combined_source": combined,
            "source_readiness": source_readiness,
            "workbook_update_plan": plan,
            "workbook_kpi_readiness": workbook_readiness,
            "forecast_bundle_ledger": ledger,
        },
        "readiness_rows": readiness_rows,
        "authority_fingerprints": fingerprints,
        "reference_time": reference_time,
    }


def revalidate_authority(repo: Path, original: Dict[str, Any]) -> Tuple[bool, List[str]]:
    current = build_authority_state(repo, utc_datetime())
    reasons: List[str] = []
    if not current.get("valid"):
        reasons.extend(f"revalidation:{reason}" for reason in current.get("reasons", []))
    for field in ("event_id", "meeting_key", "session_key", "source_manifest_pointer", "source_status", "readiness_quality"):
        if current.get(field) != original.get(field):
            add_reason(reasons, f"authority_changed_during_build:{field}")
    if current.get("authority_fingerprints") != original.get("authority_fingerprints"):
        add_reason(reasons, "authority_changed_during_build:fingerprint")
    return not reasons, reasons


def serializable_authority(state: Dict[str, Any], repo: Path) -> Dict[str, Any]:
    session_root = state.get("session_root")
    return {
        "event_id": state.get("event_id"),
        "meeting_key": state.get("meeting_key"),
        "session_key": state.get("session_key"),
        "session_name": canonical_session(state.get("session")).get("session_name"),
        "session_type": canonical_session(state.get("session")).get("session_type"),
        "source_status": state.get("source_status"),
        "readiness_quality": state.get("readiness_quality"),
        "manual_review_flags": state.get("manual_review_flags", {}),
        "manual_review_required": bool(state.get("manual_review_required")),
        "source_manifest_pointer": state.get("source_manifest_pointer"),
        "selected_session_processor_root": repo_relative(session_root, repo),
        "authority_fingerprints": state.get("authority_fingerprints", {}),
        "hold_reasons": state.get("reasons", []),
        "eligibility_reasons": state.get("eligibility_reasons", []),
        "diagnostic_publish_allowed": bool(state.get("diagnostic_publish_allowed")),
        "downstream_eligible": bool(state.get("downstream_eligible")),
    }


def locate_session_processor_root(repo: Path) -> Path:
    """Return the selector-authorized processor root; never scan or fall back."""
    reasons: List[str] = []
    selector_path = fixed_repo_file(repo, "latest/latest_manifest.json", "selector", reasons)
    selector = load_required_object(selector_path, "selector", reasons) if selector_path else {}
    manifest = safe_processor_manifest(repo, selector.get("latest_session_data_processor_manifest"), reasons)
    if manifest is None:
        raise RuntimeError("authoritative session processor root unavailable: " + ",".join(reasons))
    return manifest.parent


def has_required_session_sources(session_root: Path) -> Tuple[bool, List[str]]:
    """Compatibility entry point with deterministic exact-root validation."""
    missing: List[str] = []
    for name in REQUIRED_SESSION_FILES:
        path = session_root / name
        try:
            if not path.is_file() or path.stat().st_size == 0:
                missing.append(name)
        except OSError:
            missing.append(name)
    csv_path = session_root / "workbook_kpi_readiness.csv"
    if csv_path.is_file():
        try:
            if not read_csv_rows(csv_path):
                missing.append("workbook_kpi_readiness.csv:no_data_rows")
        except (OSError, csv.Error, UnicodeError) as exc:
            missing.append(f"workbook_kpi_readiness.csv:unreadable:{exc}")
    return not missing, missing

def is_commit_eligible_source_status(status: str) -> bool:
    """True only when the upstream session processor proved real source-backed state.

    `missing` is not acceptable even if placeholder rows exist. The previous
    SourceDiscoveryGuard fix correctly found nested folders, but still allowed a
    source_status=`missing` refresh to commit because material_change was inferred
    from CSV rows. Peak-elite behavior requires both concrete source artifacts
    AND a non-missing upstream classification.
    """
    allowed = {
        "clean",
        "partial",
        "late",
        "conflicting",
        "needs_manual_review",
        "needs-review",
        "needs_manual",
    }
    blocked = {
        "",
        "missing",
        "unknown",
        "no_action",
        "not_found",
        "empty",
        "placeholder",
        "scheduled_not_populated",
    }
    s = normalize_status(status)
    if s in blocked:
        return False
    return s in allowed

def summarize_sources(readiness: Dict[str, Any], plan: Dict[str, Any], rows: List[Dict[str, Any]]) -> Tuple[str, bool, List[str]]:
    # Accept all source-status aliases produced by the Session Data Processor.
    # The processor writes `overall_status`; earlier Workbook/KPI applier versions
    # looked only for classification/overall_classification/status and therefore
    # misclassified valid FP2-style processor output as `missing`.
    classification = (
        plan.get("classification")
        or plan.get("overall_status")
        or plan.get("overall_classification")
        or plan.get("source_status")
        or plan.get("status")
        or readiness.get("classification")
        or readiness.get("overall_status")
        or readiness.get("overall_classification")
        or readiness.get("source_status")
        or readiness.get("status")
        or "missing"
    )
    classification = normalize_status(classification)
    source_artifacts = []
    for key in ["sandbox_workbook_update_plan.json", "workbook_kpi_readiness.json", "workbook_kpi_readiness.csv", "forecast_bundle_ledger_snapshot.json"]:
        source_artifacts.append(key)
    material_change = is_commit_eligible_source_status(classification)
    if rows and material_change:
        material_change = True
    warnings = []
    if classification in ["needs_manual_review", "partial", "late", "conflicting"]:
        warnings.append(f"source_classification={classification}")
    if not rows:
        warnings.append("workbook_kpi_readiness_csv_missing_or_empty")
    if not is_commit_eligible_source_status(classification):
        warnings.append(f"source_status_not_commit_eligible={classification}")
    return classification, material_change, warnings

def add_or_replace_sheet(wb, name: str):
    if name in wb.sheetnames:
        ws = wb[name]
        wb.remove(ws)
    return wb.create_sheet(name)

def style_header(ws, max_col: int):
    fill = PatternFill("solid", fgColor="1F4E78")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1][:max_col]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"

def write_table(ws, rows: List[Dict[str, Any]], preferred_fields: List[str] | None = None):
    if preferred_fields:
        fields = preferred_fields[:]
        for row in rows:
            for k in row.keys():
                if k not in fields:
                    fields.append(k)
    else:
        fields = []
        for row in rows:
            for k in row.keys():
                if k not in fields:
                    fields.append(k)
    if not fields:
        fields = ["status"]
        rows = [{"status": "no rows"}]
    ws.append(fields)
    for row in rows:
        ws.append([row.get(k, "") for k in fields])
    style_header(ws, len(fields))
    thin = Side(style="thin", color="D9E2F3")
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=len(fields)):
        for cell in row:
            cell.border = Border(bottom=thin)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for col_idx in range(1, len(fields)+1):
        width = min(max(12, max(len(str(ws.cell(row=r, column=col_idx).value or "")) for r in range(1, min(ws.max_row, 40)+1)) + 2), 42)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

def create_or_update_sandbox_workbook(source_workbook: Path | None, output_workbook: Path, readiness_rows: List[Dict[str, Any]], plan: Dict[str, Any], ledger: Dict[str, Any], manifest: Dict[str, Any]) -> None:
    output_workbook.parent.mkdir(parents=True, exist_ok=True)

    if source_workbook and source_workbook.exists():
        shutil.copy2(source_workbook, output_workbook)
        wb = load_workbook(output_workbook)
    else:
        wb = Workbook()
        default = wb.active
        default.title = "Sandbox Refresh Summary"

    # Remove default empty sheet if it is still blank and not our summary sheet.
    if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
        ws = wb["Sheet"]
        if ws.max_row == 1 and ws.max_column == 1 and ws["A1"].value is None:
            wb.remove(ws)

    summary = add_or_replace_sheet(wb, "Sandbox Refresh Summary")
    summary_rows = [
        {"Field": "Run ID", "Value": manifest.get("run_id")},
        {"Field": "Created UTC", "Value": manifest.get("created_utc")},
        {"Field": "Source Status", "Value": manifest.get("source_status")},
        {"Field": "Readiness Quality", "Value": manifest.get("readiness_quality")},
        {"Field": "Material Change", "Value": str(manifest.get("material_change"))},
        {"Field": "Diagnostic Publish Allowed", "Value": str(manifest.get("diagnostic_publish_allowed"))},
        {"Field": "Downstream Eligible", "Value": str(manifest.get("downstream_eligible"))},
        {"Field": "Stable Engine Modified", "Value": "FALSE"},
        {"Field": "Canonical Workbook Overwrite", "Value": "FALSE"},
        {"Field": "Promotion Allowed", "Value": "FALSE"},
        {"Field": "Output Classification", "Value": "sandbox_only"},
    ]
    write_table(summary, summary_rows, ["Field", "Value"])

    ws = add_or_replace_sheet(wb, "KPI Readiness")
    write_table(ws, readiness_rows, ["source", "status", "rows", "classification", "session_key", "session_name", "updated_utc"])

    plan_ws = add_or_replace_sheet(wb, "Update Plan")
    plan_rows = []
    def flatten(prefix, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                flatten(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(obj, list):
            plan_rows.append({"Path": prefix, "Value": f"list[{len(obj)}]"})
        else:
            plan_rows.append({"Path": prefix, "Value": obj})
    flatten("", plan)
    write_table(plan_ws, plan_rows, ["Path", "Value"])

    ledger_ws = add_or_replace_sheet(wb, "Forecast Bundle Ledger")
    ledger_rows = []
    if isinstance(ledger, dict):
        for k, v in ledger.items():
            if isinstance(v, (dict, list)):
                ledger_rows.append({"Field": k, "Value": json.dumps(v)[:1000]})
            else:
                ledger_rows.append({"Field": k, "Value": v})
    write_table(ledger_ws, ledger_rows, ["Field", "Value"])

    gov_ws = add_or_replace_sheet(wb, "Governor Gates")
    gov_rows = [
        {"Gate": "Promotion Gate", "Status": "BLOCKED", "Rule": "No promotion from sandbox refresh"},
        {"Gate": "Stable Separation Gate", "Status": "ENFORCED", "Rule": "No stable P1-P20 overwrite"},
        {"Gate": "Canonical Workbook Gate", "Status": "ENFORCED", "Rule": "Create dated sandbox copy only"},
        {"Gate": "Deletion/Cleanup Gate", "Status": "BLOCKED", "Rule": "No delete authority"},
        {"Gate": "Accuracy Objective Lock", "Status": "ENFORCED", "Rule": "No accuracy claim without live/blind validation"},
    ]
    write_table(gov_ws, gov_rows, ["Gate", "Status", "Rule"])

    audit_ws = add_or_replace_sheet(wb, "Refresh Audit")
    audit_rows = [{"Field": k, "Value": json.dumps(v) if isinstance(v, (dict, list)) else v} for k, v in manifest.items()]
    write_table(audit_ws, audit_rows, ["Field", "Value"])

    wb.save(output_workbook)

def make_report(manifest: Dict[str, Any], warnings: List[str]) -> str:
    status = "Pass with warnings" if warnings else "Pass"
    warnings_md = "\n".join([f"- {w}" for w in warnings]) if warnings else "- None"
    outputs_md = "\n".join([f"- `{o['path']}` ({o.get('sha256','')[:12]}...)" for o in manifest.get("outputs", [])])
    return f"""# F1 Workbook/KPI Refresh Applier Report

## Verdict

{status}

## Run

- Run ID: `{manifest.get('run_id')}`
- Created UTC: `{manifest.get('created_utc')}`
- Source status: `{manifest.get('source_status')}`
- Readiness quality: `{manifest.get('readiness_quality')}`
- Material change: `{manifest.get('material_change')}`
- Diagnostic publish allowed: `{manifest.get('diagnostic_publish_allowed')}`
- Downstream eligible: `{manifest.get('downstream_eligible')}`

## Warnings

{warnings_md}

## Outputs

{outputs_md}

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
"""

def safe_output_target(path: Path, repo: Path, expected_prefix: str) -> bool:
    try:
        lexical_relative = path.relative_to(repo).as_posix()
    except ValueError:
        return False
    if not (
        lexical_relative == expected_prefix
        or lexical_relative.startswith(expected_prefix + "/")
    ):
        return False

    current = repo
    parts = Path(lexical_relative).parts
    for index, part in enumerate(parts):
        current = current / part
        if current.is_symlink():
            return False
        if index < len(parts) - 1 and current.exists() and not current.is_dir():
            return False

    resolved_relative = repo_relative(path, repo)
    return bool(
        resolved_relative
        and (
            resolved_relative == expected_prefix
            or resolved_relative.startswith(expected_prefix + "/")
        )
    )


def safe_existing_publication_file(path: Path, repo: Path, expected_prefix: str) -> bool:
    if not safe_output_target(path, repo, expected_prefix):
        return False
    if not path.exists():
        return True
    if not path.is_file():
        return False
    try:
        return path.stat().st_nlink == 1
    except OSError:
        return False


def safe_label(value: Any) -> str:
    label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return label[:160] or "unknown_event_session"


def write_hold_status(
    repo: Path,
    run_id: str,
    reason: str,
    authority: Dict[str, Any],
    extra_reasons: Optional[List[str]] = None,
) -> Dict[str, Any]:
    payload = {
        "status": "no_action",
        "reason": reason,
        "commit_allowed": False,
        "run_id": run_id,
        **serializable_authority(authority, repo),
        "hold_reasons": list(authority.get("reasons", [])) + list(extra_reasons or []),
        "canonical_workbook_overwrite": False,
        "stable_engine_modified": False,
        "promotion_allowed": False,
    }
    write_json(repo / "_runtime" / "workbook_kpi_refresh_status.json", payload)
    print(json.dumps(payload, indent=2))
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", help="Repository root")
    ap.add_argument("--source-workbook", default="", help="Optional source workbook path to copy before appending sandbox sheets")
    ap.add_argument("--event-label", default="auto", help="Optional event label for output naming")
    ap.add_argument("--safe-test", action="store_true", help="Run preflight only and write no forecast-affecting outputs")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    reference_time = utc_datetime()
    run_id = reference_time.strftime("%Y%m%dT%H%M%SZ")
    latest_out = repo / "latest" / "workbook_kpi_refresh_applier"
    history_out = repo / "history" / "workbook_kpi_refresh_applier" / run_id
    authority = build_authority_state(repo, reference_time)

    if args.safe_test:
        session_root = authority.get("session_root")
        if isinstance(session_root, Path):
            required_sources_present, missing_sources = has_required_session_sources(session_root)
            discovered_root = repo_relative(session_root, repo) or str(session_root)
            session_root_exists = session_root.exists()
        else:
            required_sources_present = False
            missing_sources = list(REQUIRED_SESSION_FILES)
            discovered_root = None
            session_root_exists = False
        diag = {
            "status": "safe_test_pass" if authority["valid"] else "safe_test_hold",
            "reason": "authoritative_active_session_valid" if authority["valid"] else "authority_validation_failed",
            "commit_allowed": False,
            "run_id": run_id,
            "repo_root": str(repo),
            "discovered_session_processor_root": discovered_root,
            "session_processor_root_exists": session_root_exists,
            "required_session_sources_present": required_sources_present,
            "missing_session_sources": missing_sources,
            **serializable_authority(authority, repo),
            "canonical_workbook_overwrite": False,
            "stable_engine_modified": False,
            "promotion_allowed": False,
        }
        write_json(repo / "_runtime" / "workbook_kpi_refresh_applier_safe_test.json", diag)
        print(json.dumps(diag, indent=2))
        return 0

    if not authority["valid"]:
        write_hold_status(repo, run_id, "authority_validation_failed", authority)
        return 0

    session_root = authority["session_root"]
    assert isinstance(session_root, Path)
    objects = authority["objects"]
    plan = objects["workbook_update_plan"]
    ledger = objects["forecast_bundle_ledger"]
    readiness_rows = authority["readiness_rows"]
    source_status = authority["source_status"]
    material_change = bool(readiness_rows and authority["diagnostic_publish_allowed"])
    warnings = list(authority["eligibility_reasons"])
    if not authority["downstream_eligible"]:
        warnings.insert(0, f"diagnostic_only_source_status={source_status}")

    if args.event_label == "auto":
        event_label = safe_label(
            f"{objects['data_readiness'].get('race_name') or authority['event_id']}_"
            f"{canonical_session(authority['session']).get('session_name') or 'session'}"
        )
    else:
        event_label = safe_label(args.event_label)
    workbook_name = f"F1_Workbook_KPI_SANDBOX_Refresh_{event_label}_{run_id}.xlsx"
    source_wb = Path(args.source_workbook).resolve() if args.source_workbook else None

    manifest = {
        "run_id": run_id,
        "created_utc": reference_time.isoformat(),
        "event_id": authority["event_id"],
        "meeting_key": authority["meeting_key"],
        "session_key": authority["session_key"],
        "session_name": canonical_session(authority["session"]).get("session_name"),
        "session_type": canonical_session(authority["session"]).get("session_type"),
        "source_status": source_status,
        "readiness_quality": authority["readiness_quality"],
        "source_processor_root": repo_relative(session_root, repo),
        "source_manifest_pointer": authority["source_manifest_pointer"],
        "authority_fingerprints": authority["authority_fingerprints"],
        "material_change": material_change,
        "diagnostic_publish_allowed": True,
        "downstream_eligible": bool(authority["downstream_eligible"]),
        "warnings": warnings,
        "source_artifacts": [
            f"{repo_relative(session_root, repo)}/{name}" for name in REQUIRED_SESSION_FILES
        ],
        "governance": {
            "stable_engine": PROTECTED_STABLE_ENGINE,
            "stable_engine_modified": False,
            "canonical_workbook_overwrite": False,
            "promotion_allowed": False,
            "delete_authority": False,
        },
        "outputs": [],
        "commit_allowed": True,
    }

    refreshed_rows = readiness_rows
    artifacts = {
        "sandbox_workbook_update_plan_applied.json": {
            "applied": True,
            "source_plan": plan,
            "event_id": authority["event_id"],
            "meeting_key": authority["meeting_key"],
            "session_key": authority["session_key"],
            "source_status": source_status,
            "readiness_quality": authority["readiness_quality"],
            "material_change": material_change,
            "diagnostic_publish_allowed": True,
            "downstream_eligible": bool(authority["downstream_eligible"]),
            "governance": manifest["governance"],
        },
        "upstream_latest_manifest_snapshot.json": objects["selector"],
        "upstream_data_readiness_snapshot.json": objects["data_readiness"],
        "upstream_combined_source_manifest_snapshot.json": objects["combined_source"],
    }

    with tempfile.TemporaryDirectory(prefix="f1_workbook_kpi_refresh_") as temporary:
        stage = Path(temporary)
        for name, obj in artifacts.items():
            write_json(stage / name, obj)
        write_csv(stage / "refreshed_workbook_kpi_readiness.csv", refreshed_rows)
        workbook_path = stage / workbook_name
        create_or_update_sandbox_workbook(source_wb, workbook_path, refreshed_rows, plan, ledger, manifest)

        output_names = [
            "sandbox_workbook_update_plan_applied.json",
            "refreshed_workbook_kpi_readiness.csv",
            workbook_name,
            "upstream_latest_manifest_snapshot.json",
            "upstream_data_readiness_snapshot.json",
            "upstream_combined_source_manifest_snapshot.json",
        ]
        for name in output_names:
            staged = stage / name
            manifest["outputs"].append({
                "path": f"history/workbook_kpi_refresh_applier/{run_id}/{name}",
                "sha256": sha256_file(staged),
                "bytes": staged.stat().st_size,
            })
        write_json(stage / "workbook_kpi_refresh_manifest.json", manifest)
        (stage / "workbook_kpi_refresh_report.md").write_text(make_report(manifest, warnings), encoding="utf-8")

        revalidated, revalidation_reasons = revalidate_authority(repo, authority)
        if not revalidated:
            write_hold_status(
                repo,
                run_id,
                "authority_changed_during_in_process_build",
                authority,
                revalidation_reasons,
            )
            return 0

        publish_names = [path.name for path in stage.iterdir() if path.is_file()]
        if len(publish_names) != len(list(stage.iterdir())):
            write_hold_status(repo, run_id, "unexpected_staging_content", authority)
            return 0
        unsafe_publication_target = (
            not safe_output_target(latest_out, repo, "latest/workbook_kpi_refresh_applier")
            or (latest_out.exists() and not latest_out.is_dir())
            or not safe_output_target(history_out, repo, "history/workbook_kpi_refresh_applier")
            or history_out.exists()
            or history_out.is_symlink()
        )
        for name in publish_names:
            latest_destination = latest_out / name
            history_destination = history_out / name
            if (
                not safe_existing_publication_file(
                    latest_destination,
                    repo,
                    "latest/workbook_kpi_refresh_applier",
                )
                or not safe_existing_publication_file(
                    history_destination,
                    repo,
                    "history/workbook_kpi_refresh_applier",
                )
            ):
                unsafe_publication_target = True
        if unsafe_publication_target:
            write_hold_status(repo, run_id, "unsafe_or_existing_output_target", authority)
            return 0

        history_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, history_out)
        latest_out.mkdir(parents=True, exist_ok=True)
        for name in publish_names:
            shutil.copy2(stage / name, latest_out / name)

    status_payload = {
        "status": "refresh_applied",
        "commit_allowed": True,
        **serializable_authority(authority, repo),
        "material_change": material_change,
        "warnings": warnings,
        "latest_output_root": repo_relative(latest_out, repo),
        "history_output_root": repo_relative(history_out, repo),
        "sandbox_workbook": repo_relative(latest_out / workbook_name, repo),
        "canonical_workbook_overwrite": False,
        "stable_engine_modified": False,
        "promotion_allowed": False,
        "distributed_atomicity_limitation": (
            "This process revalidates checked-out authority bytes immediately before publication; "
            "it cannot prevent another commit from advancing remote main during a later push/rebase."
        ),
    }
    write_json(repo / "_runtime" / "workbook_kpi_refresh_status.json", status_payload)
    print(json.dumps(status_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
