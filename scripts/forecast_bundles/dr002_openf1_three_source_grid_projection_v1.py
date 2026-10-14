"""Pure offline projection of compatible OpenF1 sources for P2 mechanics.

The Qualifying starting-grid evidence remains scoped to its original session.
Only a separate two-column, unscoped runtime view is projected for a possible
future sandbox producer experiment.  This module performs no I/O, discovery,
network access, clock observation, subprocess execution, producer invocation,
or model invocation.
"""
import csv
import hashlib
import io
import json
import re

import dr002_openf1_drivers_producer_adapter_v1 as drivers_adapter
import dr002_openf1_starting_grid_producer_adapter_v1 as grid_adapter
import dr002_openf1_three_source_event_compatibility_v1 as compatibility
import dr002_openf1_weather_producer_adapter_v1 as weather_adapter


SCHEMA_VERSION = "dr002-openf1-three-source-grid-projection-v1"
FROZEN_SCHEMA = "dr002-frozen-producer-input-v1"
VALIDATED = (
    "OPENF1_THREE_SOURCE_PRODUCER_INPUT_PROJECTION_VALIDATED_"
    "POST_EVENT_SANDBOX_PROJECTION_ONLY_NOT_A_PREDICTION"
)
CLASSIFICATION = "POST_EVENT_SANDBOX_PROJECTION_ONLY_NOT_A_PREDICTION"
HOLD = "HOLD"
GRID_FIELDS = (
    "driver_number", "position", "event_id", "meeting_id", "session_id"
)
PROJECTED_GRID_FIELDS = ("driver_number", "position")
SOURCE_NAMES = ("drivers", "starting_grid", "weather")
POSITIVE_DECIMAL = re.compile(r"[1-9][0-9]*")
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
FALSE_FLAGS = (
    "approved_frozen_evidence_manifest_created",
    "blind_validation_eligible",
    "commercial_or_redistribution_permission_claimed",
    "cross_session_producer_join_authorized",
    "derived_projection_is_source_evidence",
    "dr002_activated",
    "forecast_generated",
    "historical_pre_race_availability_proven",
    "model_execution_attempted",
    "new_scientific_receipt_created",
    "normalization_receipt_created",
    "official_fia_final_grid_authenticated",
    "predictive_accuracy_measured",
    "producer_execution_attempted",
    "production_forecast_generated",
    "promotion_allowed",
    "source_session_classification_authenticated",
    "stable_engine_execution_proven",
    "target_race_session_classification_authenticated",
    "verified_receipt_bindings_created",
)


class ProjectionInputError(ValueError):
    """Any failed invariant makes the complete projection HOLD."""


def _require(condition, reason):
    if not condition:
        raise ProjectionInputError(reason)


def _sha256(data):
    _require(type(data) is bytes, "hash_input_not_bytes")
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value):
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProjectionInputError("candidate_manifest_not_canonical_json") from exc


def _hold(reason):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HOLD,
        "reason_codes": [reason],
        **{flag: False for flag in FALSE_FLAGS},
    }


def _require_compatibility(result, *, event_id, meeting_id, practice_session_id,
                           qualifying_source_session_id,
                           target_race_session_id):
    _require(type(result) is dict, "k4r21_result_malformed")
    if result.get("status") != compatibility.VALIDATED:
        reasons = result.get("reason_codes")
        reason = reasons[0] if type(reasons) is list and reasons else "unspecified"
        raise ProjectionInputError("k4r21_hold:" + str(reason))
    _require(
        result.get("classification")
        == "POST_EVENT_MECHANICS_ONLY_NOT_A_PREDICTION",
        "k4r21_classification_mismatch",
    )
    _require(result.get("event_id") == event_id, "k4r21_event_mismatch")
    _require(result.get("meeting_id") == meeting_id, "k4r21_meeting_mismatch")
    expected_sessions = (
        ("practice_session", practice_session_id, "Practice", "Practice 2"),
        ("qualifying_source_session", qualifying_source_session_id,
         "Qualifying", "Qualifying"),
        ("target_race_session", target_race_session_id, "Race", "Race"),
    )
    for field, session_id, kind, name in expected_sessions:
        session = result.get(field)
        _require(type(session) is dict, "k4r21_session_metadata_missing:" + field)
        _require(
            session.get("session_id") == session_id
            and session.get("session_type") == kind
            and session.get("session_name") == name,
            "k4r21_session_metadata_mismatch:" + field,
        )
    _require(
        result.get("source_to_target_link_evidence_type")
        == compatibility.PROVIDER_LINK,
        "k4r21_source_target_link_mismatch",
    )
    _require(result.get("event_level_compatibility_assessed") is True,
             "k4r21_event_compatibility_not_assessed")
    _require(result.get("source_receipts_remain_distinct") is True,
             "k4r21_source_receipts_not_distinct")
    _require(result.get("combined_frozen_producer_manifest_created") is False,
             "k4r21_forbidden_manifest_claim")
    for flag in compatibility.COMMON_FALSE_FLAGS:
        _require(result.get(flag) is False, "k4r21_forbidden_claim:" + flag)


def _adapter_result(result, *, expected_status, source_name, filename, scope,
                    compatible_metadata, raw_bytes):
    _require(type(result) is dict, source_name + "_adapter_result_malformed")
    if result.get("status") != expected_status:
        reasons = result.get("reason_codes")
        reason = reasons[0] if type(reasons) is list and reasons else "unspecified"
        raise ProjectionInputError(source_name + "_adapter_hold:" + str(reason))
    _require(result.get("scope") == scope, source_name + "_adapter_scope_mismatch")
    _require(
        result.get("producer_input_source_name") == source_name
        and result.get("producer_input_filename") == filename,
        source_name + "_adapter_output_identity_mismatch",
    )
    csv_bytes = result.get("producer_input_csv_bytes")
    digest = result.get("producer_input_sha256")
    _require(type(csv_bytes) is bytes and bool(csv_bytes),
             source_name + "_adapter_csv_missing")
    _require(type(digest) is str and HEX64.fullmatch(digest)
             and _sha256(csv_bytes) == digest,
             source_name + "_adapter_csv_hash_mismatch")
    _require(digest == compatible_metadata.get("derived_csv_sha256"),
             source_name + "_k4r21_derived_hash_mismatch")
    _require(result.get("row_count") == compatible_metadata.get("row_count"),
             source_name + "_k4r21_row_count_mismatch")
    _require(result.get("source_receipt_id")
             == compatible_metadata.get("source_receipt_id"),
             source_name + "_k4r21_receipt_mismatch")
    _require(result.get("raw_source_sha256") == _sha256(raw_bytes)
             == compatible_metadata.get("raw_source_sha256"),
             source_name + "_k4r21_raw_hash_mismatch")
    _require(
        result.get("frozen_evidence_manifest", {}).get("trust", {}).get(
            "binding_status"
        ) == "UNBOUND",
        source_name + "_raw_evidence_not_unbound",
    )
    adapter_false_flags = (
        grid_adapter.CLAIM_CEILINGS
        if source_name == "starting_grid"
        else compatibility.ADAPTER_FALSE_FLAGS
    )
    for flag in adapter_false_flags:
        _require(result.get(flag) is False,
                 source_name + "_adapter_forbidden_claim:" + flag)
    return csv_bytes


def _positive_csv_value(value, reason):
    _require(type(value) is str and POSITIVE_DECIMAL.fullmatch(value), reason)
    return int(value)


def _csv_rows(csv_bytes, *, fields, reason):
    _require(type(csv_bytes) is bytes and bool(csv_bytes), reason)
    _require(b"\r" not in csv_bytes and csv_bytes.endswith(b"\n"), reason)
    try:
        text = csv_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ProjectionInputError(reason) from exc
    _require(tuple(reader.fieldnames or ()) == fields, reason)
    _require(bool(rows), reason)
    for row in rows:
        _require(None not in row and tuple(row) == fields
                 and all(type(value) is str for value in row.values()), reason)
    return rows


def _driver_roster(drivers_csv):
    rows = _csv_rows(
        drivers_csv, fields=drivers_adapter.CSV_FIELDS,
        reason="drivers_derived_csv_invalid",
    )
    numbers = set()
    for row in rows:
        number = _positive_csv_value(
            row["driver_number"], "drivers_driver_number_invalid"
        )
        _require(number not in numbers, "drivers_driver_number_duplicate")
        numbers.add(number)
    return rows, numbers


def _project_grid(grid_csv, *, event_id, meeting_id,
                  qualifying_source_session_id, expected_roster):
    rows = _csv_rows(
        grid_csv, fields=GRID_FIELDS, reason="starting_grid_derived_csv_invalid"
    )
    records = []
    positions = set()
    numbers = set()
    for row in rows:
        _require(row["event_id"] == event_id,
                 "starting_grid_event_scope_mismatch")
        _require(row["meeting_id"] == meeting_id,
                 "starting_grid_meeting_scope_mismatch")
        _require(row["session_id"] == qualifying_source_session_id,
                 "starting_grid_qualifying_scope_mismatch")
        number = _positive_csv_value(
            row["driver_number"], "starting_grid_driver_number_invalid"
        )
        position = _positive_csv_value(
            row["position"], "starting_grid_position_invalid"
        )
        _require(number not in numbers, "starting_grid_driver_number_duplicate")
        _require(position not in positions, "starting_grid_position_duplicate")
        numbers.add(number)
        positions.add(position)
        records.append((position, number))
    _require(positions == set(range(1, len(records) + 1)),
             "starting_grid_slots_not_contiguous")
    _require(numbers == expected_roster, "drivers_and_grid_roster_mismatch")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(PROJECTED_GRID_FIELDS)
    for position, number in sorted(records):
        writer.writerow((number, position))
    projected = stream.getvalue().encode("utf-8")
    _require(b"event_id" not in projected and b"meeting_id" not in projected
             and b"session_id" not in projected and b"session_key" not in projected,
             "projected_grid_retains_scope_columns")
    return projected


def _build_candidate_manifest(*, event_id, meeting_id, practice_session_id,
                              runtime_inputs, runtime_ids):
    _require(set(runtime_inputs) == set(SOURCE_NAMES),
             "unexpected_runtime_input_set")
    _require(set(runtime_ids) == set(SOURCE_NAMES),
             "unexpected_runtime_identity_set")
    _require(len(set(runtime_ids.values())) == len(SOURCE_NAMES),
             "derived_runtime_identity_collision")
    for identity in runtime_ids.values():
        _require(type(identity) is str and identity.startswith("derived:"),
                 "runtime_identity_not_derived")
    sources = []
    for source_name in SOURCE_NAMES:
        sources.append({
            "source_name": source_name,
            "source_id": runtime_ids[source_name],
            "relative_path": source_name + ".csv",
            "source_sha256": _sha256(runtime_inputs[source_name]),
        })
    return {
        "schema_version": FROZEN_SCHEMA,
        "event_id": event_id,
        "meeting_id": meeting_id,
        "session_id": practice_session_id,
        "sources": sources,
    }


def project_compatible_openf1_three_sources_for_p2_mechanics(
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
    implementation_git_sha=None,
):
    """Return a scope-safe, in-memory sandbox candidate or a minimal HOLD."""
    try:
        compatibility_result = (
            compatibility.assess_openf1_three_source_event_compatibility(
                weather_source_capture_receipt_bytes=(
                    weather_source_capture_receipt_bytes
                ),
                raw_weather_response_bytes=raw_weather_response_bytes,
                drivers_source_capture_receipt_bytes=(
                    drivers_source_capture_receipt_bytes
                ),
                raw_drivers_response_bytes=raw_drivers_response_bytes,
                starting_grid_source_capture_receipt_bytes=(
                    starting_grid_source_capture_receipt_bytes
                ),
                raw_starting_grid_response_bytes=raw_starting_grid_response_bytes,
                sessions_response_bytes=sessions_response_bytes,
                grid_shadow_manifest_bytes=grid_shadow_manifest_bytes,
                event_id=event_id,
                meeting_id=meeting_id,
                practice_session_id=practice_session_id,
                qualifying_source_session_id=qualifying_source_session_id,
                target_race_session_id=target_race_session_id,
                implementation_git_sha=implementation_git_sha,
            )
        )
        _require_compatibility(
            compatibility_result,
            event_id=event_id,
            meeting_id=meeting_id,
            practice_session_id=practice_session_id,
            qualifying_source_session_id=qualifying_source_session_id,
            target_race_session_id=target_race_session_id,
        )
        if implementation_git_sha is not None:
            _require(type(implementation_git_sha) is str
                     and HEX40.fullmatch(implementation_git_sha),
                     "implementation_git_sha_malformed")

        practice_scope = {
            "event_id": event_id,
            "meeting_id": meeting_id,
            "session_id": practice_session_id,
        }
        qualifying_scope = {
            "event_id": event_id,
            "meeting_id": meeting_id,
            "session_id": qualifying_source_session_id,
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
            target_race_session_id=target_race_session_id,
            **qualifying_scope,
        )
        weather_csv = _adapter_result(
            weather_result,
            expected_status=weather_adapter.VALIDATED,
            source_name="weather",
            filename="weather.csv",
            scope=practice_scope,
            compatible_metadata=compatibility_result["weather"],
            raw_bytes=raw_weather_response_bytes,
        )
        drivers_csv = _adapter_result(
            drivers_result,
            expected_status=drivers_adapter.VALIDATED,
            source_name="drivers",
            filename="drivers.csv",
            scope=practice_scope,
            compatible_metadata=compatibility_result["drivers"],
            raw_bytes=raw_drivers_response_bytes,
        )
        original_grid_csv = _adapter_result(
            grid_result,
            expected_status=grid_adapter.VALIDATED,
            source_name="starting_grid",
            filename="starting_grid.csv",
            scope=qualifying_scope,
            compatible_metadata=compatibility_result["starting_grid"],
            raw_bytes=raw_starting_grid_response_bytes,
        )
        _require(
            grid_result.get("source_qualifying_session_id")
            == qualifying_source_session_id
            and grid_result.get("target_race_session_id")
            == target_race_session_id
            and grid_result.get("source_session_kind") == "Qualifying"
            and grid_result.get("target_session_kind") == "Race",
            "starting_grid_lineage_scope_mismatch",
        )
        for flag in grid_adapter.CLAIM_CEILINGS:
            _require(grid_result.get(flag) is False,
                     "starting_grid_adapter_forbidden_claim:" + flag)

        driver_rows, roster = _driver_roster(drivers_csv)
        projected_grid_csv = _project_grid(
            original_grid_csv,
            event_id=event_id,
            meeting_id=meeting_id,
            qualifying_source_session_id=qualifying_source_session_id,
            expected_roster=roster,
        )
        _require(len(driver_rows) == grid_result.get("row_count"),
                 "drivers_and_grid_row_count_mismatch")

        projected_grid_sha = _sha256(projected_grid_csv)
        projected_grid_id = (
            "derived:postevent-unscoped-qualifying-grid-projection:"
            + projected_grid_sha
        )
        runtime_inputs = {
            "weather": weather_csv,
            "drivers": drivers_csv,
            "starting_grid": projected_grid_csv,
        }
        runtime_ids = {
            "weather": (
                "derived:openf1-weather-csv:"
                + weather_result["producer_input_sha256"]
            ),
            "drivers": drivers_result["derived_runtime_identity"],
            "starting_grid": projected_grid_id,
        }
        forbidden_identities = {
            compatibility_result[name][field]
            for name in ("weather", "drivers", "starting_grid")
            for field in ("source_receipt_id", "raw_source_id")
        }
        _require(set(runtime_ids.values()).isdisjoint(forbidden_identities),
                 "source_and_runtime_identity_collision")
        _require(
            projected_grid_id
            != compatibility_result["starting_grid"]["derived_runtime_identity"],
            "grid_projection_identity_collision",
        )

        manifest = _build_candidate_manifest(
            event_id=event_id,
            meeting_id=meeting_id,
            practice_session_id=practice_session_id,
            runtime_inputs=runtime_inputs,
            runtime_ids=runtime_ids,
        )
        manifest_bytes = _canonical_json_bytes(manifest)
        input_metadata = {
            name: {
                "filename": name + ".csv",
                "derived_runtime_identity": runtime_ids[name],
                "sha256": _sha256(runtime_inputs[name]),
                "row_count": (
                    compatibility_result["starting_grid"]["row_count"]
                    if name == "starting_grid"
                    else compatibility_result[name]["row_count"]
                ),
            }
            for name in ("weather", "drivers", "starting_grid")
        }
        source_lineage = {
            "weather": {
                "source_receipt_id": compatibility_result["weather"][
                    "source_receipt_id"
                ],
                "raw_source_id": compatibility_result["weather"]["raw_source_id"],
                "raw_source_sha256": compatibility_result["weather"][
                    "raw_source_sha256"
                ],
                "original_session_id": practice_session_id,
                "original_derived_csv_sha256": weather_result[
                    "producer_input_sha256"
                ],
            },
            "drivers": {
                "source_receipt_id": compatibility_result["drivers"][
                    "source_receipt_id"
                ],
                "raw_source_id": compatibility_result["drivers"]["raw_source_id"],
                "raw_source_sha256": compatibility_result["drivers"][
                    "raw_source_sha256"
                ],
                "original_session_id": practice_session_id,
                "original_derived_csv_sha256": drivers_result[
                    "producer_input_sha256"
                ],
            },
            "starting_grid": {
                "source_receipt_id": compatibility_result["starting_grid"][
                    "source_receipt_id"
                ],
                "raw_source_id": compatibility_result["starting_grid"][
                    "raw_source_id"
                ],
                "raw_source_sha256": compatibility_result["starting_grid"][
                    "raw_source_sha256"
                ],
                "original_session_id": qualifying_source_session_id,
                "original_derived_csv_sha256": grid_result[
                    "producer_input_sha256"
                ],
                "original_derived_runtime_identity": grid_result[
                    "derived_runtime_identity"
                ],
            },
        }
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": VALIDATED,
            "reason_codes": [],
            "classification": CLASSIFICATION,
            "event_id": event_id,
            "meeting_id": meeting_id,
            "practice_session": compatibility_result["practice_session"],
            "qualifying_source_session": compatibility_result[
                "qualifying_source_session"
            ],
            "target_race_session": compatibility_result["target_race_session"],
            "source_to_target_link_evidence_type": compatibility.PROVIDER_LINK,
            "producer_scoped_session_id": practice_session_id,
            "producer_scope_is_p2_mechanics_only": True,
            "original_source_lineage": source_lineage,
            "original_qualifying_grid_csv_sha256": grid_result[
                "producer_input_sha256"
            ],
            "projected_grid_csv_sha256": projected_grid_sha,
            "projected_grid_runtime_identity": projected_grid_id,
            "projection_reason": (
                "Drop event_id, meeting_id, and Qualifying session_id only from "
                "the additional mechanics runtime view so the original "
                "Qualifying evidence remains truthful while no source session "
                "is relabelled as Practice 2 or Race."
            ),
            "runtime_input_csv_bytes": runtime_inputs,
            "runtime_input_metadata": input_metadata,
            "candidate_producer_manifest": manifest,
            "candidate_producer_manifest_bytes": manifest_bytes,
            "candidate_producer_manifest_sha256": _sha256(manifest_bytes),
            "candidate_manifest_is_sandbox_only": True,
            "source_receipts_remain_distinct": True,
            **{flag: False for flag in FALSE_FLAGS},
        }
        if implementation_git_sha is not None:
            result["implementation_git_sha"] = implementation_git_sha
        return result
    except (
        ProjectionInputError,
        TypeError,
        ValueError,
        KeyError,
        UnicodeDecodeError,
        OverflowError,
        AttributeError,
        csv.Error,
    ) as exc:
        return _hold(str(exc) or type(exc).__name__)
