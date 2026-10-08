"""Pure raw-OpenF1-weather to producer-input adapter.

The exact raw JSON bytes and their parentless source-capture receipt remain the
scientific evidence.  The deterministic CSV returned here is a derived runtime
representation only; this module creates no receipt, file, network request,
clock observation, or trust upgrade.
"""
import csv
import io
import json
import math

import dr002_frozen_evidence_manifest_v1 as frozen_contract
import dr002_openf1_historical_rest_capture_v1 as capture_contract
import verify_forecast_integrity_receipts_v1 as receipt_contract


SCHEMA_VERSION = "dr002-openf1-weather-producer-adapter-v1"
VALIDATED = "OPENF1_WEATHER_PRODUCER_ADAPTER_VALIDATED"
HOLD = "HOLD"
WEATHER_FIELDS = (
    "date",
    "session_key",
    "meeting_key",
    "air_temperature",
    "track_temperature",
    "humidity",
    "pressure",
    "rainfall",
    "wind_direction",
    "wind_speed",
)
NUMERIC_WEATHER_FIELDS = WEATHER_FIELDS[3:]
DEPENDENCY_BLOBS = {
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    "scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py":
        "8dfd855184b172ce88235ee7de3ea33a68031b2e",
    "scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py":
        "e68fa528cd73cd5c72afd97622a00d6e5b29be19",
    "scripts/forecasts/produce_actual_forecast_rows_v1.py":
        "af27586668c767de126af829c1131c6bae4634ad",
    "docs/DR002_PRE2B7K4R3_ONE_HISTORICAL_OPENF1_REST_SHADOW_RUN_2026-10-08.md":
        "db92fb23ff0adf95e59a80f14dcd527b6d1f9906",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}


class WeatherAdapterInputError(ValueError):
    """The complete adapter result must HOLD with no partial derived output."""


def _require(condition, reason):
    if not condition:
        raise WeatherAdapterInputError(reason)


def _text(value, reason="malformed_scope"):
    _require(type(value) is str and value.strip() == value and bool(value), reason)
    _require(not any(ord(character) < 32 or ord(character) == 127
                     for character in value), reason)
    return value


def _strict_json_bytes(data, *, top_level=None):
    _require(type(data) is bytes and bool(data), "json_not_nonempty_bytes")

    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, "duplicate_json_key")
            value[key] = item
        return value

    def reject_constant(_value):
        raise WeatherAdapterInputError("nonfinite_json")

    try:
        value = json.loads(data, object_pairs_hook=pairs,
                           parse_constant=reject_constant)
    except WeatherAdapterInputError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        raise WeatherAdapterInputError("malformed_json")
    if top_level is not None:
        _require(type(value) is top_level, "wrong_json_top_level")
    return value


def _receipt_identity(receipt):
    return {
        "receipt_type": receipt["receipt_type"],
        "scope": receipt["scope"],
        "parent_receipt_ids": receipt["parent_receipt_ids"],
        "payload": receipt["payload"],
    }


def _scope_value_matches(value, expected):
    return ((type(value) is str and value == expected)
            or (type(value) is int and str(value) == expected))


def _validate_weather_rows(rows, *, meeting_id, session_id):
    _require(bool(rows), "empty_weather_response")
    expected_fields = set(WEATHER_FIELDS)
    for row in rows:
        _require(type(row) is dict and set(row) == expected_fields,
                 "malformed_weather_row_fields")
        try:
            receipt_contract._time(row["date"])
        except (receipt_contract.ReceiptError, TypeError, ValueError, AttributeError):
            raise WeatherAdapterInputError("malformed_or_non_utc_weather_date")
        _require(_scope_value_matches(row["session_key"], session_id),
                 "weather_session_scope_mismatch")
        _require(_scope_value_matches(row["meeting_key"], meeting_id),
                 "weather_meeting_scope_mismatch")
        for field in NUMERIC_WEATHER_FIELDS:
            value = row[field]
            _require(type(value) in (int, float) and math.isfinite(value),
                     "malformed_numeric_weather_value")


def _stable_scalar(value):
    if type(value) is str:
        return value
    if type(value) in (int, float):
        return json.dumps(value, allow_nan=False, ensure_ascii=True,
                          separators=(",", ":"))
    raise WeatherAdapterInputError("unsupported_csv_scalar")


def _weather_csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(WEATHER_FIELDS)
    for row in rows:
        writer.writerow([_stable_scalar(row[field]) for field in WEATHER_FIELDS])
    return stream.getvalue().encode("utf-8")


def _reason(exc):
    return getattr(exc, "code", None) or str(exc) or "malformed_adapter_input"


def _hold(exc):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HOLD,
        "reason_codes": [_reason(exc)],
        "derived_csv_is_source_evidence": False,
        "new_scientific_receipt_created": False,
        "normalization_receipt_created": False,
        "verified_receipt_bindings_created": False,
        "stable_engine_execution_proven": False,
        "blind_validation_eligible": False,
        "production_forecast_generated": False,
        "dr002_activated": False,
        "promotion_allowed": False,
    }


def adapt_openf1_weather_to_producer_input(
    *,
    source_capture_receipt_bytes,
    raw_weather_response_bytes,
    event_id,
    meeting_id,
    session_id,
):
    """Validate exact raw evidence and return deterministic ``weather.csv`` bytes.

    Every input is explicit and in memory.  Any failure returns HOLD without a
    frozen manifest or derived bytes.
    """
    try:
        scope = {
            "event_id": _text(event_id),
            "meeting_id": _text(meeting_id),
            "session_id": _text(session_id),
        }
        _require(type(source_capture_receipt_bytes) is bytes
                 and bool(source_capture_receipt_bytes),
                 "receipt_not_nonempty_bytes")
        receipt = frozen_contract.strict_json(source_capture_receipt_bytes)
        _require(receipt_contract.canonical_json_bytes(receipt)
                 == source_capture_receipt_bytes, "noncanonical_receipt_bytes")
        receipt_contract.validate_receipt_envelope(receipt)
        receipt_contract.verify_temporal_bindings(receipt)
        _require(receipt["receipt_type"] == "source_capture",
                 "wrong_receipt_type")
        _require(receipt["parent_receipt_ids"] == [], "source_capture_has_parents")
        _require(receipt["scope"] == scope, "receipt_scope_mismatch")

        expected_receipt_id = (
            "source_capture:" + receipt_contract.sha256(
                receipt_contract.canonical_json_bytes(_receipt_identity(receipt))
            )
        )
        _require(receipt["receipt_id"] == expected_receipt_id,
                 "receipt_id_mismatch")

        _require(type(raw_weather_response_bytes) is bytes
                 and bool(raw_weather_response_bytes),
                 "raw_weather_not_nonempty_bytes")
        raw_sha256 = receipt_contract.sha256(raw_weather_response_bytes)
        payload = receipt["payload"]
        _require(payload["source_sha256"] == raw_sha256,
                 "raw_source_hash_mismatch")

        expected_uri = capture_contract.canonical_request_uri(
            "weather", {"session_key": session_id}
        )
        expected_source_id = (
            "openf1:weather:"
            + receipt_contract.sha256(expected_uri.encode("utf-8"))
        )
        _require(payload["source_uri"] == expected_uri,
                 "wrong_openf1_weather_source_uri")
        _require(payload["source_id"] == expected_source_id,
                 "wrong_openf1_weather_source_id")

        receipt_ref = "memory:source_capture_receipt"
        content_ref = "memory:raw_weather_response"
        in_memory = {
            receipt_ref: source_capture_receipt_bytes,
            content_ref: raw_weather_response_bytes,
        }

        def read_bytes(reference):
            _require(reference in in_memory, "undeclared_in_memory_reference")
            return in_memory[reference]

        frozen = frozen_contract.build_frozen_evidence_manifest(
            {
                "event_id": event_id,
                "meeting_id": meeting_id,
                "allowed_session_ids": [session_id],
                "captures": [{
                    "receipt_path": receipt_ref,
                    "content_path": content_ref,
                }],
            },
            read_bytes=read_bytes,
        )
        frozen_contract.validate_frozen_evidence_manifest(frozen)
        _require(frozen["manifest"]["trust"] == frozen_contract.TRUST,
                 "frozen_manifest_trust_changed")

        rows = _strict_json_bytes(raw_weather_response_bytes, top_level=list)
        _validate_weather_rows(rows, meeting_id=meeting_id, session_id=session_id)
        csv_bytes = _weather_csv_bytes(rows)
        csv_sha256 = receipt_contract.sha256(csv_bytes)

        return {
            "schema_version": SCHEMA_VERSION,
            "status": VALIDATED,
            "reason_codes": [],
            "scope": scope,
            "source_receipt_id": receipt["receipt_id"],
            "raw_source_sha256": raw_sha256,
            "frozen_evidence_manifest": frozen["manifest"],
            "frozen_evidence_manifest_sha256":
                frozen["frozen_evidence_manifest_sha256"],
            "producer_input_source_name": "weather",
            "producer_input_filename": "weather.csv",
            "row_count": len(rows),
            "producer_input_csv_bytes": csv_bytes,
            "producer_input_sha256": csv_sha256,
            "lineage_statement": (
                "weather.csv was deterministically derived from the validated "
                "exact raw source content bound by source_receipt_id; the CSV "
                "is a separate runtime representation, not source evidence"
            ),
            "derived_csv_is_source_evidence": False,
            "new_scientific_receipt_created": False,
            "normalization_receipt_created": False,
            "verified_receipt_bindings_created": False,
            "stable_engine_execution_proven": False,
            "blind_validation_eligible": False,
            "production_forecast_generated": False,
            "dr002_activated": False,
            "promotion_allowed": False,
        }
    except (WeatherAdapterInputError, frozen_contract.EvidenceError,
            receipt_contract.ReceiptError, TypeError, ValueError, KeyError,
            UnicodeDecodeError, OverflowError, AttributeError) as exc:
        return _hold(exc)
