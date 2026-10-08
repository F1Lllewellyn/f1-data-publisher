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

SHADOW_SCHEMA_VERSION = "dr002-pre2b7k4r2-openf1-source-closure-shadow-v1"
SHADOW_RUNTIME_DIR = "dr002_pre2b7k4r2_openf1_historical_rest_shadow"
SHADOW_WORKFLOW_NAME = "F1 OpenF1 Lightweight Source Closure"
SHADOW_WORKFLOW_PATH = ".github/workflows/f1-openf1-lightweight-source-closure.yml"
SHADOW_REPOSITORY = "F1Lllewellyn/f1-data-publisher"
SHADOW_ENDPOINT = "weather"
SHADOW_ENDPOINTS = ("weather", "drivers")
SHADOW_IMPLEMENTATION = "scripts/openf1/publish_openf1_lightweight_source_closure.py"


class ProvenanceShadowHold(RuntimeError):
    """Fail-closed K4R2 shadow result."""


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
) -> Dict[str, Any]:
    """Run one manual, main-only, exact-byte historical weather/drivers shadow."""
    selected_endpoint = _selected_shadow_endpoint(endpoint)
    selected_key = _positive_decimal(session_key, "selected_session_key_malformed")
    run_id_text = _positive_decimal(run_id, "workflow_run_id_malformed")
    run_attempt_text = _positive_decimal(run_attempt, "workflow_run_attempt_malformed")
    root = (Path(output_root).resolve() / "_runtime" / SHADOW_RUNTIME_DIR
            / f"gha-{run_id_text}-{run_attempt_text}")
    root.mkdir(parents=True, exist_ok=False)
    manifest: Dict[str, Any] = {
        "schema_version": SHADOW_SCHEMA_VERSION,
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
        discovery_response = http_get(
            discovery_uri,
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        )
        discovery_status = getattr(discovery_response, "status_code", None)
        discovery_bytes = getattr(discovery_response, "content", None)
        _shadow_require(discovery_status == 200, "session_discovery_http_status_not_200")
        sessions = _strict_json_bytes(
            discovery_bytes,
            expected_type=list,
            reason="malformed_session_discovery_response",
        )
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
        _shadow_require(
            _parse_utc(eligibility_check_utc, "shadow_clock_not_utc") >= eligibility,
            "selected_session_before_historical_window",
        )

        source_uri = f"{API_BASE}/{selected_endpoint}?session_key={selected_key}"
        source_response = http_get(
            source_uri,
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        )
        http_status = getattr(source_response, "status_code", None)
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
        manifest.update(
            canonical_request_uri=source_uri,
            raw_response_sha256=raw_sha,
            ingested_utc=ingested_utc,
            receipt_created_utc=receipt_created_utc,
        )

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
            assessment_projection = {
                **assessment_projection,
                "status": historical_rest_contract.HOLD,
                "reason_codes": assessment_projection.get("reason_codes") or [reason],
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


def openf1_get(endpoint: str, params: Dict[str, Any], request_log: List[Dict[str, Any]], strategy: str) -> pd.DataFrame:
    url = f"{API_BASE}/{endpoint}"
    clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
    start = time.time()
    status = "unknown"
    error = ""
    rows = 0
    try:
        r = requests.get(url, params=clean_params, timeout=REQUEST_TIMEOUT)
        status_code = r.status_code
        if status_code == 200:
            data = r.json()
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame([data]) if data else pd.DataFrame()
            rows = len(df)
            status = "pass" if rows > 0 else "zero_rows"
            return df
        else:
            status = f"http_{status_code}"
            error = r.text[:500]
            return pd.DataFrame()
    except Exception as exc:  # noqa: BLE001 - diagnostic script should never crash a full run for one lane
        status = "exception"
        error = repr(exc)
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
        time.sleep(SLEEP_SECONDS)


def load_policy() -> Dict[str, Any]:
    if POLICY_PATH.exists():
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return {}


def is_completed_session(row: pd.Series) -> bool:
    now = utc_now()
    for col in ("date_end", "session_end", "gmt_offset"):
        # gmt_offset is intentionally ignored; included only to document known OpenF1 columns.
        pass
    date_end = row.get("date_end")
    if not date_end or pd.isna(date_end):
        # If end is missing, use date_start as weak fallback; do not call future sessions completed.
        date_start = row.get("date_start")
        if not date_start or pd.isna(date_start):
            return False
        try:
            start_ts = pd.to_datetime(date_start, utc=True).to_pydatetime()
            return start_ts < now - dt.timedelta(hours=2)
        except Exception:
            return False
    try:
        end_ts = pd.to_datetime(date_end, utc=True).to_pydatetime()
        return end_ts < now
    except Exception:
        return False


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


def get_sessions(season: int, completed_only: bool, request_log: List[Dict[str, Any]]) -> pd.DataFrame:
    sessions = openf1_get("sessions", {"year": season}, request_log, "sessions_by_year")
    if sessions.empty:
        return sessions
    sessions["_completed_session"] = sessions.apply(is_completed_session, axis=1)
    if completed_only:
        sessions = sessions[sessions["_completed_session"]].copy()
    return sessions.sort_values([c for c in ["date_start", "meeting_key", "session_key"] if c in sessions.columns])


def collect_observed_driver_numbers(outputs_by_lane: Dict[str, List[pd.DataFrame]]) -> List[int]:
    nums: set[int] = set()
    for lane, frames in outputs_by_lane.items():
        for df in frames:
            if df is None or df.empty:
                continue
            for col in ["driver_number", "driverNumber"]:
                if col in df.columns:
                    vals = pd.to_numeric(df[col], errors="coerce").dropna().astype(int).tolist()
                    nums.update(vals)
    return sorted(nums)


def retrieve_lane_for_session(lane: str, sess: pd.Series, request_log: List[Dict[str, Any]], outputs_by_lane: Dict[str, List[pd.DataFrame]]) -> pd.DataFrame:
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
        df = openf1_get("position", {"session_key": session_key}, request_log, "position_by_session_key")
        if df.empty and meeting_key is not None:
            df = openf1_get("position", {"meeting_key": meeting_key}, request_log, "position_by_meeting_key_fallback")
            if not df.empty and "session_key" in df.columns:
                df = df[df["session_key"].astype(str) == str(session_key)].copy()
        return df

    if lane == "drivers":
        df = openf1_get("drivers", {"session_key": session_key}, request_log, "drivers_by_session_key")
        if not df.empty:
            return df
        # Fallback: use already observed driver numbers from successful lanes.
        nums = collect_observed_driver_numbers(outputs_by_lane)
        frames = []
        for n in nums:
            part = openf1_get("drivers", {"session_key": session_key, "driver_number": n}, request_log, "drivers_by_observed_driver_number")
            if not part.empty:
                frames.append(part)
        return pd.concat(frames, ignore_index=True).drop_duplicates() if frames else pd.DataFrame()

    if lane == "team_radio":
        return openf1_get("team_radio", {"session_key": session_key}, request_log, "team_radio_by_session_key_opportunistic")

    return openf1_get(lane, {"session_key": session_key}, request_log, f"{lane}_by_session_key")


def classify_lane(lane: str, rows: int, attempted_sessions: int, applicable_sessions: int) -> Tuple[str, str]:
    if rows > 0:
        return "pass", "evidence_bearing"
    if lane == "team_radio":
        return "pass_with_warnings", "opportunistic_source_limited_zero_rows"
    if applicable_sessions == 0:
        return "pass_with_warnings", "not_applicable_for_current_completed_sessions"
    return "pass_with_warnings", "zero_rows_after_endpoint_specific_retry_needs_review"


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
        _shadow_require(
            selected_shadow_endpoint == SHADOW_ENDPOINT
            or bool(args.provenance_shadow_session_key),
            "drivers_shadow_requires_explicit_session_key",
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
    history_root = output_root / "history" / "openf1_lightweight_source_closure" / utc_now().strftime("%Y%m%d_%H%M%S")
    data_latest = latest_root / "data"
    data_history = history_root / "data"
    latest_root.mkdir(parents=True, exist_ok=True)
    history_root.mkdir(parents=True, exist_ok=True)

    request_log: List[Dict[str, Any]] = []
    previous_manifest = read_existing_latest(latest_root)

    sessions = get_sessions(season, completed_only, request_log)
    write_df(sessions, data_latest / "target_sessions.csv")
    write_df(sessions, data_history / "target_sessions.csv")

    outputs_by_lane: Dict[str, List[pd.DataFrame]] = {lane: [] for lane in LANES}
    lane_session_rows: List[Dict[str, Any]] = []

    for _, sess in sessions.iterrows():
        for lane in LANES:
            applicable = not (lane == "pit" and not is_race_like_session(sess))
            df = retrieve_lane_for_session(lane, sess, request_log, outputs_by_lane)
            if not df.empty:
                df = df.copy()
                if "session_key" not in df.columns and sess.get("session_key") is not None:
                    df["session_key"] = sess.get("session_key")
                if "meeting_key" not in df.columns and sess.get("meeting_key") is not None:
                    df["meeting_key"] = sess.get("meeting_key")
                df["source_closure_retrieved_utc"] = iso_now()
                outputs_by_lane[lane].append(df)
            lane_session_rows.append({
                "lane": lane,
                "meeting_key": sess.get("meeting_key"),
                "session_key": sess.get("session_key"),
                "session_name": sess.get("session_name"),
                "session_type": sess.get("session_type"),
                "applicable": applicable,
                "rows": int(len(df)),
                "status": "pass" if len(df) > 0 else ("skipped_not_applicable" if not applicable else "zero_rows"),
            })

    source_manifest_rows = []
    readiness_rows = []
    for lane, frames in outputs_by_lane.items():
        if frames:
            combined = pd.concat(frames, ignore_index=True).drop_duplicates()
        else:
            combined = pd.DataFrame()
        # Write combined lane output.
        lane_file = f"openf1_{lane}.csv"
        write_df(combined, data_latest / lane_file)
        write_df(combined, data_history / lane_file)
        rows = int(len(combined))
        attempted_sessions = int((pd.DataFrame(lane_session_rows).query("lane == @lane").shape[0]) if lane_session_rows else 0)
        applicable_sessions = int(pd.DataFrame(lane_session_rows).query("lane == @lane and applicable == True").shape[0]) if lane_session_rows else 0
        result, reason = classify_lane(lane, rows, attempted_sessions, applicable_sessions)
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
    lane_session_df = pd.DataFrame(lane_session_rows)
    readiness_df = pd.DataFrame(readiness_rows)
    source_manifest_df = pd.DataFrame(source_manifest_rows)

    write_df(request_df, latest_root / "request_log.csv")
    write_df(request_df, history_root / "request_log.csv")
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
    run_id = utc_now().strftime("%Y%m%d_%H%M%S")
    manifest = {
        "artifact_profile": "openf1-lightweight-source-closure",
        "generated_utc": iso_now(),
        "season": season,
        "completed_only": completed_only,
        "target_session_count": int(len(sessions)),
        "lanes": readiness_rows,
        "pass_count": pass_count,
        "pass_with_warnings_count": warning_count,
        "fail_count": fail_count,
        "heavy_endpoints_excluded_by_default": ["car_data", "location"],
        "timestamp_policy": "dt.datetime.now(dt.UTC)",
        "no_drs_2026_assumption": True,
        "previous_manifest_generated_utc": previous_manifest.get("generated_utc"),
        "latest_zip": "openf1_lightweight_source_closure.zip",
        "history_path": str(history_root.relative_to(output_root)),
    }
    (latest_root / "latest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (history_root / "latest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (latest_root / "data_readiness.json").write_text(json.dumps({"generated_utc": iso_now(), "lanes": readiness_rows}, indent=2), encoding="utf-8")
    (history_root / "data_readiness.json").write_text(json.dumps({"generated_utc": iso_now(), "lanes": readiness_rows}, indent=2), encoding="utf-8")

    report_lines = [
        "# F1 OpenF1 Lightweight Source Closure Report",
        "",
        f"Generated UTC: {iso_now()}",
        f"Season: {season}",
        f"Target sessions: {len(sessions)}",
        "",
        "## Result",
        "",
        f"Pass lanes: {pass_count}",
        f"Pass with warnings lanes: {warning_count}",
        f"Fail lanes: {fail_count}",
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

    print("OpenF1 lightweight source closure complete.")
    print(f"Latest output: {latest_root}")
    print(f"History output: {history_root}")
    print(f"Latest ZIP SHA256: {zip_digest}")
    print(f"Pass lanes: {pass_count}; Pass with warnings lanes: {warning_count}; Fail lanes: {fail_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
