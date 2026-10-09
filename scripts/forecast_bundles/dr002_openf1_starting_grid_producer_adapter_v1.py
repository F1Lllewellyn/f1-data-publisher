"""Pure provenance-backed OpenF1 starting-grid producer-input adapter.

The exact raw JSON bytes and their parentless source-capture receipt remain the
scientific evidence.  The deterministic CSV returned here is a derived runtime
representation only.  This module performs no network, filesystem, clock,
producer, model, workflow, or source-discovery operation and creates no receipt
or trust upgrade.
"""
import csv
import io
import json
import math
import re

import dr002_frozen_evidence_manifest_v1 as frozen_contract
import dr002_openf1_historical_rest_capture_v1 as capture_contract
import verify_forecast_integrity_receipts_v1 as receipt_contract


SCHEMA_VERSION = "dr002-openf1-starting-grid-producer-adapter-v2"
VALIDATED = "OPENF1_STARTING_GRID_POST_EVENT_MECHANICS_VALIDATED_UNOFFICIAL"
HOLD = "HOLD"
SOURCE_SESSION_KIND = "Qualifying"
TARGET_SESSION_KIND = "Race"
MAX_GRID_ROWS = 26
DOCUMENTED_FIELDS = frozenset({
    "position",
    "driver_number",
    "lap_duration",
    "meeting_key",
    "session_key",
})
CSV_FIELDS = (
    "driver_number",
    "position",
    "event_id",
    "meeting_id",
    "session_id",
)
CLAIM_CEILINGS = (
    "official_fia_grid_authenticated",
    "official_final_grid_verified",
    "source_earliest_availability_verified",
    "historical_pre_race_availability_proven",
    "race_session_authority_authenticated",
    "derived_csv_is_source_evidence",
    "verified_receipt_bindings_created",
    "new_scientific_receipt_created",
    "blind_validation_eligible",
    "stable_engine_execution_proven",
    "production_forecast_generated",
    "dr002_activated",
    "promotion_allowed",
)
DEPENDENCY_BLOBS = {
    "scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py":
        "e68fa528cd73cd5c72afd97622a00d6e5b29be19",
    "scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py":
        "357ac56a6cfe317e21d9ce71d78c58683e444a5a",
    "scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py":
        "8dfd855184b172ce88235ee7de3ea33a68031b2e",
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    "scripts/forecast_bundles/dr002_openf1_weather_drivers_frozen_producer_composition_v1.py":
        "f69a5ac49b6e3055cd13472037f8b49e8ea41265",
    "scripts/forecasts/produce_actual_forecast_rows_v1.py":
        "af27586668c767de126af829c1131c6bae4634ad",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
    "scripts/openf1/publish_openf1_lightweight_source_closure.py":
        "f2e28d326255a48a48f873d101cd3e3e99955c1f",
    ".github/workflows/f1-openf1-lightweight-source-closure.yml":
        "c32bd7bb2f8a84d1bb4e8995be246c389418f512",
}


class StartingGridAdapterInputError(ValueError):
    """The complete adapter result must HOLD with no partial derived output."""


def _require(condition, reason):
    if not condition:
        raise StartingGridAdapterInputError(reason)


def _text(value, reason="malformed_scope"):
    _require(type(value) is str and value.strip() == value and bool(value), reason)
    _require(not any(ord(character) < 32 or ord(character) == 127
                     for character in value), reason)
    return value


def _canonical_positive_decimal_text(value, reason):
    _require(type(value) is str and re.fullmatch(r"[1-9][0-9]*", value), reason)
    return value


def _strict_json_bytes(data, *, top_level):
    _require(type(data) is bytes and bool(data), "json_not_nonempty_bytes")

    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, "duplicate_json_key")
            value[key] = item
        return value

    def reject_constant(_value):
        raise StartingGridAdapterInputError("nonfinite_json")

    try:
        value = json.loads(
            data,
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except StartingGridAdapterInputError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        raise StartingGridAdapterInputError("malformed_json")
    _require(type(value) is top_level, "wrong_json_top_level")
    return value


def _receipt_identity(receipt):
    return {
        "receipt_type": receipt["receipt_type"],
        "scope": receipt["scope"],
        "parent_receipt_ids": receipt["parent_receipt_ids"],
        "payload": receipt["payload"],
    }


def _scope_row_value_matches(value, expected, reason):
    if type(value) is int:
        _require(value > 0 and str(value) == expected, reason)
        return
    if type(value) is str:
        _require(re.fullmatch(r"[1-9][0-9]*", value) is not None
                 and value == expected, reason)
        return
    raise StartingGridAdapterInputError(reason)


def _validate_rows(rows, *, meeting_id, session_id):
    _require(bool(rows), "empty_starting_grid_response")
    _require(len(rows) <= MAX_GRID_ROWS, "implausible_starting_grid_row_count")
    positions = set()
    driver_numbers = set()
    for row in rows:
        _require(type(row) is dict, "malformed_starting_grid_row")
        _require(set(row) == DOCUMENTED_FIELDS,
                 "starting_grid_documented_fields_mismatch")

        position = row["position"]
        _require(type(position) is int and position > 0,
                 "malformed_grid_position")
        _require(position not in positions, "duplicate_grid_position")
        positions.add(position)

        driver_number = row["driver_number"]
        _require(type(driver_number) is int and driver_number > 0,
                 "malformed_driver_number")
        _require(driver_number not in driver_numbers, "duplicate_driver_number")
        driver_numbers.add(driver_number)

        lap_duration = row["lap_duration"]
        _require(
            lap_duration is None
            or (
                type(lap_duration) in (int, float)
                and math.isfinite(lap_duration)
                and lap_duration >= 0
            ),
            "malformed_lap_duration",
        )
        _scope_row_value_matches(
            row["meeting_key"], meeting_id, "starting_grid_meeting_scope_mismatch"
        )
        _scope_row_value_matches(
            row["session_key"], session_id, "starting_grid_session_scope_mismatch"
        )

    expected_positions = set(range(1, len(rows) + 1))
    _require(positions == expected_positions,
             "noncontiguous_or_unrepresented_grid_slots")
    return positions, driver_numbers


def _starting_grid_csv_bytes(rows, *, event_id, meeting_id, session_id):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_FIELDS)
    for row in sorted(rows, key=lambda item: item["position"]):
        writer.writerow((
            row["driver_number"],
            row["position"],
            event_id,
            meeting_id,
            session_id,
        ))
    return stream.getvalue().encode("utf-8")


def _reason(exc):
    return getattr(exc, "code", None) or str(exc) or "malformed_adapter_input"


def _hold(exc):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HOLD,
        "reason_codes": [_reason(exc)],
        "session_kind_asserted": False,
        "source_session_classification_authenticated": False,
        "target_race_session_classification_authenticated": False,
        "producer_input_csv_is_target_race_scoped": False,
        "cross_session_join_authorized": False,
        **{field: False for field in CLAIM_CEILINGS},
    }


def adapt_openf1_starting_grid_to_producer_input(
    *,
    source_capture_receipt_bytes,
    raw_starting_grid_response_bytes,
    event_id,
    meeting_id,
    session_id,
    source_session_kind,
    target_race_session_id,
):
    """Validate exact raw evidence and return deterministic ``starting_grid.csv``.

    The receipt and CSV remain scoped to the Qualifying source session.  The
    target Race ID is an unauthenticated caller assertion only and does not
    authorize a cross-session producer join.  Any failure returns HOLD with no
    frozen manifest, source identity, digest, or derived CSV bytes.
    """
    try:
        scope = {
            "event_id": _text(event_id),
            "meeting_id": _canonical_positive_decimal_text(
                meeting_id, "malformed_meeting_id"
            ),
            "session_id": _canonical_positive_decimal_text(
                session_id, "malformed_session_id"
            ),
        }
        _require(
            type(source_session_kind) is str
            and source_session_kind == SOURCE_SESSION_KIND,
            "source_session_kind_not_qualifying",
        )
        target_race_id = _canonical_positive_decimal_text(
            target_race_session_id, "malformed_target_race_session_id"
        )
        _require(target_race_id != scope["session_id"],
                 "target_race_session_matches_source_session")

        _require(type(source_capture_receipt_bytes) is bytes
                 and bool(source_capture_receipt_bytes),
                 "receipt_not_nonempty_bytes")
        receipt = frozen_contract.strict_json(source_capture_receipt_bytes)
        _require(type(receipt) is dict, "malformed_source_receipt")
        _require(receipt_contract.canonical_json_bytes(receipt)
                 == source_capture_receipt_bytes,
                 "noncanonical_receipt_bytes")
        receipt_contract.validate_receipt_envelope(receipt)
        receipt_contract.verify_temporal_bindings(receipt)
        _require(receipt["receipt_type"] == "source_capture", "wrong_receipt_type")
        _require(receipt["parent_receipt_ids"] == [], "source_capture_has_parents")
        _require(receipt["scope"] == scope, "receipt_scope_mismatch")

        expected_receipt_id = (
            "source_capture:"
            + receipt_contract.sha256(
                receipt_contract.canonical_json_bytes(_receipt_identity(receipt))
            )
        )
        _require(receipt["receipt_id"] == expected_receipt_id,
                 "receipt_id_mismatch")

        _require(type(raw_starting_grid_response_bytes) is bytes
                 and bool(raw_starting_grid_response_bytes),
                 "raw_starting_grid_not_nonempty_bytes")
        raw_sha256 = receipt_contract.sha256(raw_starting_grid_response_bytes)
        payload = receipt["payload"]
        _require(payload["source_sha256"] == raw_sha256,
                 "raw_source_hash_mismatch")

        expected_uri = capture_contract.canonical_request_uri(
            "starting_grid", {"session_key": session_id}
        )
        expected_source_id = (
            "openf1:starting_grid:"
            + receipt_contract.sha256(expected_uri.encode("utf-8"))
        )
        _require(payload["source_uri"] == expected_uri,
                 "wrong_openf1_starting_grid_source_uri")
        _require(payload["source_id"] == expected_source_id,
                 "wrong_openf1_starting_grid_source_id")

        receipt_ref = "memory:source_capture_receipt"
        content_ref = "memory:raw_starting_grid_response"
        in_memory = {
            receipt_ref: source_capture_receipt_bytes,
            content_ref: raw_starting_grid_response_bytes,
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

        rows = _strict_json_bytes(
            raw_starting_grid_response_bytes, top_level=list
        )
        positions, driver_numbers = _validate_rows(
            rows, meeting_id=meeting_id, session_id=session_id
        )
        csv_bytes = _starting_grid_csv_bytes(
            rows,
            event_id=event_id,
            meeting_id=meeting_id,
            session_id=session_id,
        )
        csv_sha256 = receipt_contract.sha256(csv_bytes)

        return {
            "schema_version": SCHEMA_VERSION,
            "status": VALIDATED,
            "reason_codes": [],
            "scope": scope,
            "session_kind": SOURCE_SESSION_KIND,
            "session_kind_asserted": True,
            "session_kind_assertion_authenticated": False,
            "source_qualifying_session_id": scope["session_id"],
            "target_race_session_id": target_race_id,
            "source_session_kind": SOURCE_SESSION_KIND,
            "target_session_kind": TARGET_SESSION_KIND,
            "source_session_classification_authenticated": False,
            "target_race_session_classification_authenticated": False,
            "producer_input_csv_is_target_race_scoped": False,
            "cross_session_join_authorized": False,
            "provider_category": "UNOFFICIAL_OPENF1_DOCUMENTED_REST",
            "commercial_or_redistribution_permission_claimed": False,
            "source_receipt_id": receipt["receipt_id"],
            "raw_source_id": payload["source_id"],
            "raw_source_sha256": raw_sha256,
            "frozen_evidence_manifest": frozen["manifest"],
            "frozen_evidence_manifest_sha256":
                frozen["frozen_evidence_manifest_sha256"],
            "producer_input_source_name": "starting_grid",
            "producer_input_filename": "starting_grid.csv",
            "row_count": len(rows),
            "unique_driver_count": len(driver_numbers),
            "slot_count": len(positions),
            "producer_input_csv_bytes": csv_bytes,
            "producer_input_sha256": csv_sha256,
            "derived_runtime_identity":
                "derived:openf1-starting-grid-csv:" + csv_sha256,
            "lineage_statement": (
                "starting_grid.csv was deterministically derived from the "
                "validated exact raw OpenF1 starting_grid content bound by "
                "source_receipt_id; the CSV is a distinct runtime "
                "representation keyed to the Qualifying source session, not "
                "source evidence, a target-Race join, or an official FIA grid"
            ),
            **{field: False for field in CLAIM_CEILINGS},
        }
    except (
        StartingGridAdapterInputError,
        frozen_contract.EvidenceError,
        receipt_contract.ReceiptError,
        TypeError,
        ValueError,
        KeyError,
        UnicodeDecodeError,
        OverflowError,
        AttributeError,
    ) as exc:
        return _hold(exc)
