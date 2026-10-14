"""Pure offline prospective OpenF1 three-source pre-cutoff candidate.

The caller supplies every byte and timestamp.  This module performs no I/O,
source discovery, clock observation, workflow dispatch, producer/model call, or
receipt creation.  A successful result establishes only internal structural and
temporal consistency of self-declared source-capture receipts.  It does not
authenticate the publisher, observation clock, FIA grid, or production use.
"""
import csv
import hashlib
import io
import json
import re

import dr002_openf1_drivers_producer_adapter_v1 as drivers_adapter
import dr002_openf1_starting_grid_producer_adapter_v1 as grid_adapter
import dr002_openf1_three_source_event_compatibility_v1 as compatibility
import dr002_openf1_three_source_grid_projection_v1 as projection
import dr002_openf1_weather_producer_adapter_v1 as weather_adapter


SCHEMA_VERSION = "dr002-openf1-three-source-precutoff-candidate-v1"
MANIFEST_SCHEMA_VERSION = (
    "dr002-openf1-three-source-precutoff-candidate-manifest-v1"
)
VALIDATED = "PROSPECTIVE_ASOF_SOURCE_CANDIDATE_STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
CLASSIFICATION = "NON_OPERATIONAL_SANDBOX_PRE_CUTOFF_CANDIDATE_ONLY"
HOLD = "HOLD"
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
SOURCE_NAMES = ("drivers", "starting_grid", "weather")
CANONICAL_FILENAMES = {
    "drivers": "drivers.csv",
    "starting_grid": "starting_grid.csv",
    "weather": "weather.csv",
}
FALSE_FLAGS = (
    "source_capture_externally_attested",
    "source_publisher_authenticated",
    "official_fia_final_grid_authenticated",
    "historical_availability_proven",
    "production_authenticated",
    "verified_receipt_bindings_created",
    "producer_execution_attempted",
    "forecast_generated",
    "forecast_locked",
    "blind_validation_eligible",
    "dr002_activated",
    "promotion_allowed",
    "stable_engine_execution_proven",
)


class CandidateInputError(ValueError):
    """Any failed invariant makes the complete candidate HOLD."""


def _require(condition, reason):
    if not condition:
        raise CandidateInputError(reason)


def _sha256(data):
    _require(type(data) is bytes, "hash_input_not_bytes")
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value):
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise CandidateInputError("candidate_manifest_not_canonical_json") from exc


def _hold(reason):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HOLD,
        "reason_codes": [reason],
        **{flag: False for flag in FALSE_FLAGS},
    }


def _adapter_csv(result, *, expected_status, source_name, scope, raw_bytes):
    _require(type(result) is dict, source_name + "_adapter_result_malformed")
    if result.get("status") != expected_status:
        reasons = result.get("reason_codes")
        reason = reasons[0] if type(reasons) is list and reasons else "unspecified"
        raise CandidateInputError(source_name + "_adapter_hold:" + str(reason))
    _require(result.get("scope") == scope, source_name + "_adapter_scope_mismatch")
    _require(
        result.get("producer_input_source_name") == source_name
        and result.get("producer_input_filename") == CANONICAL_FILENAMES[source_name],
        source_name + "_adapter_output_identity_mismatch",
    )
    csv_bytes = result.get("producer_input_csv_bytes")
    digest = result.get("producer_input_sha256")
    _require(type(csv_bytes) is bytes and bool(csv_bytes),
             source_name + "_derived_csv_missing")
    _require(type(digest) is str and HEX64.fullmatch(digest)
             and digest == _sha256(csv_bytes),
             source_name + "_derived_hash_mismatch")
    _require(result.get("raw_source_sha256") == _sha256(raw_bytes),
             source_name + "_raw_hash_mismatch")
    _require(
        result.get("frozen_evidence_manifest", {}).get("trust", {}).get(
            "binding_status"
        ) == "UNBOUND",
        source_name + "_raw_evidence_not_unbound",
    )
    false_flags = (
        grid_adapter.CLAIM_CEILINGS
        if source_name == "starting_grid"
        else compatibility.ADAPTER_FALSE_FLAGS
    )
    for flag in false_flags:
        _require(result.get(flag) is False,
                 source_name + "_adapter_forbidden_claim:" + flag)
    if source_name == "starting_grid":
        for flag in (
            "source_session_classification_authenticated",
            "target_race_session_classification_authenticated",
            "producer_input_csv_is_target_race_scoped",
            "cross_session_join_authorized",
            "commercial_or_redistribution_permission_claimed",
        ):
            _require(result.get(flag) is False,
                     source_name + "_adapter_forbidden_claim:" + flag)
    return csv_bytes


def _receipt_metadata(receipt_bytes, *, result, raw_bytes, source_name, cutoff,
                      race_end):
    """Reuse canonical adapter validation, then enforce the new as-of ordering."""
    metadata = compatibility._receipt_metadata(
        receipt_bytes,
        result=result,
        raw_bytes=raw_bytes,
        source_name=source_name,
    )
    receipt = metadata["receipt"]
    payload = receipt["payload"]
    first = compatibility._parse_utc(
        payload.get("first_observed_utc"), source_name + "_first_observed_invalid"
    )
    ingested = compatibility._parse_utc(
        payload.get("ingested_utc"), source_name + "_ingested_invalid"
    )
    created = compatibility._parse_utc(
        receipt.get("receipt_created_utc"),
        source_name + "_receipt_created_invalid",
    )
    _require(first <= ingested <= created,
             source_name + "_receipt_time_order_invalid")
    _require(first <= race_end, source_name + "_first_observed_after_race")
    _require(first <= cutoff, source_name + "_first_observed_after_cutoff")
    _require(ingested <= cutoff, source_name + "_ingested_after_cutoff")
    _require(created <= cutoff, source_name + "_receipt_created_after_cutoff")
    return {
        **metadata,
        "ingested_utc": payload["ingested_utc"],
        "receipt_created_utc": receipt["receipt_created_utc"],
    }


def _csv_rows(csv_bytes, *, fields, reason):
    _require(type(csv_bytes) is bytes and bool(csv_bytes), reason)
    _require(b"\r" not in csv_bytes and csv_bytes.endswith(b"\n"), reason)
    try:
        reader = csv.DictReader(
            io.StringIO(csv_bytes.decode("utf-8"), newline=""), strict=True
        )
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CandidateInputError(reason) from exc
    _require(tuple(reader.fieldnames or ()) == fields and bool(rows), reason)
    for row in rows:
        _require(None not in row and tuple(row) == fields
                 and all(type(value) is str for value in row.values()), reason)
    return rows


def _driver_roster(drivers_csv):
    rows = _csv_rows(
        drivers_csv,
        fields=drivers_adapter.CSV_FIELDS,
        reason="drivers_derived_csv_invalid",
    )
    numbers = set()
    for row in rows:
        value = row["driver_number"]
        _require(compatibility.POSITIVE_DECIMAL.fullmatch(value),
                 "drivers_driver_number_invalid")
        number = int(value)
        _require(number not in numbers, "drivers_driver_number_duplicate")
        numbers.add(number)
    return rows, numbers


def _project_grid(original_grid_csv, *, event_id, meeting_id,
                  qualifying_source_session_id, expected_roster):
    try:
        return projection._project_grid(
            original_grid_csv,
            event_id=event_id,
            meeting_id=meeting_id,
            qualifying_source_session_id=qualifying_source_session_id,
            expected_roster=expected_roster,
        )
    except projection.ProjectionInputError as exc:
        raise CandidateInputError(str(exc) or "starting_grid_projection_invalid") from exc


def _candidate_manifest(*, event_id, meeting_id, practice_session_id,
                        qualifying_source_session_id, target_race_session_id,
                        cutoff_utc, runtime_inputs, runtime_ids):
    _require(set(runtime_inputs) == set(SOURCE_NAMES),
             "unexpected_runtime_input_set")
    _require(set(runtime_ids) == set(SOURCE_NAMES),
             "unexpected_runtime_identity_set")
    _require(len(set(runtime_ids.values())) == 3,
             "derived_runtime_identity_collision")
    sources = []
    for name in SOURCE_NAMES:
        identity = runtime_ids[name]
        _require(type(identity) is str and identity.startswith("derived:"),
                 "runtime_identity_not_derived")
        sources.append({
            "source_name": name,
            "source_id": identity,
            "relative_path": CANONICAL_FILENAMES[name],
            "source_sha256": _sha256(runtime_inputs[name]),
        })
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "classification": CLASSIFICATION,
        "sandbox_only": True,
        "approved_producer_authorization": False,
        "event_id": event_id,
        "meeting_id": meeting_id,
        "session_id": practice_session_id,
        "processor_scope": "PRACTICE_2_MECHANICS_ONLY",
        "qualifying_source_session_id": qualifying_source_session_id,
        "target_race_session_id": target_race_session_id,
        "forecast_cutoff_utc": cutoff_utc,
        "sources": sources,
    }


def assess_openf1_three_source_precutoff_candidate(
    *,
    weather_source_capture_receipt_bytes,
    raw_weather_response_bytes,
    drivers_source_capture_receipt_bytes,
    raw_drivers_response_bytes,
    starting_grid_source_capture_receipt_bytes,
    raw_starting_grid_response_bytes,
    sessions_response_bytes,
    grid_shadow_manifest_bytes,
    event_id,
    meeting_id,
    practice_session_id,
    qualifying_source_session_id,
    target_race_session_id,
    forecast_cutoff_utc,
    implementation_git_sha=None,
):
    """Return a non-operational pre-cutoff candidate or a minimal HOLD."""
    try:
        event = compatibility._text(event_id, "malformed_event_id")
        meeting = compatibility._positive_decimal(
            meeting_id, "malformed_meeting_id"
        )
        practice_id = compatibility._positive_decimal(
            practice_session_id, "malformed_practice_session_id"
        )
        qualifying_id = compatibility._positive_decimal(
            qualifying_source_session_id,
            "malformed_qualifying_source_session_id",
        )
        race_id = compatibility._positive_decimal(
            target_race_session_id, "malformed_target_race_session_id"
        )
        _require(len({practice_id, qualifying_id, race_id}) == 3,
                 "source_and_target_session_ids_not_distinct")
        cutoff = compatibility._parse_utc(
            forecast_cutoff_utc, "forecast_cutoff_invalid"
        )
        if implementation_git_sha is not None:
            _require(type(implementation_git_sha) is str
                     and HEX40.fullmatch(implementation_git_sha),
                     "implementation_git_sha_malformed")

        sessions = compatibility._strict_json_bytes(
            sessions_response_bytes,
            top_level=list,
            reason="session_discovery_malformed",
        )
        manifest = compatibility._strict_json_bytes(
            grid_shadow_manifest_bytes,
            top_level=dict,
            reason="grid_shadow_manifest_malformed",
        )
        practice, qualifying, race = compatibility._validate_sessions(
            sessions,
            event_id=event,
            meeting_id=meeting,
            practice_session_id=practice_id,
            qualifying_source_session_id=qualifying_id,
            target_race_session_id=race_id,
        )
        _require(cutoff > qualifying["end"],
                 "forecast_cutoff_not_after_qualifying_end")
        _require(cutoff < race["start"],
                 "forecast_cutoff_not_before_race_start")

        practice_scope = {
            "event_id": event,
            "meeting_id": meeting,
            "session_id": practice_id,
        }
        qualifying_scope = {
            "event_id": event,
            "meeting_id": meeting,
            "session_id": qualifying_id,
        }
        weather_result = weather_adapter.adapt_openf1_weather_to_producer_input(
            source_capture_receipt_bytes=weather_source_capture_receipt_bytes,
            raw_weather_response_bytes=raw_weather_response_bytes,
            **practice_scope,
        )
        drivers_result = drivers_adapter.adapt_openf1_drivers_to_producer_input(
            source_capture_receipt_bytes=drivers_source_capture_receipt_bytes,
            raw_drivers_response_bytes=raw_drivers_response_bytes,
            **practice_scope,
        )
        grid_result = grid_adapter.adapt_openf1_starting_grid_to_producer_input(
            source_capture_receipt_bytes=starting_grid_source_capture_receipt_bytes,
            raw_starting_grid_response_bytes=raw_starting_grid_response_bytes,
            source_session_kind="Qualifying",
            target_race_session_id=race_id,
            **qualifying_scope,
        )
        weather_csv = _adapter_csv(
            weather_result,
            expected_status=weather_adapter.VALIDATED,
            source_name="weather",
            scope=practice_scope,
            raw_bytes=raw_weather_response_bytes,
        )
        drivers_csv = _adapter_csv(
            drivers_result,
            expected_status=drivers_adapter.VALIDATED,
            source_name="drivers",
            scope=practice_scope,
            raw_bytes=raw_drivers_response_bytes,
        )
        original_grid_csv = _adapter_csv(
            grid_result,
            expected_status=grid_adapter.VALIDATED,
            source_name="starting_grid",
            scope=qualifying_scope,
            raw_bytes=raw_starting_grid_response_bytes,
        )
        _require(
            grid_result.get("source_qualifying_session_id") == qualifying_id
            and grid_result.get("target_race_session_id") == race_id
            and grid_result.get("source_session_kind") == "Qualifying"
            and grid_result.get("target_session_kind") == "Race",
            "starting_grid_lineage_scope_mismatch",
        )

        weather_receipt = _receipt_metadata(
            weather_source_capture_receipt_bytes,
            result=weather_result,
            raw_bytes=raw_weather_response_bytes,
            source_name="weather",
            cutoff=cutoff,
            race_end=race["end"],
        )
        drivers_receipt = _receipt_metadata(
            drivers_source_capture_receipt_bytes,
            result=drivers_result,
            raw_bytes=raw_drivers_response_bytes,
            source_name="drivers",
            cutoff=cutoff,
            race_end=race["end"],
        )
        grid_receipt = _receipt_metadata(
            starting_grid_source_capture_receipt_bytes,
            result=grid_result,
            raw_bytes=raw_starting_grid_response_bytes,
            source_name="starting_grid",
            cutoff=cutoff,
            race_end=race["end"],
        )
        receipts = (weather_receipt, drivers_receipt, grid_receipt)
        _require(len({item["receipt_id"] for item in receipts}) == 3,
                 "duplicate_source_receipt_identity")
        _require(len({item["source_id"] for item in receipts}) == 3,
                 "duplicate_raw_source_identity")

        sessions_sha = _sha256(sessions_response_bytes)
        compatibility._validate_grid_manifest(
            manifest,
            sessions_sha=sessions_sha,
            grid_sha=grid_receipt["raw_sha256"],
            grid_receipt=grid_receipt,
            event_id=event,
            meeting_id=meeting,
            qualifying_source_session_id=qualifying_id,
            target_race_session_id=race_id,
        )

        driver_rows, roster = _driver_roster(drivers_csv)
        projected_grid_csv = _project_grid(
            original_grid_csv,
            event_id=event,
            meeting_id=meeting,
            qualifying_source_session_id=qualifying_id,
            expected_roster=roster,
        )
        _require(len(driver_rows) == grid_result.get("row_count")
                 == grid_result.get("unique_driver_count")
                 == grid_result.get("slot_count"),
                 "three_source_driver_count_mismatch")

        projected_grid_sha = _sha256(projected_grid_csv)
        runtime_inputs = {
            "weather": weather_csv,
            "drivers": drivers_csv,
            "starting_grid": projected_grid_csv,
        }
        runtime_ids = {
            "weather": "derived:openf1-weather-csv:"
                       + weather_result["producer_input_sha256"],
            "drivers": drivers_result["derived_runtime_identity"],
            "starting_grid": (
                "derived:precutoff-unscoped-qualifying-grid-projection:"
                + projected_grid_sha
            ),
        }
        _require(len(set(runtime_ids.values())) == 3,
                 "derived_runtime_identity_collision")
        forbidden_identities = {
            item[field]
            for item in receipts
            for field in ("receipt_id", "source_id")
        }
        _require(set(runtime_ids.values()).isdisjoint(forbidden_identities),
                 "source_and_runtime_identity_collision")
        _require(runtime_ids["starting_grid"]
                 != grid_result.get("derived_runtime_identity"),
                 "grid_projection_identity_collision")

        candidate_manifest = _candidate_manifest(
            event_id=event,
            meeting_id=meeting,
            practice_session_id=practice_id,
            qualifying_source_session_id=qualifying_id,
            target_race_session_id=race_id,
            cutoff_utc=forecast_cutoff_utc,
            runtime_inputs=runtime_inputs,
            runtime_ids=runtime_ids,
        )
        candidate_manifest_bytes = _canonical_json_bytes(candidate_manifest)
        source_lineage = {
            "weather": {
                "source_receipt_id": weather_receipt["receipt_id"],
                "raw_source_id": weather_receipt["source_id"],
                "raw_source_sha256": weather_receipt["raw_sha256"],
                "original_session_id": practice_id,
                "original_derived_csv_sha256": weather_result[
                    "producer_input_sha256"
                ],
            },
            "drivers": {
                "source_receipt_id": drivers_receipt["receipt_id"],
                "raw_source_id": drivers_receipt["source_id"],
                "raw_source_sha256": drivers_receipt["raw_sha256"],
                "original_session_id": practice_id,
                "original_derived_csv_sha256": drivers_result[
                    "producer_input_sha256"
                ],
            },
            "starting_grid": {
                "source_receipt_id": grid_receipt["receipt_id"],
                "raw_source_id": grid_receipt["source_id"],
                "raw_source_sha256": grid_receipt["raw_sha256"],
                "original_session_id": qualifying_id,
                "target_race_session_id": race_id,
                "original_five_column_csv_sha256": grid_result[
                    "producer_input_sha256"
                ],
                "projected_two_column_csv_sha256": projected_grid_sha,
            },
        }
        source_timing = {
            name: {
                "first_observed_utc": receipt["first_observed_utc"],
                "ingested_utc": receipt["ingested_utc"],
                "receipt_created_utc": receipt["receipt_created_utc"],
            }
            for name, receipt in (
                ("weather", weather_receipt),
                ("drivers", drivers_receipt),
                ("starting_grid", grid_receipt),
            )
        }
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": VALIDATED,
            "reason_codes": [],
            "classification": CLASSIFICATION,
            "event_id": event,
            "meeting_id": meeting,
            "forecast_cutoff_utc": forecast_cutoff_utc,
            "practice_session": {
                "session_id": practice_id,
                "session_type": "Practice",
                "session_name": "Practice 2",
                "start_utc": practice["start_utc"],
                "end_utc": practice["end_utc"],
            },
            "qualifying_source_session": {
                "session_id": qualifying_id,
                "session_type": "Qualifying",
                "session_name": "Qualifying",
                "start_utc": qualifying["start_utc"],
                "end_utc": qualifying["end_utc"],
            },
            "target_race_session": {
                "session_id": race_id,
                "session_type": "Race",
                "session_name": "Race",
                "start_utc": race["start_utc"],
                "end_utc": race["end_utc"],
            },
            "source_to_target_link_evidence_type": compatibility.PROVIDER_LINK,
            "source_timing": source_timing,
            "original_source_lineage": source_lineage,
            "runtime_input_csv_bytes": runtime_inputs,
            "runtime_input_metadata": {
                name: {
                    "filename": CANONICAL_FILENAMES[name],
                    "derived_runtime_identity": runtime_ids[name],
                    "sha256": _sha256(runtime_inputs[name]),
                    "row_count": (
                        len(driver_rows)
                        if name != "weather"
                        else weather_result["row_count"]
                    ),
                }
                for name in SOURCE_NAMES
            },
            "candidate_manifest": candidate_manifest,
            "candidate_manifest_bytes": candidate_manifest_bytes,
            "candidate_manifest_sha256": _sha256(candidate_manifest_bytes),
            "candidate_manifest_is_sandbox_only": True,
            "candidate_is_approved_producer_authorization": False,
            "internal_temporal_checks_satisfied": True,
            **{flag: False for flag in FALSE_FLAGS},
        }
        if implementation_git_sha is not None:
            result["implementation_git_sha"] = implementation_git_sha
        return result
    except (
        CandidateInputError,
        compatibility.CompatibilityInputError,
        projection.ProjectionInputError,
        TypeError,
        ValueError,
        KeyError,
        UnicodeDecodeError,
        OverflowError,
        AttributeError,
        csv.Error,
    ) as exc:
        return _hold(str(exc) or type(exc).__name__)
