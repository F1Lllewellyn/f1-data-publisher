"""Pure hosted-OpenF1 historical REST capture and source-receipt contract.

All facts and exact response bytes are caller supplied. This module performs no
external I/O or ambient-state access.
"""
from datetime import timedelta
import json
import math
import re
import urllib.parse

import verify_forecast_integrity_receipts_v1 as receipt_contract


SCHEMA_VERSION = "dr002-openf1-historical-rest-capture-assessment-v1"
VALIDATED = "OPENF1_HISTORICAL_REST_CAPTURE_VALIDATED"
HOLD = "HOLD"
API_BASE = "https://api.openf1.org/v1"
HISTORICAL_WINDOW_DELAY_SECONDS = 1800

DEPENDENCY_BLOBS = {
    "scripts/openf1/publish_openf1_lightweight_source_closure.py":
        "ebdba37477b7efdc584c2550295cb7c61cf53481",
    ".github/workflows/f1-openf1-lightweight-source-closure.yml":
        "7521e0e91e201b0610d8771a8524393c59ba1ecb",
    "configs/openf1/openf1_lightweight_source_closure_policy.json":
        "d21765b33e66dfa499b92c9f44a4543608f2c6a4",
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    "scripts/forecast_bundles/dr002_verified_source_consumer_v1.py":
        "e402939202ed579c368499f3baefb3641de27de7",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}

TRUST_CEILINGS = (
    "publisher_source_authenticated",
    "openf1_official_f1_source",
    "observation_clock_authenticated",
    "historical_availability_before_first_observation_proven",
    "publisher_revision_completeness_proven",
    "global_observation_completeness_proven",
    "production_revision_tracking_proven",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "dr002_activated",
    "promotion_allowed",
)


class HistoricalCaptureInputError(ValueError):
    """Malformed, ambiguous, temporally ineligible, or unsupported input."""


def _require(condition, reason):
    if not condition:
        raise HistoricalCaptureInputError(reason)


def _text(value, reason):
    _require(type(value) is str and value.strip() == value and bool(value), reason)
    _require(not any(ord(character) < 32 or ord(character) == 127 for character in value), reason)
    return value


def _parameter_value(value):
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is float:
        _require(math.isfinite(value), "malformed_request_params")
        return json.dumps(value, allow_nan=False, separators=(",", ":"))
    if type(value) is str:
        _text(value, "malformed_request_params")
        return value
    raise HistoricalCaptureInputError("malformed_request_params")


def canonical_request_uri(endpoint, request_params):
    """Return one deterministic URI from a safe endpoint and scalar mapping."""
    _require(type(endpoint) is str and re.fullmatch(r"[a-z][a-z0-9_]*", endpoint) is not None,
             "malformed_endpoint")
    _require(type(request_params) is dict and bool(request_params), "malformed_request_params")
    encoded = []
    for key in sorted(request_params):
        _require(type(key) is str and re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*(?:[<>]=?)?", key) is not None,
            "malformed_request_params")
        encoded.append((key, _parameter_value(request_params[key])))
    query = urllib.parse.urlencode(
        encoded, doseq=False, safe="", encoding="utf-8", errors="strict",
        quote_via=urllib.parse.quote,
    )
    return API_BASE + "/" + endpoint + "?" + query


def _scope_value_matches(value, expected):
    if type(value) is str:
        return value == expected
    if type(value) is int:
        return str(value) == expected
    return False


def _validate_request_scope(request_params, *, meeting_id, session_id):
    if "session_key" in request_params:
        _require(_scope_value_matches(request_params["session_key"], session_id),
                 "request_session_scope_mismatch")
    if "meeting_key" in request_params:
        _require(_scope_value_matches(request_params["meeting_key"], meeting_id),
                 "request_meeting_scope_mismatch")


def _validate_response_scope(value, *, meeting_id, session_id):
    if type(value) is dict:
        if "session_key" in value:
            _require(_scope_value_matches(value["session_key"], session_id),
                     "response_session_scope_mismatch")
        if "meeting_key" in value:
            _require(_scope_value_matches(value["meeting_key"], meeting_id),
                     "response_meeting_scope_mismatch")
        for item in value.values():
            _validate_response_scope(item, meeting_id=meeting_id, session_id=session_id)
    elif type(value) is list:
        for item in value:
            _validate_response_scope(item, meeting_id=meeting_id, session_id=session_id)


def _strict_response_json(raw_bytes):
    _require(type(raw_bytes) is bytes and bool(raw_bytes), "raw_response_not_bytes")

    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, "duplicate_json_key")
            value[key] = item
        return value

    def reject_constant(_value):
        raise HistoricalCaptureInputError("malformed_json")

    try:
        value = json.loads(
            raw_bytes, object_pairs_hook=pairs, parse_constant=reject_constant,
        )
    except HistoricalCaptureInputError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        raise HistoricalCaptureInputError("malformed_json")
    _require(type(value) in (list, dict), "response_json_not_list_or_object")
    return value


def _format_utc(value):
    timespec = "microseconds" if value.microsecond else "seconds"
    return value.isoformat(timespec=timespec).replace("+00:00", "Z")


def _assessment_defaults(*, raw_response_bytes, session_end_utc, first_observed_utc,
                         capture_ref):
    raw = raw_response_bytes if type(raw_response_bytes) is bytes else None
    return {
        "schema_version": SCHEMA_VERSION,
        "assessment_type": "OPENF1_HISTORICAL_REST_CAPTURE",
        "status": HOLD,
        "reason_codes": [],
        "canonical_request_uri": None,
        "raw_response_bytes": raw,
        "raw_response_sha256": receipt_contract.sha256(raw) if raw is not None else None,
        "row_count": None,
        "session_end_utc": session_end_utc if type(session_end_utc) is str else None,
        "historical_window_eligible_utc": None,
        "first_observed_utc": first_observed_utc if type(first_observed_utc) is str else None,
        "source_capture_receipt_bytes": None,
        "receipt_sha256": None,
        "source_id": None,
        "capture_ref": capture_ref if type(capture_ref) is str else None,
        "openf1_documented_historical_window_satisfied": False,
        **{field: False for field in TRUST_CEILINGS},
    }


def assess_openf1_historical_rest_capture(
    *,
    event_id,
    meeting_id,
    session_id,
    endpoint,
    request_params,
    raw_response_bytes,
    http_status,
    session_end_utc,
    first_observed_utc,
    ingested_utc,
    receipt_created_utc,
    capture_ref,
    implementation,
    event_time_utc=None,
    publisher_time_utc=None,
    unsupported_claims=None,
):
    """Assess exact caller-supplied historical bytes and build one existing receipt.

    HOLD is returned for every malformed or ineligible input. A validated result
    proves only that the supplied exact bytes were first observed at the supplied
    local observation time, after OpenF1's documented historical-window delay.
    """
    result = _assessment_defaults(
        raw_response_bytes=raw_response_bytes,
        session_end_utc=session_end_utc,
        first_observed_utc=first_observed_utc,
        capture_ref=capture_ref,
    )
    try:
        assertions = {} if unsupported_claims is None else unsupported_claims
        _require(type(assertions) is dict, "malformed_unsupported_claims")
        _require(all(key in TRUST_CEILINGS and type(value) is bool
                     for key, value in assertions.items()), "malformed_unsupported_claims")
        _require(not any(assertions.values()), "unsupported_trust_assertion")

        scope = {
            "event_id": _text(event_id, "malformed_scope"),
            "meeting_id": _text(meeting_id, "malformed_scope"),
            "session_id": _text(session_id, "malformed_scope"),
        }
        _text(capture_ref, "malformed_capture_ref")
        _text(implementation, "malformed_implementation")
        uri = canonical_request_uri(endpoint, request_params)
        _validate_request_scope(request_params, meeting_id=meeting_id, session_id=session_id)
        source_id = (
            "openf1:" + endpoint + ":"
            + receipt_contract.sha256(uri.encode("utf-8"))
        )
        result.update(canonical_request_uri=uri, source_id=source_id)

        session_end = receipt_contract._time(session_end_utc)
        first_observed = receipt_contract._time(first_observed_utc)
        ingested = receipt_contract._time(ingested_utc)
        receipt_created = receipt_contract._time(receipt_created_utc)
        eligible = session_end + timedelta(seconds=HISTORICAL_WINDOW_DELAY_SECONDS)
        result["historical_window_eligible_utc"] = _format_utc(eligible)
        if first_observed >= eligible:
            result["openf1_documented_historical_window_satisfied"] = True
        _require(first_observed >= eligible, "observation_before_historical_window")
        _require(first_observed <= ingested <= receipt_created, "inconsistent_capture_times")

        if event_time_utc is not None:
            receipt_contract._time(event_time_utc)
        if publisher_time_utc is not None:
            receipt_contract._time(publisher_time_utc)
        _require(type(http_status) is int and http_status == 200, "http_status_not_200")
        parsed = _strict_response_json(raw_response_bytes)
        _validate_response_scope(parsed, meeting_id=meeting_id, session_id=session_id)
        response_sha = receipt_contract.sha256(raw_response_bytes)
        result["raw_response_sha256"] = response_sha
        result["row_count"] = len(parsed) if type(parsed) is list else None

        payload = {
            "source_id": source_id,
            "source_uri": uri,
            "source_sha256": response_sha,
            "event_time_utc": event_time_utc,
            "publisher_time_utc": publisher_time_utc,
            "first_observed_utc": first_observed_utc,
            "ingested_utc": ingested_utc,
            "capture_ref": capture_ref,
            "implementation": implementation,
        }
        identity = {
            "receipt_type": "source_capture",
            "scope": scope,
            "parent_receipt_ids": [],
            "payload": payload,
        }
        receipt = {
            "schema_version": receipt_contract.VERSION,
            "receipt_id": "source_capture:" + receipt_contract.sha256(
                receipt_contract.canonical_json_bytes(identity)
            ),
            "receipt_created_utc": receipt_created_utc,
            **identity,
        }
        receipt_contract.validate_receipt_envelope(receipt)
        receipt_contract.verify_temporal_bindings(receipt)
        _require(receipt["parent_receipt_ids"] == [], "source_capture_has_parents")
        _require(receipt["payload"]["source_sha256"] == response_sha,
                 "source_hash_mismatch")
        receipt_bytes = receipt_contract.canonical_json_bytes(receipt)
        receipt_sha = receipt_contract.sha256(receipt_bytes)
        _require(receipt_sha == receipt_contract.receipt_sha256(receipt),
                 "canonical_receipt_hash_mismatch")
        result.update(
            status=VALIDATED,
            source_capture_receipt_bytes=receipt_bytes,
            receipt_sha256=receipt_sha,
        )
        return result
    except (HistoricalCaptureInputError, receipt_contract.ReceiptError) as exc:
        result["reason_codes"] = [getattr(exc, "code", None) or str(exc)
                                  or "historical_capture_hold"]
        return result
    except (TypeError, ValueError, KeyError, OverflowError, AttributeError):
        result["reason_codes"] = ["malformed_historical_capture_input"]
        return result
