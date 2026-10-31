#!/usr/bin/env python3
"""Publish lightweight OpenF1 source-closure artifacts.

This script is deliberately lightweight. It does not pull high-frequency
car_data or location by default. It captures source lanes that support
pattern identification, forecast attribution, reliability/EOL context,
clean-air/traffic-energy modelling, and post-event audit.

Timestamp policy: use timezone-aware dt.datetime.now(dt.UTC).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import numbers
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

FORECAST_BUNDLES_DIR = Path(__file__).resolve().parents[1] / "forecast_bundles"
if str(FORECAST_BUNDLES_DIR) not in sys.path:
    sys.path.insert(0, str(FORECAST_BUNDLES_DIR))
import dr002_openf1_historical_rest_capture_v1 as historical_rest_contract
import dr002_openf1_drivers_producer_adapter_v1 as drivers_adapter_contract
import dr002_openf1_starting_grid_producer_adapter_v1 as starting_grid_adapter_contract

API_BASE = "https://api.openf1.org/v1"
ROOT = Path.cwd()
POLICY_PATH = ROOT / "configs" / "openf1" / "openf1_lightweight_source_closure_policy.json"

# Lightweight endpoints only. Do not add car_data/location here by default.
LANES = [
    "weather",
    "race_control",
    "intervals",
    "position",
    "stints",
    "pit",
    "starting_grid",
    "drivers",
    "team_radio",
]

RACE_LIKE_HINTS = ("race", "sprint")
TEAM_RADIO_IS_OPPORTUNISTIC = True
REQUEST_TIMEOUT = 30
SLEEP_SECONDS = 0.10
MATERIAL_REQUEST_STATUSES = {
    "exception",
    "invalid_http_status",
    "invalid_json",
    "invalid_response_schema",
    "invalid_sessions_schema",
}
ROW_REQUIRED_LANES = {"weather", "position", "drivers"}

# NORMAL-mode public historical collection is intentionally bounded below the
# workflow timeout.  OpenF1 documents a 30 request/minute public historical
# limit; this sliding-window budget includes discovery, primary requests and
# fallbacks.  It is not used by the explicit manual provenance-shadow path.
NORMAL_REQUESTS_PER_MINUTE = 30
NORMAL_RATE_WINDOW_SECONDS = 60.0
NORMAL_MAX_COLLECTION_SECONDS = 24 * 60.0
NORMAL_MAX_RUN_REQUESTS = 720
NORMAL_CACHE_SCHEMA_VERSION = "openf1-normal-session-evidence-v1"
NORMAL_LEGACY_HISTORY_REL = Path(
    "history/openf1_lightweight_source_closure/20261026_013754"
)
NORMAL_LEGACY_REQUEST_LOG_SHA256 = (
    "bb7608335b3bb3e430aff902d9238c429aba94c2f8bb25c25dfa540b84d98158"
)
NORMAL_LEGACY_REQUEST_LOG_GIT_BLOB = (
    "310fd9ba531e1985b0a1f6ff282072f1bc14d1f3"
)
NORMAL_LEGACY_SNAPSHOT_SHA256 = (
    "5b4ce0fae0660b8519b6481e70c46289edda822651b936e7efe3d56da0f894c7"
)
NORMAL_LEGACY_SNAPSHOT_FILES = (
    "latest_manifest.json",
    "data/target_sessions.csv",
    "zero_lane_diagnostics.csv",
    "request_log.csv",
    "combined_source_manifest.csv",
    *(f"data/openf1_{lane}.csv" for lane in LANES),
)
NORMAL_SESSION_IDENTITY_FIELDS = (
    "session_key",
    "meeting_key",
    "year",
    "country_name",
    "location",
    "circuit_short_name",
    "session_name",
    "session_type",
    "date_start",
    "date_end",
)

SHADOW_SCHEMA_VERSION = "dr002-pre2b7k4r2-openf1-source-closure-shadow-v1"
SHADOW_RUNTIME_DIR = "dr002_pre2b7k4r2_openf1_historical_rest_shadow"
SHADOW_WORKFLOW_NAME = "F1 OpenF1 Lightweight Source Closure"
SHADOW_WORKFLOW_PATH = ".github/workflows/f1-openf1-lightweight-source-closure.yml"
SHADOW_REPOSITORY = "F1Lllewellyn/f1-data-publisher"
SHADOW_ENDPOINT = "weather"
SHADOW_ENDPOINTS = ("weather", "drivers", "starting_grid")
SHADOW_IMPLEMENTATION = "scripts/openf1/publish_openf1_lightweight_source_closure.py"
SHADOW_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
STARTING_GRID_SHADOW_SCHEMA_VERSION = (
    "dr002-pre2b7k4r16-openf1-qualifying-grid-race-target-shadow-v1"
)


class ProvenanceShadowHold(RuntimeError):
    """Fail-closed K4R2 shadow result."""


class NormalCollectionDeferred(RuntimeError):
    """A bounded NORMAL-mode request was deliberately not sent."""


class NormalRequestBudget:
    """Deterministic sliding-window and whole-run request budget."""

    def __init__(
        self,
        *,
        requests_per_window: int = NORMAL_REQUESTS_PER_MINUTE,
        window_seconds: float = NORMAL_RATE_WINDOW_SECONDS,
        max_requests: int = NORMAL_MAX_RUN_REQUESTS,
        max_elapsed_seconds: float = NORMAL_MAX_COLLECTION_SECONDS,
        clock: Any = time.monotonic,
        sleeper: Any = time.sleep,
    ) -> None:
        if (
            type(requests_per_window) is not int
            or requests_per_window <= 0
            or type(max_requests) is not int
            or max_requests <= 0
            or window_seconds <= 0
            or max_elapsed_seconds <= 0
        ):
            raise ValueError("invalid_normal_request_budget")
        self.requests_per_window = requests_per_window
        self.window_seconds = float(window_seconds)
        self.max_requests = max_requests
        self.max_elapsed_seconds = float(max_elapsed_seconds)
        self.clock = clock
        self.sleeper = sleeper
        self.started = float(clock())
        self.logical_now = self.started
        self.request_times: List[float] = []
        self.total_requests = 0
        self.total_wait_seconds = 0.0
        self.block_reason: Optional[str] = None
        self.restriction_events: List[str] = []

    def block(self, reason: str) -> None:
        if reason not in self.restriction_events:
            self.restriction_events.append(reason)
        if self.block_reason is None:
            self.block_reason = reason

    def permit_endpoint_fallback(self) -> bool:
        """Allow one existing endpoint-specific recovery after a primary 429."""
        if self.block_reason != "provider_rate_limited_http_429":
            return False
        self.block_reason = None
        return True

    def acquire(self) -> None:
        if self.block_reason is not None:
            raise NormalCollectionDeferred(self.block_reason)
        if self.total_requests >= self.max_requests:
            self.block("run_request_budget_exhausted")
            raise NormalCollectionDeferred(self.block_reason)

        now = max(float(self.clock()), self.logical_now)
        self.request_times = [
            stamp for stamp in self.request_times
            if now - stamp < self.window_seconds
        ]
        if len(self.request_times) >= self.requests_per_window:
            wait_seconds = self.window_seconds - (now - self.request_times[0])
            wait_seconds = max(0.0, wait_seconds)
            if now + wait_seconds - self.started > self.max_elapsed_seconds:
                self.block("run_time_budget_exhausted")
                raise NormalCollectionDeferred(self.block_reason)
            self.sleeper(wait_seconds)
            self.total_wait_seconds += wait_seconds
            now = max(float(self.clock()), now + wait_seconds)
            self.logical_now = now
            self.request_times = [
                stamp for stamp in self.request_times
                if now - stamp < self.window_seconds
            ]

        if now - self.started > self.max_elapsed_seconds:
            self.block("run_time_budget_exhausted")
            raise NormalCollectionDeferred(self.block_reason)
        self.request_times.append(now)
        self.logical_now = now
        self.total_requests += 1

    def evidence(self) -> Dict[str, Any]:
        return {
            "policy": "public_historical_sliding_window",
            "requests_per_minute": self.requests_per_window,
            "window_seconds": self.window_seconds,
            "max_run_requests": self.max_requests,
            "max_collection_seconds": self.max_elapsed_seconds,
            "provider_requests_performed": self.total_requests,
            "rate_wait_seconds": round(self.total_wait_seconds, 3),
            "deferred_reason": self.block_reason,
            "restriction_events": list(self.restriction_events),
            "credentials_or_paid_live_access_used": False,
        }


def _http_status_from_request_status(status: Any) -> Optional[int]:
    match = re.fullmatch(r"http_([1-5][0-9]{2})", str(status or ""))
    return int(match.group(1)) if match else None


def _material_request_failure(status: Any) -> bool:
    text = str(status or "")
    code = _http_status_from_request_status(text)
    return text.startswith("deferred_") or text in MATERIAL_REQUEST_STATUSES or (
        code is not None and code != 404
    )


def _request_statuses(entries: List[Dict[str, Any]]) -> List[str]:
    return [str(entry.get("status") or "unknown") for entry in entries]


def _availability_reason(scope: str, status: str) -> str:
    code = _http_status_from_request_status(status)
    if code in {401, 403}:
        return f"{scope}_access_restricted:http_{code}"
    if code == 429:
        return f"{scope}_rate_limited:http_429"
    if code is not None and code >= 500:
        return f"{scope}_provider_unavailable:http_{code}"
    if code == 404:
        return f"{scope}_not_found:http_404"
    if status == "zero_rows":
        return f"{scope}_available_zero_rows"
    if status.startswith("deferred_"):
        return f"{scope}_deferred:{status.removeprefix('deferred_')}"
    if status in {"invalid_json", "invalid_response_schema", "invalid_sessions_schema"}:
        return f"{scope}_response_invalid:{status}"
    if status in {"exception", "invalid_http_status"}:
        return f"{scope}_transport_unavailable:{status}"
    return f"{scope}_unavailable:{status}"


def utc_now() -> dt.datetime:
    """Timezone-aware UTC timestamp, compatible with modern Python."""
    return dt.datetime.now(dt.UTC)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def slugify(value: Any) -> str:
    s = str(value or "unknown")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s or "unknown"


def _shadow_require(condition: bool, reason: str) -> None:
    if not condition:
        raise ProvenanceShadowHold(reason)


def _positive_decimal(value: Any, reason: str) -> str:
    _shadow_require(type(value) in (str, int) and type(value) is not bool, reason)
    text = str(value)
    _shadow_require(re.fullmatch(r"[1-9][0-9]*", text) is not None, reason)
    return text


def _selected_shadow_endpoint(value: Any) -> str:
    _shadow_require(type(value) is str and value in SHADOW_ENDPOINTS,
                    "provenance_shadow_endpoint_unsupported")
    return value


def _sha256_text(value: Any, reason: str) -> str:
    _shadow_require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                    reason)
    return value


def _required_text(value: Any, reason: str) -> str:
    _shadow_require(type(value) is str and value.strip() == value and bool(value), reason)
    _shadow_require(not any(ord(character) < 32 or ord(character) == 127 for character in value), reason)
    return value


def _parse_utc(value: Any, reason: str) -> dt.datetime:
    _shadow_require(type(value) is str and bool(value), reason)
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise ProvenanceShadowHold(reason) from exc
    _shadow_require(parsed.tzinfo is not None and parsed.utcoffset() is not None, reason)
    return parsed.astimezone(dt.UTC)


def _format_utc(value: dt.datetime) -> str:
    timespec = "microseconds" if value.microsecond else "seconds"
    return value.astimezone(dt.UTC).isoformat(timespec=timespec).replace("+00:00", "Z")


def _clock_utc(clock: Any) -> str:
    value = clock()
    if isinstance(value, dt.datetime):
        _shadow_require(value.tzinfo is not None and value.utcoffset() is not None,
                        "shadow_clock_not_utc")
        return _format_utc(value)
    parsed = _parse_utc(value, "shadow_clock_not_utc")
    return _format_utc(parsed)


def _strict_json_bytes(raw: bytes, *, expected_type: type, reason: str) -> Any:
    _shadow_require(type(raw) is bytes and bool(raw), reason)

    def pairs(items: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
        value: Dict[str, Any] = {}
        for key, item in items:
            _shadow_require(key not in value, reason)
            value[key] = item
        return value

    def reject_constant(_value: str) -> None:
        raise ProvenanceShadowHold(reason)

    try:
        parsed = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    except ProvenanceShadowHold:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ProvenanceShadowHold(reason) from exc
    _shadow_require(type(parsed) is expected_type, reason)
    return parsed


def _default_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _json_safe_assessment(assessment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in assessment.items()
        if key not in {"raw_response_bytes", "source_capture_receipt_bytes"}
    }


def _validate_shadow_identity(
    *, repository: str, workflow: str, workflow_ref: str, ref: str,
    head_sha: str, run_id: str, run_attempt: str,
) -> Dict[str, str]:
    expected_ref = "refs/heads/main"
    expected_workflow_ref = f"{SHADOW_REPOSITORY}/{SHADOW_WORKFLOW_PATH}@{expected_ref}"
    _shadow_require(repository == SHADOW_REPOSITORY, "workflow_repository_mismatch")
    _shadow_require(workflow == SHADOW_WORKFLOW_NAME, "workflow_name_mismatch")
    _shadow_require(ref == expected_ref, "shadow_requires_main")
    _shadow_require(workflow_ref == expected_workflow_ref, "workflow_ref_mismatch")
    _shadow_require(type(head_sha) is str and re.fullmatch(r"[0-9a-f]{40}", head_sha) is not None,
                    "workflow_head_sha_malformed")
    return {
        "repository": repository,
        "workflow": workflow,
        "workflow_ref": workflow_ref,
        "ref": ref,
        "head_sha": head_sha,
        "run_id": _positive_decimal(run_id, "workflow_run_id_malformed"),
        "run_attempt": _positive_decimal(run_attempt, "workflow_run_attempt_malformed"),
    }


def _selected_session(
    sessions: List[Any], selected_session_key: str, season: int, *,
    reject_malformed_rows: bool = False,
) -> Dict[str, Any]:
    matches = []
    for row in sessions:
        if type(row) is not dict:
            raise ProvenanceShadowHold("malformed_session_metadata")
        try:
            row_key = _positive_decimal(row.get("session_key"), "malformed_session_metadata")
        except ProvenanceShadowHold:
            if reject_malformed_rows:
                raise
            continue
        if row_key == selected_session_key:
            matches.append(row)
    _shadow_require(len(matches) == 1, "selected_session_not_unique")
    selected = matches[0]
    meeting_key = _positive_decimal(selected.get("meeting_key"), "malformed_session_metadata")
    year = _positive_decimal(selected.get("year"), "malformed_session_metadata")
    _shadow_require(year == str(season), "selected_session_year_mismatch")
    country = _required_text(selected.get("country_name"), "malformed_session_metadata")
    location = _required_text(selected.get("location"), "malformed_session_metadata")
    circuit = _required_text(selected.get("circuit_short_name"), "malformed_session_metadata")
    date_end = _parse_utc(selected.get("date_end"), "malformed_session_metadata")
    event_id = "_".join((year, meeting_key, slugify(country), slugify(location), slugify(circuit)))
    return {
        "event_id": event_id,
        "meeting_id": meeting_key,
        "session_id": selected_session_key,
        "session_end": date_end,
        "session_end_utc": _format_utc(date_end),
    }


def _session_not_cancelled(row: Dict[str, Any], reason: str) -> None:
    for field in ("cancelled", "canceled", "is_cancelled", "is_canceled"):
        if field in row:
            _shadow_require(row[field] is False, reason)
    for field in ("status", "session_status"):
        if field in row:
            status = _required_text(row[field], reason).lower()
            _shadow_require(status not in {"cancelled", "canceled"}, reason)


def _selected_qualifying_source_and_race_target(
    sessions: List[Any], selected_session_key: str, season: int,
) -> Dict[str, Any]:
    """Select one Qualifying grid source and one later same-event Race target."""
    source_scope = _selected_session(
        sessions,
        selected_session_key,
        season,
        reject_malformed_rows=True,
    )
    source = next(
        row for row in sessions
        if str(row.get("session_key")) == selected_session_key
    )
    _shadow_require(
        source.get("session_name") == "Qualifying"
        and source.get("session_type") == "Qualifying",
        "selected_grid_source_not_qualifying",
    )
    _session_not_cancelled(source, "selected_grid_source_cancelled")
    source_start = _parse_utc(
        source.get("date_start"), "malformed_session_metadata"
    )
    _shadow_require(source_scope["session_end"] >= source_start,
                    "grid_source_chronology_invalid")

    source_year = _positive_decimal(source.get("year"), "malformed_session_metadata")
    source_meeting = source_scope["meeting_id"]
    source_country = _required_text(
        source.get("country_name"), "malformed_session_metadata"
    )
    source_location = _required_text(
        source.get("location"), "malformed_session_metadata"
    )
    source_circuit = _required_text(
        source.get("circuit_short_name"), "malformed_session_metadata"
    )

    race_candidates = []
    for row in sessions:
        if type(row) is not dict:
            raise ProvenanceShadowHold("malformed_session_metadata")
        if row.get("session_name") != "Race" or row.get("session_type") != "Race":
            continue
        race_key = _positive_decimal(
            row.get("session_key"), "malformed_target_race_metadata"
        )
        meeting_key = _positive_decimal(
            row.get("meeting_key"), "malformed_target_race_metadata"
        )
        year = _positive_decimal(row.get("year"), "malformed_target_race_metadata")
        if meeting_key != source_meeting:
            continue
        _shadow_require(year == source_year == str(season),
                        "target_race_year_mismatch")
        _shadow_require(race_key != selected_session_key,
                        "target_race_matches_source_session")
        _session_not_cancelled(row, "target_race_cancelled")
        country = _required_text(
            row.get("country_name"), "malformed_target_race_metadata"
        )
        location = _required_text(
            row.get("location"), "malformed_target_race_metadata"
        )
        circuit = _required_text(
            row.get("circuit_short_name"), "malformed_target_race_metadata"
        )
        _shadow_require(
            (country, location, circuit)
            == (source_country, source_location, source_circuit),
            "target_race_event_identity_mismatch",
        )
        race_start = _parse_utc(
            row.get("date_start"), "malformed_target_race_metadata"
        )
        race_end = _parse_utc(row.get("date_end"), "malformed_target_race_metadata")
        _shadow_require(race_end >= race_start, "target_race_chronology_invalid")
        _shadow_require(
            race_start > source_scope["session_end"],
            "target_race_not_after_qualifying_source",
        )
        race_candidates.append({
            "session_id": race_key,
            "session_start_utc": _format_utc(race_start),
            "session_end_utc": _format_utc(race_end),
        })

    _shadow_require(len(race_candidates) == 1, "target_race_not_unique")
    return {
        **source_scope,
        "source_session_start_utc": _format_utc(source_start),
        "source_session_kind": "Qualifying",
        "target_race_session_id": race_candidates[0]["session_id"],
        "target_race_session_kind": "Race",
        "target_race_start_utc": race_candidates[0]["session_start_utc"],
        "target_race_end_utc": race_candidates[0]["session_end_utc"],
    }


def _response_header(response: Any, name: str) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        direct = headers.get(name)
        if direct is not None:
            return direct
        for key, value in headers.items():
            if type(key) is str and key.lower() == name.lower():
                return value
        return None
    except (AttributeError, TypeError):
        raise ProvenanceShadowHold("response_headers_malformed")


def _diagnostic_http_status_code(response: Any) -> Optional[int]:
    """Return only a real, bounded HTTP status integer for diagnostics."""
    status = getattr(response, "status_code", None)
    if type(status) is int and 100 <= status <= 599:
        return status
    return None


def _validated_starting_grid_response(
    response: Any, *, expected_uri: str, label: str,
) -> bytes:
    """Validate bounded, non-redirected JSON HTTP evidence for K4R15."""
    _shadow_require(
        getattr(response, "status_code", None) == 200,
        f"{label}_http_status_not_200",
    )
    _shadow_require(
        getattr(response, "url", None) == expected_uri,
        f"{label}_final_url_mismatch",
    )
    history = getattr(response, "history", None)
    _shadow_require(
        isinstance(history, (list, tuple)) and len(history) == 0,
        f"{label}_redirect_forbidden",
    )
    content_type = _response_header(response, "Content-Type")
    if content_type is not None:
        _shadow_require(
            type(content_type) is str
            and content_type.split(";", 1)[0].strip().lower() == "application/json",
            f"{label}_content_type_not_json",
        )
    content = getattr(response, "content", None)
    _shadow_require(type(content) is bytes, f"{label}_response_not_bytes")
    _shadow_require(
        0 < len(content) <= SHADOW_MAX_RESPONSE_BYTES,
        f"{label}_response_size_out_of_bounds",
    )
    return content


def _persist_shadow_metadata(
    root: Path,
    *,
    assessment: Dict[str, Any],
    manifest: Dict[str, Any],
    write_bytes: Any,
) -> None:
    write_bytes(root / "historical_rest_capture_assessment.json", _json_bytes(assessment))
    write_bytes(root / "shadow_manifest.json", _json_bytes(manifest))
    if manifest.get("selected_endpoint") == "drivers":
        report = [
            "# DR-002 pre-2B-7K4R7 OpenF1 drivers historical REST provenance shadow",
            "",
            f"Status: {manifest['status']}",
            f"Reason: {manifest.get('reason')}",
            "Selected endpoint: drivers",
            f"K4R1 status: {manifest.get('k4r1_status')}",
            f"K4R6 status: {manifest.get('k4r6_status')}",
            f"Driver rows: {manifest.get('drivers_row_count')}",
            f"Unique drivers: {manifest.get('drivers_unique_driver_count')}",
            f"Derived CSV SHA-256: {manifest.get('drivers_derived_csv_sha256')}",
            f"Derived runtime identity: {manifest.get('drivers_derived_runtime_identity')}",
            "",
            "The raw drivers response and parentless source-capture receipt are the source",
            "evidence. Derived CSV metadata is runtime metadata only; no CSV was persisted.",
            "OpenF1 is not official FIA/F1 roster authority and this does not prove earlier",
            "historical availability, complete revisions, a trustworthy final grid, or a forecast.",
            "",
            "Integration capability only. This is not blind validation, stable-engine execution,",
            "production enforcement, DR-002 activation, promotion, or an accuracy claim.",
            "",
            "DR-002 remains PROPOSED — NOT ACTIVATED. Forecast gate OFF. Promotion NOT ALLOWED.",
        ]
    elif manifest.get("selected_endpoint") == "starting_grid":
        discovery_hash = manifest.get("session_discovery_raw_sha256")
        target_race_id = manifest.get("grid_target_race_session_id")
        grid_hash = manifest.get("starting_grid_raw_sha256")
        if (manifest.get("status") == historical_rest_contract.VALIDATED
                and discovery_hash and target_race_id and grid_hash):
            evidence_report = [
                "The raw sessions discovery links a provider-reported Qualifying source",
                "to a distinct later Race target in the same event. The parentless K4R1",
                "receipt and derived CSV remain scoped to the Qualifying source session.",
                "The K4R14 CSV is runtime metadata only and was not persisted or joined",
                "to the Race target.",
            ]
        elif not discovery_hash:
            evidence_report = [
                "No raw session-discovery data was accepted; no source-to-Race link was established.",
                "No starting-grid source capture or source-capture receipt was created.",
            ]
        elif not target_race_id:
            evidence_report = [
                "Raw session-discovery data was accepted, but no unique source-to-Race link",
                "was established. No starting-grid source capture or receipt was created.",
            ]
        elif not grid_hash:
            evidence_report = [
                "Raw session-discovery data was accepted and linked a provider-reported",
                "Qualifying source to a distinct later Race target. The subsequent starting-grid",
                "response was rejected; no starting-grid source capture or receipt was created.",
            ]
        else:
            evidence_report = [
                "Raw session-discovery and starting-grid data were accepted, but downstream",
                "validation did not complete. No successful derived-grid result is claimed.",
            ]
        report = [
            "# DR-002 pre-2B-7K4R19 OpenF1 Qualifying grid / Race target shadow",
            "",
            f"Status: {manifest['status']}",
            f"Reason: {manifest.get('reason')}",
            "Selected endpoint: starting_grid",
            (f"Grid source: {manifest.get('grid_source_session_kind')} session "
             f"{manifest.get('grid_source_session_id')}"),
            (f"Race target: {manifest.get('grid_target_race_session_kind')} session "
             f"{manifest.get('grid_target_race_session_id')}"),
            f"K4R1 status: {manifest.get('k4r1_status')}",
            f"K4R14 status: {manifest.get('k4r14_status')}",
            f"Grid rows: {manifest.get('starting_grid_row_count')}",
            f"Unique drivers: {manifest.get('starting_grid_unique_driver_count')}",
            f"Grid slots: {manifest.get('starting_grid_slot_count')}",
            f"Derived CSV SHA-256: {manifest.get('starting_grid_derived_csv_sha256')}",
            f"Derived runtime identity: {manifest.get('starting_grid_derived_runtime_identity')}",
            "",
            *evidence_report,
            "OpenF1 is unofficial and this does not authenticate an official FIA final",
            "grid, prove historical pre-race availability, or generate a forecast.",
            "",
            "Integration capability only. No producer, model, stable engine, workflow",
            "dispatch, repository mutation, activation, promotion, or accuracy claim.",
            "",
            "DR-002 remains PROPOSED — NOT ACTIVATED. Forecast gate OFF. Promotion NOT ALLOWED.",
        ]
    else:
        report = [
            "# DR-002 pre-2B-7K4R2 OpenF1 historical REST provenance shadow",
            "",
            f"Status: {manifest['status']}",
            f"Reason: {manifest.get('reason')}",
            "",
            "Integration capability only. This is not blind validation, stable-engine execution,",
            "production enforcement, DR-002 activation, promotion, or an accuracy claim.",
            "",
            "DR-002 remains PROPOSED — NOT ACTIVATED. Forecast gate OFF. Promotion NOT ALLOWED.",
        ]
    write_bytes(root / "shadow_report.md", ("\n".join(report) + "\n").encode("utf-8"))


def run_provenance_shadow(
    *,
    session_key: Any,
    season: int,
    output_root: Path,
    repository: str,
    workflow: str,
    workflow_ref: str,
    ref: str,
    head_sha: str,
    run_id: Any,
    run_attempt: Any,
    http_get: Any = requests.get,
    clock: Any = iso_now,
    assessor: Any = historical_rest_contract.assess_openf1_historical_rest_capture,
    write_bytes: Any = _default_write_bytes,
    read_bytes: Any = lambda path: path.read_bytes(),
    endpoint: Any = SHADOW_ENDPOINT,
    drivers_adapter: Any = drivers_adapter_contract.adapt_openf1_drivers_to_producer_input,
    starting_grid_adapter: Any = (
        starting_grid_adapter_contract.adapt_openf1_starting_grid_to_producer_input
    ),
) -> Dict[str, Any]:
    """Run one manual, main-only, exact-byte historical provenance shadow."""
    selected_endpoint = _selected_shadow_endpoint(endpoint)
    selected_key = _positive_decimal(session_key, "selected_session_key_malformed")
    run_id_text = _positive_decimal(run_id, "workflow_run_id_malformed")
    run_attempt_text = _positive_decimal(run_attempt, "workflow_run_attempt_malformed")
    root = (Path(output_root).resolve() / "_runtime" / SHADOW_RUNTIME_DIR
            / f"gha-{run_id_text}-{run_attempt_text}")
    root.mkdir(parents=True, exist_ok=False)
    manifest: Dict[str, Any] = {
        "schema_version": (
            STARTING_GRID_SHADOW_SCHEMA_VERSION
            if selected_endpoint == "starting_grid"
            else SHADOW_SCHEMA_VERSION
        ),
        "status": historical_rest_contract.HOLD,
        "reason": None,
        "repository": repository,
        "workflow": workflow,
        "workflow_ref": workflow_ref,
        "ref": ref,
        "head_sha": head_sha,
        "run_id": run_id_text,
        "run_attempt": run_attempt_text,
        "event_id": None,
        "meeting_id": None,
        "session_id": selected_key,
        "canonical_request_uri": None,
        "raw_response_sha256": None,
        "receipt_sha256": None,
        "first_observed_utc": None,
        "ingested_utc": None,
        "receipt_created_utc": None,
        "row_count": None,
        "historical_window_eligible_utc": None,
        "openf1_documented_historical_window_satisfied": False,
        "k4r1_status": historical_rest_contract.HOLD,
        "receipt_type": None,
        "verified_receipt_bindings_created": False,
        "latest_or_history_written": False,
        "repository_mutation_performed": False,
        "dr002_activated": False,
        "promotion_allowed": False,
    }
    if selected_endpoint == "drivers":
        manifest.update(
            selected_endpoint="drivers",
            raw_response_filename="drivers.response.json",
            k4r6_status=drivers_adapter_contract.HOLD,
            drivers_row_count=None,
            drivers_unique_driver_count=None,
            drivers_derived_csv_sha256=None,
            drivers_derived_runtime_identity=None,
            derived_csv_persisted=False,
            derived_csv_is_source_evidence=False,
            new_scientific_receipt_created=False,
            normalization_receipt_created=False,
            openf1_official_f1_roster_authority=False,
            historical_availability_before_first_observation_proven=False,
        )
    elif selected_endpoint == "starting_grid":
        manifest.update(
            selected_endpoint="starting_grid",
            session_metadata_source_type="OPENF1_PROVIDER_DISCOVERY_CLAIM",
            grid_source_session_id=None,
            grid_source_session_kind=None,
            grid_source_start_utc=None,
            grid_source_end_utc=None,
            grid_target_race_session_id=None,
            grid_target_race_session_kind=None,
            grid_target_race_start_utc=None,
            grid_target_race_end_utc=None,
            source_to_race_link_evidence_type=None,
            source_session_classification_authenticated=False,
            target_race_session_classification_authenticated=False,
            producer_input_csv_is_target_race_scoped=False,
            cross_session_join_authorized=False,
            discovery_source_capture_receipt_created=False,
            raw_response_filename="starting_grid.response.json",
            session_discovery_filename="sessions.response.json",
            session_discovery_request_uri=None,
            session_discovery_request_attempted=False,
            session_discovery_http_status_code=None,
            session_discovery_raw_sha256=None,
            session_discovery_actual_received_utc=None,
            discovery_response_sha256=None,
            discovery_first_observed_utc=None,
            starting_grid_raw_sha256=None,
            starting_grid_request_attempted=False,
            starting_grid_http_status_code=None,
            k4r14_status=starting_grid_adapter_contract.HOLD,
            starting_grid_row_count=None,
            starting_grid_unique_driver_count=None,
            starting_grid_slot_count=None,
            starting_grid_derived_csv_sha256=None,
            starting_grid_derived_runtime_identity=None,
            grid_row_count=None,
            unique_driver_count=None,
            slot_count=None,
            derived_csv_sha256=None,
            derived_runtime_identity=None,
            source_receipt_id=None,
            raw_source_id=None,
            frozen_evidence_manifest_sha256=None,
            frozen_evidence_binding_status=None,
            derived_csv_persisted=False,
            official_fia_grid_authenticated=False,
            official_final_grid_verified=False,
            source_earliest_availability_verified=False,
            historical_pre_race_availability_proven=False,
            race_session_authority_authenticated=False,
            derived_csv_is_source_evidence=False,
            verified_receipt_bindings_created=False,
            new_scientific_receipt_created=False,
            blind_validation_eligible=False,
            stable_engine_execution_proven=False,
            production_forecast_generated=False,
            commercial_or_redistribution_permission_claimed=False,
            revision_completeness_verified=False,
            official_final_grid_revision_verified=False,
            provider_revision_history_verified=False,
            historical_availability_proven=False,
            pre_race_availability_proven=False,
        )
    assessment_projection: Dict[str, Any] = {
        "status": historical_rest_contract.HOLD,
        "reason_codes": ["shadow_not_completed"],
    }
    try:
        identity = _validate_shadow_identity(
            repository=repository,
            workflow=workflow,
            workflow_ref=workflow_ref,
            ref=ref,
            head_sha=head_sha,
            run_id=run_id_text,
            run_attempt=run_attempt_text,
        )
        manifest.update(identity)

        discovery_uri = f"{API_BASE}/sessions?year={int(season)}"
        discovery_request_options = {
            "timeout": REQUEST_TIMEOUT,
            "headers": {"Accept": "application/json", "Accept-Encoding": "identity"},
        }
        if selected_endpoint == "starting_grid":
            discovery_request_options["allow_redirects"] = False
            manifest["session_discovery_request_attempted"] = True
        discovery_response = http_get(discovery_uri, **discovery_request_options)
        if selected_endpoint == "starting_grid":
            discovery_status = _diagnostic_http_status_code(discovery_response)
            manifest["session_discovery_http_status_code"] = discovery_status
            _shadow_require(
                discovery_status is not None,
                "session_discovery_http_status_unavailable",
            )
            discovery_bytes = _validated_starting_grid_response(
                discovery_response,
                expected_uri=discovery_uri,
                label="session_discovery",
            )
            discovery_actual_received_utc = _clock_utc(clock)
            discovery_path = root / "sessions.response.json"
            write_bytes(discovery_path, discovery_bytes)
            discovery_readback = read_bytes(discovery_path)
            _shadow_require(
                discovery_readback == discovery_bytes,
                "session_discovery_readback_mismatch",
            )
            discovery_sha = hashlib.sha256(discovery_bytes).hexdigest()
            _shadow_require(
                hashlib.sha256(discovery_readback).hexdigest() == discovery_sha,
                "session_discovery_readback_hash_mismatch",
            )
            manifest.update(
                session_discovery_request_uri=discovery_uri,
                session_discovery_raw_sha256=discovery_sha,
                session_discovery_actual_received_utc=discovery_actual_received_utc,
                discovery_response_sha256=discovery_sha,
                discovery_first_observed_utc=discovery_actual_received_utc,
            )
        else:
            discovery_status = getattr(discovery_response, "status_code", None)
            discovery_bytes = getattr(discovery_response, "content", None)
            _shadow_require(discovery_status == 200, "session_discovery_http_status_not_200")
        sessions = _strict_json_bytes(
            discovery_bytes,
            expected_type=list,
            reason="malformed_session_discovery_response",
        )
        if selected_endpoint == "starting_grid":
            scope = _selected_qualifying_source_and_race_target(
                sessions, selected_key, int(season)
            )
            manifest.update(
                grid_source_session_id=scope["session_id"],
                grid_source_session_kind=scope["source_session_kind"],
                grid_source_start_utc=scope["source_session_start_utc"],
                grid_source_end_utc=scope["session_end_utc"],
                grid_target_race_session_id=scope["target_race_session_id"],
                grid_target_race_session_kind=scope["target_race_session_kind"],
                grid_target_race_start_utc=scope["target_race_start_utc"],
                grid_target_race_end_utc=scope["target_race_end_utc"],
                source_to_race_link_evidence_type=(
                    "OPENF1_PROVIDER_DISCOVERY_CLAIM"
                ),
            )
        else:
            scope = _selected_session(
                sessions,
                selected_key,
                int(season),
                reject_malformed_rows=selected_endpoint == "drivers",
            )
        manifest.update({key: scope[key] for key in ("event_id", "meeting_id", "session_id")})

        eligibility = scope["session_end"] + dt.timedelta(
            seconds=historical_rest_contract.HISTORICAL_WINDOW_DELAY_SECONDS
        )
        manifest["historical_window_eligible_utc"] = _format_utc(eligibility)
        eligibility_check_utc = _clock_utc(clock)
        if selected_endpoint == "starting_grid":
            _shadow_require(
                _parse_utc(
                    manifest["session_discovery_actual_received_utc"],
                    "shadow_clock_not_utc",
                )
                <= _parse_utc(eligibility_check_utc, "shadow_clock_not_utc"),
                "session_discovery_clock_after_eligibility_check",
            )
        _shadow_require(
            _parse_utc(eligibility_check_utc, "shadow_clock_not_utc") >= eligibility,
            "selected_session_before_historical_window",
        )

        source_uri = f"{API_BASE}/{selected_endpoint}?session_key={selected_key}"
        source_request_options = {
            "timeout": REQUEST_TIMEOUT,
            "headers": {"Accept": "application/json", "Accept-Encoding": "identity"},
        }
        if selected_endpoint == "starting_grid":
            source_request_options["allow_redirects"] = False
            manifest["starting_grid_request_attempted"] = True
        source_response = http_get(source_uri, **source_request_options)
        http_status = getattr(source_response, "status_code", None)
        if selected_endpoint == "starting_grid":
            http_status = _diagnostic_http_status_code(source_response)
            manifest["starting_grid_http_status_code"] = http_status
            _shadow_require(
                http_status is not None,
                "starting_grid_http_status_unavailable",
            )
            raw_response_bytes = _validated_starting_grid_response(
                source_response,
                expected_uri=source_uri,
                label="starting_grid",
            )
        else:
            raw_response_bytes = getattr(source_response, "content", None)
            _shadow_require(type(raw_response_bytes) is bytes, "raw_response_not_bytes")
        first_observed_utc = _clock_utc(clock)
        manifest["first_observed_utc"] = first_observed_utc

        raw_path = root / f"{selected_endpoint}.response.json"
        write_bytes(raw_path, raw_response_bytes)
        raw_readback = read_bytes(raw_path)
        _shadow_require(raw_readback == raw_response_bytes, "raw_response_readback_mismatch")
        raw_sha = hashlib.sha256(raw_response_bytes).hexdigest()
        _shadow_require(hashlib.sha256(raw_readback).hexdigest() == raw_sha,
                        "raw_response_readback_hash_mismatch")
        ingested_utc = _clock_utc(clock)
        receipt_created_utc = _clock_utc(clock)
        if selected_endpoint == "starting_grid":
            chronological = [
                manifest["session_discovery_actual_received_utc"],
                eligibility_check_utc,
                first_observed_utc,
                ingested_utc,
                receipt_created_utc,
            ]
            _shadow_require(
                all(
                    _parse_utc(earlier, "shadow_clock_not_utc")
                    <= _parse_utc(later, "shadow_clock_not_utc")
                    for earlier, later in zip(chronological, chronological[1:])
                ),
                "shadow_clock_chronology_invalid",
            )
        manifest.update(
            canonical_request_uri=source_uri,
            raw_response_sha256=raw_sha,
            ingested_utc=ingested_utc,
            receipt_created_utc=receipt_created_utc,
        )
        if selected_endpoint == "starting_grid":
            manifest["starting_grid_raw_sha256"] = raw_sha

        assessment = assessor(
            event_id=scope["event_id"],
            meeting_id=scope["meeting_id"],
            session_id=scope["session_id"],
            endpoint=selected_endpoint,
            request_params={"session_key": selected_key},
            raw_response_bytes=raw_response_bytes,
            http_status=http_status,
            session_end_utc=scope["session_end_utc"],
            first_observed_utc=first_observed_utc,
            ingested_utc=ingested_utc,
            receipt_created_utc=receipt_created_utc,
            capture_ref=str(raw_path.relative_to(Path(output_root).resolve())),
            implementation=SHADOW_IMPLEMENTATION,
        )
        _shadow_require(type(assessment) is dict, "k4r1_assessment_malformed")
        assessment_projection = _json_safe_assessment(assessment)
        manifest["k4r1_status"] = assessment.get("status")
        _shadow_require(
            assessment.get("status") == historical_rest_contract.VALIDATED,
            "k4r1_hold:" + ",".join(assessment.get("reason_codes") or ["unspecified"]),
        )
        _shadow_require(assessment.get("canonical_request_uri") == source_uri,
                        "k4r1_request_uri_mismatch")
        _shadow_require(assessment.get("raw_response_sha256") == raw_sha,
                        "k4r1_raw_response_hash_mismatch")
        receipt_bytes = assessment.get("source_capture_receipt_bytes")
        _shadow_require(type(receipt_bytes) is bytes and bool(receipt_bytes),
                        "k4r1_receipt_bytes_missing")
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        _shadow_require(receipt_sha == assessment.get("receipt_sha256"),
                        "k4r1_receipt_hash_mismatch")
        receipt = _strict_json_bytes(
            receipt_bytes,
            expected_type=dict,
            reason="k4r1_receipt_malformed",
        )
        _shadow_require(
            historical_rest_contract.receipt_contract.canonical_json_bytes(receipt)
            == receipt_bytes,
            "k4r1_receipt_not_canonical",
        )
        _shadow_require(receipt.get("receipt_type") == "source_capture",
                        "k4r1_receipt_type_mismatch")
        _shadow_require(receipt.get("parent_receipt_ids") == [],
                        "k4r1_receipt_has_parents")
        _shadow_require(receipt.get("scope") == {
            "event_id": scope["event_id"],
            "meeting_id": scope["meeting_id"],
            "session_id": scope["session_id"],
        }, "k4r1_receipt_scope_mismatch")
        receipt_payload = receipt.get("payload")
        _shadow_require(type(receipt_payload) is dict, "k4r1_receipt_payload_malformed")
        _shadow_require(receipt_payload.get("source_uri") == source_uri,
                        "k4r1_receipt_source_uri_mismatch")
        expected_source_id = (
            f"openf1:{selected_endpoint}:"
            + hashlib.sha256(source_uri.encode("utf-8")).hexdigest()
        )
        _shadow_require(receipt_payload.get("source_id") == expected_source_id,
                        "k4r1_receipt_source_id_mismatch")
        _shadow_require(receipt_payload.get("source_sha256") == raw_sha,
                        "k4r1_receipt_source_hash_mismatch")
        _shadow_require("verified_receipt_bindings" not in receipt,
                        "verified_receipt_bindings_forbidden")
        receipt_path = root / "source_capture_receipt.json"
        write_bytes(receipt_path, receipt_bytes)
        receipt_readback = read_bytes(receipt_path)
        _shadow_require(receipt_readback == receipt_bytes, "receipt_readback_mismatch")

        if selected_endpoint == "drivers":
            adapter_result = drivers_adapter(
                source_capture_receipt_bytes=receipt_readback,
                raw_drivers_response_bytes=raw_readback,
                event_id=scope["event_id"],
                meeting_id=scope["meeting_id"],
                session_id=scope["session_id"],
            )
            _shadow_require(type(adapter_result) is dict, "k4r6_result_malformed")
            manifest["k4r6_status"] = adapter_result.get("status")
            _shadow_require(
                adapter_result.get("status") == drivers_adapter_contract.VALIDATED,
                "k4r6_hold:" + ",".join(
                    adapter_result.get("reason_codes") or ["unspecified"]
                ),
            )
            derived_sha = _sha256_text(
                adapter_result.get("producer_input_sha256"),
                "k4r6_derived_csv_hash_malformed",
            )
            _shadow_require(
                adapter_result.get("derived_runtime_identity")
                == "derived:openf1-drivers-csv:" + derived_sha,
                "k4r6_derived_runtime_identity_mismatch",
            )
            driver_rows = adapter_result.get("row_count")
            unique_drivers = adapter_result.get("unique_driver_count")
            _shadow_require(type(driver_rows) is int and driver_rows > 0,
                            "k4r6_driver_row_count_malformed")
            _shadow_require(type(unique_drivers) is int
                            and 0 < unique_drivers <= driver_rows,
                            "k4r6_unique_driver_count_malformed")
            _shadow_require(adapter_result.get("scope") == receipt["scope"],
                            "k4r6_scope_mismatch")
            _shadow_require(adapter_result.get("source_receipt_id") == receipt["receipt_id"],
                            "k4r6_receipt_id_mismatch")
            _shadow_require(adapter_result.get("raw_source_sha256") == raw_sha,
                            "k4r6_raw_source_hash_mismatch")
            for flag in (
                "derived_csv_is_source_evidence",
                "new_scientific_receipt_created",
                "normalization_receipt_created",
                "verified_receipt_bindings_created",
            ):
                _shadow_require(adapter_result.get(flag) is False,
                                "k4r6_forbidden_claim:" + flag)
            manifest.update(
                drivers_row_count=driver_rows,
                drivers_unique_driver_count=unique_drivers,
                drivers_derived_csv_sha256=derived_sha,
                drivers_derived_runtime_identity=adapter_result["derived_runtime_identity"],
            )
        elif selected_endpoint == "starting_grid":
            adapter_result = starting_grid_adapter(
                source_capture_receipt_bytes=receipt_readback,
                raw_starting_grid_response_bytes=raw_readback,
                event_id=scope["event_id"],
                meeting_id=scope["meeting_id"],
                session_id=scope["session_id"],
                source_session_kind="Qualifying",
                target_race_session_id=scope["target_race_session_id"],
            )
            _shadow_require(type(adapter_result) is dict, "k4r14_result_malformed")
            manifest["k4r14_status"] = adapter_result.get("status")
            _shadow_require(
                adapter_result.get("status") == starting_grid_adapter_contract.VALIDATED,
                "k4r14_hold:" + ",".join(
                    adapter_result.get("reason_codes") or ["unspecified"]
                ),
            )
            _shadow_require(adapter_result.get("scope") == receipt["scope"],
                            "k4r14_scope_mismatch")
            _shadow_require(adapter_result.get("session_kind") == "Qualifying",
                            "k4r14_session_kind_mismatch")
            _shadow_require(
                adapter_result.get("source_qualifying_session_id")
                == scope["session_id"],
                "k4r14_source_session_id_mismatch",
            )
            _shadow_require(
                adapter_result.get("target_race_session_id")
                == scope["target_race_session_id"],
                "k4r14_target_race_session_id_mismatch",
            )
            _shadow_require(
                adapter_result.get("source_session_kind") == "Qualifying"
                and adapter_result.get("target_session_kind") == "Race",
                "k4r14_source_target_kind_mismatch",
            )
            _shadow_require(adapter_result.get("session_kind_asserted") is True,
                            "k4r14_session_kind_not_asserted")
            _shadow_require(
                adapter_result.get("session_kind_assertion_authenticated") is False,
                "k4r14_session_kind_authentication_forbidden",
            )
            for flag in (
                "source_session_classification_authenticated",
                "target_race_session_classification_authenticated",
                "producer_input_csv_is_target_race_scoped",
                "cross_session_join_authorized",
            ):
                _shadow_require(adapter_result.get(flag) is False,
                                "k4r14_forbidden_claim:" + flag)
            _shadow_require(
                adapter_result.get("provider_category")
                == "UNOFFICIAL_OPENF1_DOCUMENTED_REST",
                "k4r14_provider_category_mismatch",
            )
            _shadow_require(
                adapter_result.get("source_receipt_id") == receipt["receipt_id"],
                "k4r14_receipt_id_mismatch",
            )
            _shadow_require(
                adapter_result.get("raw_source_id") == receipt_payload["source_id"],
                "k4r14_raw_source_id_mismatch",
            )
            _shadow_require(adapter_result.get("raw_source_sha256") == raw_sha,
                            "k4r14_raw_source_hash_mismatch")
            derived_sha = _sha256_text(
                adapter_result.get("producer_input_sha256"),
                "k4r14_derived_csv_hash_malformed",
            )
            derived_csv_bytes = adapter_result.get("producer_input_csv_bytes")
            _shadow_require(
                type(derived_csv_bytes) is bytes
                and hashlib.sha256(derived_csv_bytes).hexdigest() == derived_sha,
                "k4r14_derived_csv_hash_mismatch",
            )
            _shadow_require(derived_sha != raw_sha,
                            "k4r14_derived_csv_not_distinct_from_raw")
            _shadow_require(
                adapter_result.get("derived_runtime_identity")
                == "derived:openf1-starting-grid-csv:" + derived_sha,
                "k4r14_derived_runtime_identity_mismatch",
            )
            _shadow_require(
                adapter_result.get("derived_runtime_identity")
                != receipt_payload["source_id"],
                "k4r14_derived_identity_not_distinct_from_source",
            )
            row_count = adapter_result.get("row_count")
            unique_drivers = adapter_result.get("unique_driver_count")
            slot_count = adapter_result.get("slot_count")
            _shadow_require(type(row_count) is int and row_count > 0,
                            "k4r14_row_count_malformed")
            _shadow_require(type(unique_drivers) is int and unique_drivers == row_count,
                            "k4r14_unique_driver_count_malformed")
            _shadow_require(type(slot_count) is int and slot_count == row_count,
                            "k4r14_slot_count_malformed")
            _shadow_require(assessment.get("row_count") == row_count,
                            "k4r1_k4r14_row_count_mismatch")
            frozen_manifest = adapter_result.get("frozen_evidence_manifest")
            frozen_sha = _sha256_text(
                adapter_result.get("frozen_evidence_manifest_sha256"),
                "k4r14_frozen_manifest_hash_malformed",
            )
            _shadow_require(type(frozen_manifest) is dict,
                            "k4r14_frozen_manifest_malformed")
            try:
                starting_grid_adapter_contract.frozen_contract.validate_frozen_evidence_manifest({
                    "manifest": frozen_manifest,
                    "frozen_evidence_manifest_sha256": frozen_sha,
                })
            except Exception as exc:
                raise ProvenanceShadowHold("k4r14_frozen_manifest_invalid") from exc
            _shadow_require(
                frozen_manifest.get("scope") == {
                    "event_id": scope["event_id"],
                    "meeting_id": scope["meeting_id"],
                    "allowed_session_ids": [scope["session_id"]],
                },
                "k4r14_frozen_manifest_scope_mismatch",
            )
            frozen_evidence = frozen_manifest.get("evidence")
            _shadow_require(
                type(frozen_evidence) is list
                and len(frozen_evidence) == 1
                and frozen_evidence[0].get("receipt_id") == receipt["receipt_id"]
                and frozen_evidence[0].get("source_id") == receipt_payload["source_id"]
                and frozen_evidence[0].get("source_sha256") == raw_sha,
                "k4r14_frozen_manifest_binding_mismatch",
            )
            _shadow_require(
                frozen_manifest.get("trust", {}).get("binding_status") == "UNBOUND",
                "k4r14_binding_status_mismatch",
            )
            for flag in starting_grid_adapter_contract.CLAIM_CEILINGS:
                _shadow_require(adapter_result.get(flag) is False,
                                "k4r14_forbidden_claim:" + flag)
                manifest[flag] = False
            _shadow_require(
                adapter_result.get("commercial_or_redistribution_permission_claimed")
                is False,
                "k4r14_forbidden_claim:commercial_or_redistribution_permission_claimed",
            )
            manifest.update(
                starting_grid_row_count=row_count,
                starting_grid_unique_driver_count=unique_drivers,
                starting_grid_slot_count=slot_count,
                starting_grid_derived_csv_sha256=derived_sha,
                starting_grid_derived_runtime_identity=(
                    adapter_result["derived_runtime_identity"]
                ),
                grid_row_count=row_count,
                unique_driver_count=unique_drivers,
                slot_count=slot_count,
                derived_csv_sha256=derived_sha,
                derived_runtime_identity=adapter_result["derived_runtime_identity"],
                source_receipt_id=receipt["receipt_id"],
                raw_source_id=receipt_payload["source_id"],
                frozen_evidence_manifest_sha256=frozen_sha,
                frozen_evidence_binding_status="UNBOUND",
            )

        manifest.update(
            status=historical_rest_contract.VALIDATED,
            reason=None,
            canonical_request_uri=assessment["canonical_request_uri"],
            receipt_sha256=receipt_sha,
            row_count=assessment.get("row_count"),
            historical_window_eligible_utc=assessment.get("historical_window_eligible_utc"),
            openf1_documented_historical_window_satisfied=assessment.get(
                "openf1_documented_historical_window_satisfied"
            ) is True,
            receipt_type="source_capture",
        )
        _persist_shadow_metadata(
            root,
            assessment=assessment_projection,
            manifest=manifest,
            write_bytes=write_bytes,
        )
        return manifest
    except Exception as exc:  # fail closed and retain a run-scoped diagnostic package
        reason = str(exc) or type(exc).__name__
        manifest.update(status=historical_rest_contract.HOLD, reason=reason)
        if assessment_projection.get("status") != historical_rest_contract.VALIDATED:
            reason_codes = assessment_projection.get("reason_codes") or [reason]
            if (
                selected_endpoint == "starting_grid"
                and reason_codes == ["shadow_not_completed"]
                and reason in {
                    "session_discovery_http_status_not_200",
                    "session_discovery_http_status_unavailable",
                    "starting_grid_http_status_not_200",
                    "starting_grid_http_status_unavailable",
                }
            ):
                reason_codes = [reason]
            assessment_projection = {
                **assessment_projection,
                "status": historical_rest_contract.HOLD,
                "reason_codes": reason_codes,
            }
        try:
            _persist_shadow_metadata(
                root,
                assessment=assessment_projection,
                manifest=manifest,
                write_bytes=write_bytes,
            )
        except Exception:
            pass
        if isinstance(exc, ProvenanceShadowHold):
            raise
        raise ProvenanceShadowHold(reason) from exc


def openf1_get(
    endpoint: str,
    params: Dict[str, Any],
    request_log: List[Dict[str, Any]],
    strategy: str,
    budget: Optional[NormalRequestBudget] = None,
) -> pd.DataFrame:
    url = f"{API_BASE}/{endpoint}"
    clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
    start = time.time()
    status = "unknown"
    error = ""
    rows = 0
    try:
        if budget is not None:
            budget.acquire()
        r = requests.get(url, params=clean_params, timeout=REQUEST_TIMEOUT)
        status_code = getattr(r, "status_code", None)
        if type(status_code) is not int or not 100 <= status_code <= 599:
            status = "invalid_http_status"
            error = repr(status_code)
            if budget is not None:
                budget.block("invalid_http_status")
            return pd.DataFrame()
        if status_code == 200:
            try:
                data = r.json()
            except Exception as exc:  # noqa: BLE001 - preserve response failure as evidence
                status = "invalid_json"
                error = repr(exc)
                if budget is not None:
                    budget.block("invalid_json_response")
                return pd.DataFrame()
            if type(data) is not list or any(type(row) is not dict for row in data):
                status = "invalid_response_schema"
                error = f"expected_list_of_objects:{type(data).__name__}"
                if budget is not None:
                    budget.block("invalid_response_schema")
                return pd.DataFrame()
            df = pd.DataFrame(data)
            rows = len(df)
            status = "pass" if rows > 0 else "zero_rows"
            return df
        else:
            status = f"http_{status_code}"
            error = r.text[:500]
            if budget is not None:
                if status_code in {401, 403}:
                    budget.block(f"access_restricted_http_{status_code}")
                elif status_code == 429:
                    budget.block("provider_rate_limited_http_429")
                elif status_code >= 500:
                    budget.block(f"provider_unavailable_http_{status_code}")
            return pd.DataFrame()
    except NormalCollectionDeferred as exc:
        status = f"deferred_{exc}"
        error = "provider request not sent by bounded NORMAL collection policy"
        return pd.DataFrame()
    except Exception as exc:  # noqa: BLE001 - diagnostic script should never crash a full run for one lane
        status = "exception"
        error = repr(exc)
        if budget is not None:
            budget.block("transport_exception")
        return pd.DataFrame()
    finally:
        request_log.append({
            "timestamp_utc": iso_now(),
            "endpoint": endpoint,
            "strategy": strategy,
            "params_json": json.dumps(clean_params, sort_keys=True),
            "rows": rows,
            "status": status,
            "error": error,
            "elapsed_seconds": round(time.time() - start, 3),
        })
        if budget is None:
            time.sleep(SLEEP_SECONDS)


def load_policy() -> Dict[str, Any]:
    if POLICY_PATH.exists():
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return {}


def _canonical_positive_integer(value: Any) -> Optional[str]:
    """Return one canonical positive integer spelling or fail closed."""
    if isinstance(value, bool):
        return None
    if isinstance(value, numbers.Integral):
        text = str(int(value))
    elif type(value) is str:
        text = value
    else:
        return None
    return text if re.fullmatch(r"[1-9][0-9]*", text) else None


def _normal_utc(value: Any) -> Optional[dt.datetime]:
    if type(value) is not str or not value or value.strip() != value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(dt.UTC)


def _missing_optional_value(value: Any) -> bool:
    if value is None:
        return True
    if type(value) is str:
        return value == ""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def is_completed_session(row: pd.Series) -> bool:
    # Unknown end time is an incomplete schedule record, never proof of completion.
    end_ts = _normal_utc(row.get("date_end"))
    return end_ts is not None and end_ts < utc_now()


def session_kind(row: pd.Series) -> str:
    text = " ".join(str(row.get(c, "")) for c in ["session_name", "session_type"])
    return text.lower()


def is_race_like_session(row: pd.Series) -> bool:
    kind = session_kind(row)
    return any(h in kind for h in RACE_LIKE_HINTS)


def read_existing_latest(latest_root: Path) -> Dict[str, Any]:
    manifest_path = latest_root / "latest_manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def write_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _invalidate_last_request(
    request_log: List[Dict[str, Any]], status: str, error: str,
) -> None:
    if request_log:
        request_log[-1]["status"] = status
        request_log[-1]["error"] = error
        request_log[-1]["rows"] = 0


def get_sessions(
    season: int,
    completed_only: bool,
    request_log: List[Dict[str, Any]],
    budget: Optional[NormalRequestBudget] = None,
) -> pd.DataFrame:
    sessions = openf1_get(
        "sessions", {"year": season}, request_log, "sessions_by_year", budget
    )
    if sessions.empty:
        return sessions
    required = {
        "session_key", "meeting_key", "year", "country_name", "location",
        "circuit_short_name", "session_name", "session_type", "date_start",
    }
    missing = sorted(required - set(sessions.columns))
    if missing:
        _invalidate_last_request(
            request_log,
            "invalid_sessions_schema",
            "missing_columns:" + ",".join(missing),
        )
        return pd.DataFrame()
    seen_session_keys: set[str] = set()
    canonical_session_keys: List[int] = []
    canonical_meeting_keys: List[int] = []
    canonical_years: List[int] = []
    invalid_reason = ""
    required_text_fields = (
        "country_name", "location", "circuit_short_name", "session_name",
        "session_type",
    )
    for position, (_, row) in enumerate(sessions.iterrows()):
        session_key = _canonical_positive_integer(row.get("session_key"))
        meeting_key = _canonical_positive_integer(row.get("meeting_key"))
        row_year = _canonical_positive_integer(row.get("year"))
        if session_key is None:
            invalid_reason = f"invalid_session_key:row={position}"
            break
        if session_key in seen_session_keys:
            invalid_reason = (
                f"duplicate_session_key:row={position}:session_key={session_key}"
            )
            break
        if meeting_key is None:
            invalid_reason = f"invalid_meeting_key:row={position}"
            break
        if row_year != str(season):
            invalid_reason = (
                f"wrong_season:row={position}:expected={season}:observed="
                f"{row_year or 'invalid'}"
            )
            break
        if any(
            type(row.get(field)) is not str
            or not row.get(field)
            or row.get(field).strip() != row.get(field)
            for field in required_text_fields
        ):
            invalid_reason = f"invalid_session_text_identity:row={position}"
            break
        start = _normal_utc(row.get("date_start"))
        if start is None:
            invalid_reason = f"invalid_session_start:row={position}"
            break
        end_value = row.get("date_end")
        if _missing_optional_value(end_value):
            end = None
        else:
            end = _normal_utc(end_value)
            if end is None:
                invalid_reason = f"invalid_session_end:row={position}"
                break
        if end is not None and end <= start:
            invalid_reason = f"invalid_session_chronology:row={position}"
            break
        seen_session_keys.add(session_key)
        canonical_session_keys.append(int(session_key))
        canonical_meeting_keys.append(int(meeting_key))
        canonical_years.append(int(row_year))
    if invalid_reason:
        _invalidate_last_request(
            request_log,
            "invalid_sessions_schema",
            invalid_reason,
        )
        return pd.DataFrame()
    sessions = sessions.copy()
    sessions["session_key"] = canonical_session_keys
    sessions["meeting_key"] = canonical_meeting_keys
    sessions["year"] = canonical_years
    sessions["_completed_session"] = sessions.apply(is_completed_session, axis=1)
    if completed_only:
        sessions = sessions[sessions["_completed_session"]].copy()
    return sessions.sort_values([c for c in ["date_start", "meeting_key", "session_key"] if c in sessions.columns])


def collect_observed_driver_numbers(
    outputs_by_lane: Dict[str, List[pd.DataFrame]],
    session_key: Any = None,
) -> List[int]:
    nums: set[int] = set()
    for lane, frames in outputs_by_lane.items():
        for df in frames:
            if df is None or df.empty:
                continue
            scoped = df
            if session_key is not None:
                if "session_key" not in df.columns:
                    continue
                scoped = df[df["session_key"].astype(str) == str(session_key)]
            for col in ["driver_number", "driverNumber"]:
                if col in scoped.columns:
                    vals = pd.to_numeric(
                        scoped[col], errors="coerce"
                    ).dropna().astype(int).tolist()
                    nums.update(vals)
    return sorted(nums)


def retrieve_lane_for_session(
    lane: str,
    sess: pd.Series,
    request_log: List[Dict[str, Any]],
    outputs_by_lane: Dict[str, List[pd.DataFrame]],
    budget: Optional[NormalRequestBudget] = None,
) -> pd.DataFrame:
    session_key = sess.get("session_key")
    meeting_key = sess.get("meeting_key")

    if lane == "pit" and not is_race_like_session(sess):
        request_log.append({
            "timestamp_utc": iso_now(),
            "endpoint": lane,
            "strategy": "skip_non_race_like_session",
            "params_json": json.dumps({"session_key": session_key}),
            "rows": 0,
            "status": "skipped_not_applicable",
            "error": "pit endpoint is only treated as required for race/sprint-like sessions",
            "elapsed_seconds": 0,
        })
        return pd.DataFrame()

    if lane == "position":
        # First try session_key. If zero, retry by meeting_key because OpenF1 position examples commonly use meeting_key.
        df = openf1_get(
            "position", {"session_key": session_key}, request_log,
            "position_by_session_key", budget,
        )
        if (
            df.empty
            and meeting_key is not None
            and (
                budget is None
                or budget.block_reason is None
                or budget.permit_endpoint_fallback()
            )
        ):
            df = openf1_get(
                "position", {"meeting_key": meeting_key}, request_log,
                "position_by_meeting_key_fallback", budget,
            )
            if not df.empty and "session_key" in df.columns:
                df = df[df["session_key"].astype(str) == str(session_key)].copy()
        return df

    if lane == "drivers":
        df = openf1_get(
            "drivers", {"session_key": session_key}, request_log,
            "drivers_by_session_key", budget,
        )
        if not df.empty:
            return df
        if budget is not None and budget.block_reason is not None:
            if not budget.permit_endpoint_fallback():
                return pd.DataFrame()
        # Fallback: use already observed driver numbers from successful lanes.
        nums = collect_observed_driver_numbers(outputs_by_lane, session_key)
        frames = []
        for n in nums:
            part = openf1_get(
                "drivers", {"session_key": session_key, "driver_number": n},
                request_log, "drivers_by_observed_driver_number", budget,
            )
            if not part.empty:
                frames.append(part)
            if budget is not None and budget.block_reason is not None:
                break
        return pd.concat(frames, ignore_index=True).drop_duplicates() if frames else pd.DataFrame()

    if lane == "team_radio":
        return openf1_get(
            "team_radio", {"session_key": session_key}, request_log,
            "team_radio_by_session_key_opportunistic", budget,
        )

    return openf1_get(
        lane, {"session_key": session_key}, request_log,
        f"{lane}_by_session_key", budget,
    )


def _frame_matches_session(df: pd.DataFrame, sess: pd.Series) -> bool:
    if df.empty or not {"session_key", "meeting_key"}.issubset(df.columns):
        return False
    expected_session = _canonical_positive_integer(sess.get("session_key"))
    expected_meeting = _canonical_positive_integer(sess.get("meeting_key"))
    if expected_session is None or expected_meeting is None:
        return False
    return all(
        _canonical_positive_integer(session_key) == expected_session
        and _canonical_positive_integer(meeting_key) == expected_meeting
        for session_key, meeting_key in zip(
            df["session_key"].tolist(),
            df["meeting_key"].tolist(),
        )
    )


def _fallback_proves_coverage(
    lane: str,
    df: pd.DataFrame,
    sess: pd.Series,
    request_entries: List[Dict[str, Any]],
) -> bool:
    if not _frame_matches_session(df, sess):
        return False
    if lane == "position":
        fallback = [
            entry for entry in request_entries
            if entry.get("strategy") == "position_by_meeting_key_fallback"
        ]
        return len(fallback) == 1 and fallback[0].get("status") == "pass"
    if lane == "drivers":
        fallback = [
            entry for entry in request_entries
            if entry.get("strategy") == "drivers_by_observed_driver_number"
        ]
        if not fallback or any(entry.get("status") != "pass" for entry in fallback):
            return False
        expected: set[int] = set()
        for entry in fallback:
            try:
                params = json.loads(str(entry.get("params_json") or "{}"))
                expected.add(int(params["driver_number"]))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                return False
        if "driver_number" not in df.columns:
            return False
        observed = set(
            pd.to_numeric(df["driver_number"], errors="coerce")
            .dropna().astype(int).tolist()
        )
        return bool(expected) and observed == expected
    return False


def _lane_requires_rows(lane: str, sess: pd.Series) -> bool:
    if lane in ROW_REQUIRED_LANES:
        return True
    if lane in {"pit", "starting_grid", "stints"}:
        return is_race_like_session(sess)
    return False


def assess_session_lane(
    lane: str,
    sess: pd.Series,
    df: pd.DataFrame,
    request_entries: List[Dict[str, Any]],
    applicable: bool,
) -> Tuple[str, str, bool]:
    """Return a per-session verdict without inferring completeness from lane totals."""
    statuses = _request_statuses(request_entries)
    if not applicable:
        return "skipped_not_applicable", "endpoint_not_applicable", False

    identity_complete = _frame_matches_session(df, sess) if not df.empty else False
    fallback_recovered = _fallback_proves_coverage(
        lane, df, sess, request_entries
    )
    unresolved_material = any(
        _material_request_failure(status) for status in statuses
    ) and not fallback_recovered

    if lane == "team_radio":
        if unresolved_material:
            return (
                "pass_with_warnings",
                "opportunistic_provider_failure:" + ",".join(statuses),
                fallback_recovered,
            )
        if df.empty:
            return (
                "pass_with_warnings",
                "opportunistic_source_limited_zero_rows",
                fallback_recovered,
            )
        if not identity_complete:
            return "pass_with_warnings", "opportunistic_identity_unproven", False
        return "pass", "evidence_bearing", fallback_recovered

    if unresolved_material:
        return (
            "fail",
            "unresolved_provider_failure:" + ",".join(statuses),
            fallback_recovered,
        )
    if not df.empty and not identity_complete:
        return "fail", "session_identity_unproven", fallback_recovered
    if fallback_recovered:
        return "pass", "endpoint_fallback_recovered_complete", True
    if df.empty and _lane_requires_rows(lane, sess):
        if "http_404" in statuses:
            return "fail", "required_session_http_404", False
        return "fail", "required_session_zero_rows", False
    if df.empty:
        return (
            "pass_with_warnings",
            "endpoint_semantic_absence_or_zero_rows",
            False,
        )
    return "pass", "evidence_bearing", False


def classify_lane(
    lane: str,
    rows: int,
    attempted_sessions: int,
    applicable_sessions: int,
    session_rows: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, str]:
    if session_rows is not None:
        failures = [row for row in session_rows if row.get("status") == "fail"]
        warnings = [
            row for row in session_rows
            if row.get("status") == "pass_with_warnings"
        ]
        if failures:
            return "fail", f"session_coverage_incomplete:{len(failures)}"
        if warnings:
            return (
                "pass_with_warnings",
                f"session_coverage_warnings:{len(warnings)}",
            )
    if rows > 0:
        return "pass", "evidence_bearing"
    if lane == "team_radio":
        return "pass_with_warnings", "opportunistic_source_limited_zero_rows"
    if applicable_sessions == 0:
        return "pass_with_warnings", "not_applicable_for_current_completed_sessions"
    return "pass_with_warnings", "zero_rows_after_endpoint_specific_retry_needs_review"


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_sha(payload: bytes) -> str:
    return hashlib.sha1(  # noqa: S324 - Git object identity, not security use
        b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    ).hexdigest()


def _read_csv_frame(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _frame_for_session(frame: pd.DataFrame, session_key: Any) -> pd.DataFrame:
    expected = _canonical_positive_integer(session_key)
    if expected is None or frame.empty or "session_key" not in frame.columns:
        return frame.iloc[0:0].copy()
    selected = [
        _canonical_positive_integer(value) == expected
        for value in frame["session_key"].tolist()
    ]
    return frame.loc[selected].copy()


def _index_frames_by_session(
    frames: Dict[str, pd.DataFrame],
) -> Dict[str, Dict[str, pd.DataFrame]]:
    indexed: Dict[str, Dict[str, pd.DataFrame]] = {}
    for lane, frame in frames.items():
        lane_index: Dict[str, pd.DataFrame] = {}
        if not frame.empty and "session_key" in frame.columns:
            keys = [
                _canonical_positive_integer(value)
                for value in frame["session_key"].tolist()
            ]
            working = frame.copy()
            working["_normal_cache_session_key"] = keys
            for key, group in working.groupby(
                "_normal_cache_session_key", sort=False, dropna=True
            ):
                lane_index[str(key)] = group.drop(
                    columns=["_normal_cache_session_key"]
                ).copy()
        indexed[lane] = lane_index
    return indexed


def _frame_evidence_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _request_evidence_sha256(entries: List[Dict[str, Any]]) -> str:
    normalized = [
        {str(key): "" if value is None else str(value) for key, value in row.items()}
        for row in entries
    ]
    return hashlib.sha256(
        json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def _session_identity_payload(
    sess: pd.Series, *, completed_only: bool,
) -> Optional[Dict[str, Any]]:
    session_key = _canonical_positive_integer(sess.get("session_key"))
    meeting_key = _canonical_positive_integer(sess.get("meeting_key"))
    year = _canonical_positive_integer(sess.get("year"))
    start = _normal_utc(sess.get("date_start"))
    end = _normal_utc(sess.get("date_end"))
    if None in {session_key, meeting_key, year, start, end}:
        return None
    payload: Dict[str, Any] = {
        "completed_only": completed_only,
        "session_key": session_key,
        "meeting_key": meeting_key,
        "year": year,
        "date_start": _format_utc(start),
        "date_end": _format_utc(end),
    }
    for field in NORMAL_SESSION_IDENTITY_FIELDS:
        if field in payload:
            continue
        value = sess.get(field)
        if type(value) is not str or not value or value.strip() != value:
            return None
        payload[field] = value
    return payload


def _session_identity_sha256(
    sess: pd.Series, *, completed_only: bool,
) -> Optional[str]:
    payload = _session_identity_payload(sess, completed_only=completed_only)
    if payload is None:
        return None
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _first_observed_utc(
    entries: List[Dict[str, Any]], frame: pd.DataFrame,
) -> Optional[str]:
    observed: List[dt.datetime] = []
    for row in entries:
        value = _normal_utc(row.get("timestamp_utc"))
        if value is not None:
            observed.append(value)
    if "source_closure_retrieved_utc" in frame.columns:
        for raw in frame["source_closure_retrieved_utc"].tolist():
            value = _normal_utc(raw)
            if value is not None:
                observed.append(value)
    return _format_utc(min(observed)) if observed else None


def _snapshot_identity(root: Path, names: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for name in names:
        path = root / name
        payload = path.read_bytes()
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(str(len(payload)).encode("ascii") + b"\0")
        digest.update(hashlib.sha256(payload).digest())
    return digest.hexdigest()


def _normal_snapshot_evidence_files() -> Tuple[str, ...]:
    return (
        "data/target_sessions.csv",
        "zero_lane_diagnostics.csv",
        "request_log.csv",
        "combined_source_manifest.csv",
        *(f"data/openf1_{lane}.csv" for lane in LANES),
    )


def _validated_snapshot_frames(
    root: Path, *, season: int, completed_only: bool,
) -> Tuple[Dict[str, Any], pd.DataFrame, Dict[str, pd.DataFrame]]:
    manifest = json.loads((root / "latest_manifest.json").read_text(encoding="utf-8"))
    if (
        type(manifest) is not dict
        or _canonical_positive_integer(manifest.get("season")) != str(season)
        or manifest.get("completed_only") is not completed_only
    ):
        raise ValueError("cache_policy_mismatch")
    sessions = _read_csv_frame(root / "data/target_sessions.csv")
    if int(manifest.get("target_session_count", -1)) != len(sessions):
        raise ValueError("cache_target_count_mismatch")
    if "session_key" not in sessions.columns:
        raise ValueError("cache_target_identity_missing")
    target_keys = {
        key for value in sessions["session_key"].tolist()
        if (key := _canonical_positive_integer(value)) is not None
    }
    if len(target_keys) != len(sessions):
        raise ValueError("cache_target_identity_invalid")

    source_manifest = _read_csv_frame(root / "combined_source_manifest.csv")
    if len(source_manifest) != len(LANES) or "lane" not in source_manifest.columns:
        raise ValueError("cache_source_manifest_invalid")
    frames: Dict[str, pd.DataFrame] = {}
    for lane in LANES:
        matches = source_manifest[source_manifest["lane"].astype(str) == lane]
        if len(matches) != 1:
            raise ValueError(f"cache_source_manifest_lane_invalid:{lane}")
        row = matches.iloc[0]
        expected_path = f"data/openf1_{lane}.csv"
        path = root / expected_path
        if str(row.get("path")) != expected_path or str(row.get("sha256")) != _sha256_path(path):
            raise ValueError(f"cache_source_hash_mismatch:{lane}")
        frame = _read_csv_frame(path)
        try:
            declared_rows = int(row.get("rows"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"cache_source_rows_invalid:{lane}") from exc
        if declared_rows != len(frame):
            raise ValueError(f"cache_source_rows_mismatch:{lane}")
        if not frame.empty:
            if not {"session_key", "meeting_key", "source_closure_retrieved_utc"}.issubset(frame.columns):
                raise ValueError(f"cache_source_identity_missing:{lane}")
            row_keys = {
                key for value in frame["session_key"].tolist()
                if (key := _canonical_positive_integer(value)) is not None
            }
            if len(row_keys) == 0 or not row_keys.issubset(target_keys):
                raise ValueError(f"cache_source_identity_invalid:{lane}")
        frames[lane] = frame
    return manifest, sessions, frames


def _entry_params(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(str(entry.get("params_json") or "{}"))
    except json.JSONDecodeError:
        return None
    return value if type(value) is dict else None


def _entry_matches_session(
    entry: Dict[str, Any], sess: pd.Series, *, allow_meeting_only: bool = False,
) -> bool:
    params = _entry_params(entry)
    if params is None:
        return False
    expected_session = _canonical_positive_integer(sess.get("session_key"))
    expected_meeting = _canonical_positive_integer(sess.get("meeting_key"))
    observed_session = _canonical_positive_integer(params.get("session_key"))
    observed_meeting = _canonical_positive_integer(params.get("meeting_key"))
    if observed_session is not None:
        return observed_session == expected_session
    return allow_meeting_only and observed_meeting == expected_meeting


def _legacy_request_slice(
    records: List[Dict[str, Any]],
    start: int,
    lane: str,
    sess: pd.Series,
) -> Tuple[List[Dict[str, Any]], int]:
    if start >= len(records):
        raise ValueError("legacy_request_log_truncated")
    first = records[start]
    if str(first.get("endpoint")) != lane:
        raise ValueError(f"legacy_request_endpoint_mismatch:{lane}")
    index = start + 1
    strategy = str(first.get("strategy"))
    if strategy == "skip_non_race_like_session":
        if lane != "pit" or not _entry_matches_session(first, sess):
            raise ValueError("legacy_skip_identity_mismatch")
        return records[start:index], index
    if not _entry_matches_session(first, sess):
        raise ValueError(f"legacy_request_identity_mismatch:{lane}")
    if lane == "position" and index < len(records):
        candidate = records[index]
        if str(candidate.get("strategy")) == "position_by_meeting_key_fallback":
            if str(candidate.get("endpoint")) != lane or not _entry_matches_session(
                candidate, sess, allow_meeting_only=True
            ):
                raise ValueError("legacy_position_fallback_identity_mismatch")
            index += 1
    elif lane == "drivers":
        while index < len(records):
            candidate = records[index]
            if str(candidate.get("strategy")) != "drivers_by_observed_driver_number":
                break
            if str(candidate.get("endpoint")) != lane or not _entry_matches_session(candidate, sess):
                raise ValueError("legacy_drivers_fallback_identity_mismatch")
            index += 1
    return records[start:index], index


def _load_verified_legacy_cache(
    output_root: Path, *, season: int, completed_only: bool,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    root = output_root / NORMAL_LEGACY_HISTORY_REL
    evidence: Dict[str, Any] = {
        "mode": "legacy_verified_history",
        "path": NORMAL_LEGACY_HISTORY_REL.as_posix(),
        "aggregate_pass_accepted": False,
        "verified_sessions": 0,
        "rejected_sessions": 0,
        "reason": None,
    }
    try:
        if season != 2026 or completed_only is not True:
            raise ValueError("legacy_policy_incompatible")
        if _snapshot_identity(root, NORMAL_LEGACY_SNAPSHOT_FILES) != NORMAL_LEGACY_SNAPSHOT_SHA256:
            raise ValueError("legacy_snapshot_identity_mismatch")
        request_payload = (root / "request_log.csv").read_bytes()
        if hashlib.sha256(request_payload).hexdigest() != NORMAL_LEGACY_REQUEST_LOG_SHA256:
            raise ValueError("legacy_request_log_sha256_mismatch")
        if _git_blob_sha(request_payload) != NORMAL_LEGACY_REQUEST_LOG_GIT_BLOB:
            raise ValueError("legacy_request_log_git_blob_mismatch")
        _, sessions, frames = _validated_snapshot_frames(
            root, season=season, completed_only=completed_only
        )
        indexed_frames = _index_frames_by_session(frames)
        diagnostics = _read_csv_frame(root / "zero_lane_diagnostics.csv")
        requests_frame = _read_csv_frame(root / "request_log.csv")
        records = requests_frame.to_dict("records")
        if len(records) < 1 or str(records[0].get("strategy")) != "sessions_by_year":
            raise ValueError("legacy_discovery_evidence_missing")
        if str(records[0].get("status")) != "pass":
            raise ValueError("legacy_discovery_not_available")
        if len(diagnostics) != len(sessions) * len(LANES):
            raise ValueError("legacy_diagnostics_incomplete")

        session_by_key = {
            _canonical_positive_integer(row.get("session_key")): row
            for _, row in sessions.iterrows()
        }
        cache: Dict[str, Dict[str, Any]] = {}
        working: Dict[str, Dict[str, Any]] = {}
        index = 1
        for position, (_, diagnostic) in enumerate(diagnostics.iterrows()):
            lane = str(diagnostic.get("lane"))
            expected_lane = LANES[position % len(LANES)]
            if lane != expected_lane:
                raise ValueError("legacy_diagnostic_lane_order_invalid")
            session_key = _canonical_positive_integer(diagnostic.get("session_key"))
            sess = session_by_key.get(session_key)
            if session_key is None or sess is None:
                raise ValueError("legacy_diagnostic_session_invalid")
            entries, index = _legacy_request_slice(records, index, lane, sess)
            frame = indexed_frames[lane].get(
                session_key, frames[lane].iloc[0:0].copy()
            )
            applicable = not (lane == "pit" and not is_race_like_session(sess))
            status, reason, fallback = assess_session_lane(
                lane, sess, frame, entries, applicable
            )
            first_observed = _first_observed_utc(entries, frame)
            if first_observed is None:
                raise ValueError("legacy_first_observation_missing")
            item = working.setdefault(session_key, {
                "session_identity_sha256": _session_identity_sha256(
                    sess, completed_only=completed_only
                ),
                "lanes": {},
                "source": "legacy_verified_history",
            })
            item["lanes"][lane] = {
                "frame": frame,
                "request_entries": [dict(row) for row in entries],
                "status": status,
                "reason": reason,
                "fallback_recovered": fallback,
                "first_observed_utc": first_observed,
            }
        if index != len(records):
            raise ValueError("legacy_request_log_unmapped")
        for key, item in working.items():
            lanes = item["lanes"]
            complete = (
                item["session_identity_sha256"] is not None
                and set(lanes) == set(LANES)
                and all(lane["status"] != "fail" for lane in lanes.values())
            )
            if complete:
                cache[key] = item
            else:
                evidence["rejected_sessions"] += 1
        evidence["verified_sessions"] = len(cache)
        evidence["known_target_session_keys"] = sorted(
            _canonical_positive_integer(value)
            for value in sessions["session_key"].tolist()
        )
        return cache, evidence
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        evidence["reason"] = str(exc) or type(exc).__name__
        return {}, evidence


def _load_hardened_cache(
    latest_root: Path, *, season: int, completed_only: bool,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    evidence: Dict[str, Any] = {
        "mode": "hardened_latest",
        "verified_sessions": 0,
        "reason": None,
    }
    try:
        manifest, sessions, frames = _validated_snapshot_frames(
            latest_root, season=season, completed_only=completed_only
        )
        indexed_frames = _index_frames_by_session(frames)
        normal = manifest.get("normal_collection")
        if (
            type(normal) is not dict
            or normal.get("schema_version") != NORMAL_CACHE_SCHEMA_VERSION
            or manifest.get("publication_eligible") is not True
            or manifest.get("source_quality_status") != "complete"
            or normal.get("historical_reuse_only") is not True
            or normal.get("prospective_forecast_eligibility_established") is not False
        ):
            raise ValueError("hardened_cache_contract_missing")
        expected_hashes = {
            "target_sessions_sha256": latest_root / "data/target_sessions.csv",
            "request_log_sha256": latest_root / "request_log.csv",
            "zero_lane_diagnostics_sha256": latest_root / "zero_lane_diagnostics.csv",
            "combined_source_manifest_sha256": latest_root / "combined_source_manifest.csv",
        }
        for field, path in expected_hashes.items():
            if normal.get(field) != _sha256_path(path):
                raise ValueError(f"hardened_cache_hash_mismatch:{field}")
        if normal.get("snapshot_evidence_sha256") != _snapshot_identity(
            latest_root, _normal_snapshot_evidence_files()
        ):
            raise ValueError("hardened_cache_snapshot_identity_mismatch")

        diagnostics = _read_csv_frame(latest_root / "zero_lane_diagnostics.csv")
        requests_frame = _read_csv_frame(latest_root / "request_log.csv")
        request_records = requests_frame.to_dict("records")
        required = {
            "lane", "session_key", "applicable", "status", "reason", "rows",
            "request_start_index", "request_count", "request_evidence_sha256",
            "frame_evidence_sha256", "session_identity_sha256",
            "first_observed_utc", "fallback_recovered",
        }
        if not required.issubset(diagnostics.columns):
            raise ValueError("hardened_cache_diagnostics_contract_missing")
        if len(diagnostics) != len(sessions) * len(LANES):
            raise ValueError("hardened_cache_diagnostics_incomplete")
        generated = _normal_utc(manifest.get("generated_utc"))
        if generated is None:
            raise ValueError("hardened_cache_generated_utc_invalid")
        session_by_key = {
            _canonical_positive_integer(row.get("session_key")): row
            for _, row in sessions.iterrows()
        }
        cache: Dict[str, Dict[str, Any]] = {}
        seen: set[Tuple[str, str]] = set()
        for _, diagnostic in diagnostics.iterrows():
            session_key = _canonical_positive_integer(diagnostic.get("session_key"))
            lane = str(diagnostic.get("lane"))
            sess = session_by_key.get(session_key)
            if session_key is None or sess is None or lane not in LANES:
                raise ValueError("hardened_cache_diagnostic_identity_invalid")
            pair = (session_key, lane)
            if pair in seen:
                raise ValueError("hardened_cache_diagnostic_duplicate")
            seen.add(pair)
            try:
                start = int(diagnostic.get("request_start_index"))
                count = int(diagnostic.get("request_count"))
            except (TypeError, ValueError) as exc:
                raise ValueError("hardened_cache_request_pointer_invalid") from exc
            if start < 0 or count < 1 or start + count > len(request_records):
                raise ValueError("hardened_cache_request_pointer_invalid")
            entries = request_records[start:start + count]
            if _request_evidence_sha256(entries) != str(diagnostic.get("request_evidence_sha256")):
                raise ValueError("hardened_cache_request_evidence_mismatch")
            frame = indexed_frames[lane].get(
                session_key, frames[lane].iloc[0:0].copy()
            )
            if _frame_evidence_sha256(frame) != str(diagnostic.get("frame_evidence_sha256")):
                raise ValueError("hardened_cache_frame_evidence_mismatch")
            identity_sha = _session_identity_sha256(
                sess, completed_only=completed_only
            )
            if identity_sha != str(diagnostic.get("session_identity_sha256")):
                raise ValueError("hardened_cache_session_identity_mismatch")
            applicable = str(diagnostic.get("applicable")) == "True"
            status, reason, fallback = assess_session_lane(
                lane, sess, frame, entries, applicable
            )
            if (
                status != str(diagnostic.get("status"))
                or reason != str(diagnostic.get("reason"))
                or fallback != (str(diagnostic.get("fallback_recovered")) == "True")
                or len(frame) != int(diagnostic.get("rows"))
            ):
                raise ValueError("hardened_cache_quality_replay_mismatch")
            first_observed = _normal_utc(diagnostic.get("first_observed_utc"))
            if first_observed is None or first_observed > generated:
                raise ValueError("hardened_cache_observation_time_invalid")
            item = cache.setdefault(session_key, {
                "session_identity_sha256": identity_sha,
                "lanes": {},
                "source": "hardened_latest",
            })
            item["lanes"][lane] = {
                "frame": frame,
                "request_entries": [dict(row) for row in entries],
                "status": status,
                "reason": reason,
                "fallback_recovered": fallback,
                "first_observed_utc": _format_utc(first_observed),
            }
        if any(
            set(item["lanes"]) != set(LANES)
            or any(lane["status"] == "fail" for lane in item["lanes"].values())
            for item in cache.values()
        ):
            raise ValueError("hardened_cache_session_incomplete")
        evidence["verified_sessions"] = len(cache)
        evidence["known_target_session_keys"] = sorted(cache)
        return cache, evidence
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        evidence["reason"] = str(exc) or type(exc).__name__
        return {}, evidence


def create_zip(folder: Path, zip_path: Path) -> str:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob("*"):
            if p.is_file() and p != zip_path:
                z.write(p, p.relative_to(folder))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (zip_path.with_suffix(zip_path.suffix + ".sha256.txt")).write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--completed-only", default="true")
    parser.add_argument("--output-root", default=".")
    parser.add_argument("--provenance-shadow-session-key", default="")
    parser.add_argument("--provenance-shadow-endpoint", default=SHADOW_ENDPOINT)
    parser.add_argument("--github-repository", default="")
    parser.add_argument("--github-workflow", default="")
    parser.add_argument("--github-workflow-ref", default="")
    parser.add_argument("--github-ref", default="")
    parser.add_argument("--github-sha", default="")
    parser.add_argument("--github-run-id", default="")
    parser.add_argument("--github-run-attempt", default="")
    args = parser.parse_args()

    season = int(args.season)
    completed_only = str(args.completed_only).lower() not in {"false", "0", "no"}
    output_root = Path(args.output_root).resolve()
    try:
        selected_shadow_endpoint = _selected_shadow_endpoint(
            args.provenance_shadow_endpoint
        )
        if selected_shadow_endpoint == "drivers":
            _shadow_require(
                bool(args.provenance_shadow_session_key),
                "drivers_shadow_requires_explicit_session_key",
            )
        elif selected_shadow_endpoint == "starting_grid":
            _shadow_require(
                bool(args.provenance_shadow_session_key),
                "starting_grid_shadow_requires_explicit_session_key",
            )
    except ProvenanceShadowHold as exc:
        print(f"OpenF1 historical REST provenance shadow HOLD: {exc}", file=sys.stderr)
        return 1
    if args.provenance_shadow_session_key:
        try:
            result = run_provenance_shadow(
                session_key=args.provenance_shadow_session_key,
                season=season,
                output_root=output_root,
                repository=args.github_repository,
                workflow=args.github_workflow,
                workflow_ref=args.github_workflow_ref,
                ref=args.github_ref,
                head_sha=args.github_sha,
                run_id=args.github_run_id,
                run_attempt=args.github_run_attempt,
                endpoint=selected_shadow_endpoint,
            )
        except ProvenanceShadowHold as exc:
            print(f"OpenF1 historical REST provenance shadow HOLD: {exc}", file=sys.stderr)
            return 1
        print("OpenF1 historical REST provenance shadow validated.")
        print(json.dumps(result, sort_keys=True))
        return 0

    policy = load_policy()
    latest_root = output_root / "latest" / "openf1_lightweight_source_closure"
    history_root = (
        output_root / "history" / "openf1_lightweight_source_closure"
        / utc_now().strftime("%Y%m%d_%H%M%S")
    )
    data_latest = latest_root / "data"
    data_history = history_root / "data"
    previous_manifest = read_existing_latest(latest_root)
    hardened_cache, hardened_cache_evidence = _load_hardened_cache(
        latest_root, season=season, completed_only=completed_only
    )
    if hardened_cache:
        session_cache = hardened_cache
        cache_evidence = hardened_cache_evidence
    else:
        legacy_cache, legacy_cache_evidence = _load_verified_legacy_cache(
            output_root, season=season, completed_only=completed_only
        )
        session_cache = legacy_cache
        cache_evidence = legacy_cache_evidence
        cache_evidence["hardened_cache_rejection_reason"] = (
            hardened_cache_evidence.get("reason")
        )

    latest_root.mkdir(parents=True, exist_ok=True)
    history_root.mkdir(parents=True, exist_ok=True)

    request_log: List[Dict[str, Any]] = []
    budget = NormalRequestBudget(
        requests_per_window=NORMAL_REQUESTS_PER_MINUTE,
        window_seconds=NORMAL_RATE_WINDOW_SECONDS,
        max_requests=NORMAL_MAX_RUN_REQUESTS,
        max_elapsed_seconds=NORMAL_MAX_COLLECTION_SECONDS,
        clock=time.monotonic,
        sleeper=time.sleep,
    )
    previous_manifest_season = _canonical_positive_integer(
        previous_manifest.get("season")
    )
    previous_manifest_completed_only = previous_manifest.get("completed_only")
    previous_coverage_compatible = (
        previous_manifest_season == str(season)
        and type(previous_manifest_completed_only) is bool
        and previous_manifest_completed_only is completed_only
    )
    previous_target_keys: set[str] = set()
    previous_target_path = data_latest / "target_sessions.csv"
    if previous_coverage_compatible and previous_target_path.exists():
        try:
            previous_targets = pd.read_csv(previous_target_path)
            if "session_key" in previous_targets.columns:
                previous_target_keys = set(
                    key for value in previous_targets["session_key"].tolist()
                    if (key := _canonical_positive_integer(value)) is not None
                )
        except Exception:
            previous_target_keys = set()

    sessions = get_sessions(season, completed_only, request_log, budget)
    discovery_status = (
        str(request_log[0].get("status") or "unknown")
        if request_log else "not_observed"
    )
    source_quality_reasons: List[str] = []
    if discovery_status not in {"pass", "zero_rows", "not_observed"}:
        source_quality_reasons.append(_availability_reason(
            "session_discovery", discovery_status
        ))
    current_target_keys = (
        set(
            key for value in sessions["session_key"].tolist()
            if (key := _canonical_positive_integer(value)) is not None
        )
        if "session_key" in sessions.columns else set()
    )
    known_cache_target_keys = set(
        cache_evidence.get("known_target_session_keys") or []
    )
    missing_cache_targets = sorted(known_cache_target_keys - current_target_keys)
    if missing_cache_targets:
        source_quality_reasons.append(
            "verified_cache_session_coverage_regression:"
            + ",".join(missing_cache_targets[:20])
        )
    if previous_coverage_compatible:
        missing_previous = sorted(previous_target_keys - current_target_keys)
        if missing_previous:
            source_quality_reasons.append(
                "completed_session_coverage_regression:"
                + ",".join(missing_previous[:20])
            )
    try:
        previous_count = int(previous_manifest.get("target_session_count") or 0)
    except (TypeError, ValueError):
        previous_count = 0
    if (
        previous_coverage_compatible
        and previous_count > 0
        and len(sessions) < previous_count
    ):
        source_quality_reasons.append(
            f"completed_session_count_regression:{previous_count}->{len(sessions)}"
        )
    write_df(sessions, data_latest / "target_sessions.csv")
    write_df(sessions, data_history / "target_sessions.csv")

    outputs_by_lane: Dict[str, List[pd.DataFrame]] = {lane: [] for lane in LANES}
    lane_session_rows: List[Dict[str, Any]] = []
    reused_session_keys: set[str] = set()
    fresh_session_keys: set[str] = set()
    avoided_request_count = 0

    for _, sess in sessions.iterrows():
        session_key = _canonical_positive_integer(sess.get("session_key"))
        current_identity = _session_identity_sha256(
            sess, completed_only=completed_only
        )
        cached = session_cache.get(session_key or "")
        reuse_session = bool(
            cached
            and current_identity is not None
            and cached.get("session_identity_sha256") == current_identity
            and set(cached.get("lanes", {})) == set(LANES)
        )
        if reuse_session:
            reused_session_keys.add(session_key or "")
        else:
            fresh_session_keys.add(session_key or "invalid")
        for lane in LANES:
            applicable = not (lane == "pit" and not is_race_like_session(sess))
            request_start = len(request_log)
            cache_source = "fresh_provider"
            cached_lane = cached.get("lanes", {}).get(lane) if reuse_session else None
            if cached_lane is not None:
                df = cached_lane["frame"].copy()
                copied_entries = [
                    dict(entry) for entry in cached_lane["request_entries"]
                ]
                request_log.extend(copied_entries)
                if any(
                    str(entry.get("strategy")) != "skip_non_race_like_session"
                    for entry in copied_entries
                ):
                    avoided_request_count += 1
                cache_source = str(cached.get("source") or "verified_cache")
                first_observed = cached_lane.get("first_observed_utc")
            else:
                df = retrieve_lane_for_session(
                    lane, sess, request_log, outputs_by_lane, budget
                )
                first_observed = None
            request_entries = request_log[request_start:]
            session_result, session_reason, fallback_recovered = assess_session_lane(
                lane, sess, df, request_entries, applicable
            )
            if not df.empty:
                df = df.copy()
                if cache_source == "fresh_provider":
                    df["source_closure_retrieved_utc"] = iso_now()
                outputs_by_lane[lane].append(df)
            if first_observed is None:
                first_observed = _first_observed_utc(request_entries, df)
            lane_session_rows.append({
                "lane": lane,
                "meeting_key": sess.get("meeting_key"),
                "session_key": sess.get("session_key"),
                "session_name": sess.get("session_name"),
                "session_type": sess.get("session_type"),
                "applicable": applicable,
                "rows": int(len(df)),
                "status": session_result,
                "reason": session_reason,
                "request_count": len(request_entries),
                "request_statuses": ",".join(_request_statuses(request_entries)),
                "fallback_recovered": fallback_recovered,
                "request_start_index": request_start,
                "session_identity_sha256": current_identity or "",
                "first_observed_utc": first_observed or "",
                "cache_source": cache_source,
                "request_evidence_sha256": "",
                "frame_evidence_sha256": "",
            })

    source_manifest_rows = []
    readiness_rows = []
    combined_frames: Dict[str, pd.DataFrame] = {}
    for lane, frames in outputs_by_lane.items():
        if frames:
            combined = pd.concat(frames, ignore_index=True).drop_duplicates()
        else:
            combined = pd.DataFrame()
        # Write combined lane output.
        lane_file = f"openf1_{lane}.csv"
        write_df(combined, data_latest / lane_file)
        write_df(combined, data_history / lane_file)
        combined_frames[lane] = _read_csv_frame(data_latest / lane_file)
        rows = int(len(combined))
        lane_rows = [row for row in lane_session_rows if row["lane"] == lane]
        attempted_sessions = len(lane_rows)
        applicable_sessions = sum(bool(row["applicable"]) for row in lane_rows)
        result, reason = classify_lane(
            lane, rows, attempted_sessions, applicable_sessions, lane_rows
        )
        readiness_rows.append({
            "lane": lane,
            "rows": rows,
            "result": result,
            "reason": reason,
            "required_status": "opportunistic" if lane == "team_radio" else "required_lightweight",
            "heavy_endpoint": False,
        })
        source_manifest_rows.append({
            "path": f"data/{lane_file}",
            "lane": lane,
            "rows": rows,
            "sha256": hashlib.sha256((data_latest / lane_file).read_bytes()).hexdigest() if (data_latest / lane_file).exists() else "",
            "result": result,
            "reason": reason,
        })

    request_df = pd.DataFrame(request_log)
    readiness_df = pd.DataFrame(readiness_rows)
    source_manifest_df = pd.DataFrame(source_manifest_rows)

    write_df(request_df, latest_root / "request_log.csv")
    write_df(request_df, history_root / "request_log.csv")
    persisted_requests = _read_csv_frame(
        latest_root / "request_log.csv"
    ).to_dict("records")
    combined_frame_index = _index_frames_by_session(combined_frames)
    for row in lane_session_rows:
        start = int(row["request_start_index"])
        count = int(row["request_count"])
        entries = persisted_requests[start:start + count]
        frame = combined_frame_index[row["lane"]].get(
            _canonical_positive_integer(row["session_key"]) or "",
            combined_frames[row["lane"]].iloc[0:0].copy(),
        )
        row["request_evidence_sha256"] = _request_evidence_sha256(entries)
        row["frame_evidence_sha256"] = _frame_evidence_sha256(frame)
    lane_session_df = pd.DataFrame(lane_session_rows)
    write_df(lane_session_df, latest_root / "zero_lane_diagnostics.csv")
    write_df(lane_session_df, history_root / "zero_lane_diagnostics.csv")
    write_df(readiness_df, latest_root / "source_readiness_summary.csv")
    write_df(readiness_df, history_root / "source_readiness_summary.csv")
    write_df(source_manifest_df, latest_root / "combined_source_manifest.csv")
    write_df(source_manifest_df, history_root / "combined_source_manifest.csv")

    # Optional workbook summary for non-coders.
    xlsx_path = latest_root / "F1_OpenF1_Lightweight_Source_Closure_Summary.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        readiness_df.to_excel(writer, sheet_name="Source Readiness", index=False)
        lane_session_df.to_excel(writer, sheet_name="Zero Lane Diagnostics", index=False)
        source_manifest_df.to_excel(writer, sheet_name="Manifest", index=False)
        sessions.to_excel(writer, sheet_name="Target Sessions", index=False)

    # Copy workbook to history too.
    history_xlsx = history_root / xlsx_path.name
    history_xlsx.write_bytes(xlsx_path.read_bytes())

    pass_count = int((readiness_df["result"] == "pass").sum()) if not readiness_df.empty else 0
    warning_count = int((readiness_df["result"] == "pass_with_warnings").sum()) if not readiness_df.empty else 0
    fail_count = int((readiness_df["result"] == "fail").sum()) if not readiness_df.empty else 0
    if fail_count:
        source_quality_reasons.append(
            f"required_lane_session_failures:{fail_count}"
        )
    source_quality_reasons = list(dict.fromkeys(source_quality_reasons))
    publication_eligible = not source_quality_reasons
    source_quality_status = (
        "complete_empty"
        if publication_eligible and len(sessions) == 0
        else ("complete" if publication_eligible else "hold")
    )
    generated_utc = iso_now()
    snapshot_files = _normal_snapshot_evidence_files()
    normal_collection = {
        "schema_version": NORMAL_CACHE_SCHEMA_VERSION,
        "historical_reuse_only": True,
        "prospective_forecast_eligibility_established": False,
        "source_readiness_promoted": False,
        "dr002_activated": False,
        "stable_engine_modified": False,
        "cache_evidence": cache_evidence,
        "verified_cache_candidate_sessions": len(session_cache),
        "reused_session_count": len(reused_session_keys),
        "fresh_session_count": len(fresh_session_keys),
        "provider_requests_avoided": avoided_request_count,
        "request_budget": budget.evidence(),
        "target_sessions_sha256": _sha256_path(
            data_latest / "target_sessions.csv"
        ),
        "request_log_sha256": _sha256_path(latest_root / "request_log.csv"),
        "zero_lane_diagnostics_sha256": _sha256_path(
            latest_root / "zero_lane_diagnostics.csv"
        ),
        "combined_source_manifest_sha256": _sha256_path(
            latest_root / "combined_source_manifest.csv"
        ),
        "snapshot_evidence_sha256": _snapshot_identity(
            latest_root, snapshot_files
        ),
    }
    manifest = {
        "artifact_profile": "openf1-lightweight-source-closure",
        "generated_utc": generated_utc,
        "season": season,
        "completed_only": completed_only,
        "target_session_count": int(len(sessions)),
        "lanes": readiness_rows,
        "pass_count": pass_count,
        "pass_with_warnings_count": warning_count,
        "fail_count": fail_count,
        "publication_eligible": publication_eligible,
        "source_quality_status": source_quality_status,
        "source_quality_reasons": source_quality_reasons,
        "session_discovery_status": discovery_status,
        "session_discovery_availability": (
            "available"
            if discovery_status in {"pass", "zero_rows"}
            else _availability_reason("session_discovery", discovery_status)
        ),
        "previous_manifest_season": previous_manifest.get("season"),
        "previous_manifest_completed_only": previous_manifest_completed_only,
        "previous_coverage_compatible": previous_coverage_compatible,
        "heavy_endpoints_excluded_by_default": ["car_data", "location"],
        "timestamp_policy": "dt.datetime.now(dt.UTC)",
        "no_drs_2026_assumption": True,
        "previous_manifest_generated_utc": previous_manifest.get("generated_utc"),
        "latest_zip": "openf1_lightweight_source_closure.zip",
        "history_path": str(history_root.relative_to(output_root)),
        "normal_collection": normal_collection,
    }
    (latest_root / "latest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (history_root / "latest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    readiness_payload = {"generated_utc": generated_utc, "lanes": readiness_rows}
    (latest_root / "data_readiness.json").write_text(
        json.dumps(readiness_payload, indent=2), encoding="utf-8"
    )
    (history_root / "data_readiness.json").write_text(
        json.dumps(readiness_payload, indent=2), encoding="utf-8"
    )

    report_lines = [
        "# F1 OpenF1 Lightweight Source Closure Report",
        "",
        f"Generated UTC: {generated_utc}",
        f"Season: {season}",
        f"Target sessions: {len(sessions)}",
        "",
        "## Result",
        "",
        f"Pass lanes: {pass_count}",
        f"Pass with warnings lanes: {warning_count}",
        f"Fail lanes: {fail_count}",
        f"Publication eligible: {str(publication_eligible).lower()}",
        f"Source quality status: {source_quality_status}",
        "Source quality reasons: "
        + (", ".join(source_quality_reasons) if source_quality_reasons else "none"),
        f"Provider requests performed: {budget.total_requests}",
        f"Provider requests avoided: {avoided_request_count}",
        f"Verified sessions reused: {len(reused_session_keys)}",
        f"Fresh sessions collected: {len(fresh_session_keys)}",
        "Prospective forecast eligibility established: false",
        "",
        "## Important",
        "",
        "Heavy OpenF1 car_data and location were not pulled by this workflow.",
        "Team radio is treated as opportunistic, not mandatory.",
        "2026 race assumptions do not use DRS logic.",
    ]
    (latest_root / "source_closure_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    (history_root / "source_closure_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    zip_digest = create_zip(latest_root, latest_root / "openf1_lightweight_source_closure.zip")
    create_zip(history_root, history_root / "openf1_lightweight_source_closure.zip")

    print(
        "OpenF1 lightweight source closure complete."
        if publication_eligible
        else "OpenF1 lightweight source closure HOLD: nonpublishable source quality."
    )
    print(f"Latest output: {latest_root}")
    print(f"History output: {history_root}")
    print(f"Latest ZIP SHA256: {zip_digest}")
    print(f"Pass lanes: {pass_count}; Pass with warnings lanes: {warning_count}; Fail lanes: {fail_count}")
    return 0 if publication_eligible else 1


if __name__ == "__main__":
    raise SystemExit(main())
