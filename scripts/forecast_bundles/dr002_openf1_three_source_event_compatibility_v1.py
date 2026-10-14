"""Pure OpenF1 three-source event and temporal compatibility assessment.

This module validates caller-supplied, in-memory historical evidence only.  It
does not discover artifacts, access a provider, read files, observe a clock,
create a receipt or frozen producer manifest, or invoke a producer/model.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import re

import dr002_openf1_drivers_producer_adapter_v1 as drivers_adapter
import dr002_openf1_historical_rest_capture_v1 as capture_contract
import dr002_openf1_starting_grid_producer_adapter_v1 as grid_adapter
import dr002_openf1_weather_producer_adapter_v1 as weather_adapter


SCHEMA_VERSION = "dr002-openf1-three-source-event-compatibility-v1"
VALIDATED = (
    "OPENF1_THREE_SOURCE_EVENT_COMPATIBILITY_VALIDATED_"
    "POST_EVENT_MECHANICS_ONLY_NOT_A_PREDICTION"
)
HOLD = "HOLD"
PROVIDER_LINK = "OPENF1_PROVIDER_DISCOVERY_CLAIM"
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")
POSITIVE_DECIMAL = re.compile(r"[1-9][0-9]*")
UTC_TEXT = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)"
)
COMMON_FALSE_FLAGS = (
    "cross_session_producer_join_authorized",
    "producer_execution_attempted",
    "historical_pre_race_availability_proven",
    "official_fia_final_grid_authenticated",
    "blind_validation_eligible",
    "dr002_activated",
    "promotion_allowed",
    "new_scientific_receipt_created",
    "verified_receipt_bindings_created",
    "stable_engine_execution_proven",
    "production_forecast_generated",
)
ADAPTER_FALSE_FLAGS = (
    "derived_csv_is_source_evidence",
    "new_scientific_receipt_created",
    "normalization_receipt_created",
    "verified_receipt_bindings_created",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "production_forecast_generated",
    "dr002_activated",
    "promotion_allowed",
)


class CompatibilityInputError(ValueError):
    """Any validation error makes the complete assessment HOLD."""


def _require(condition, reason):
    if not condition:
        raise CompatibilityInputError(reason)


def _text(value, reason):
    _require(type(value) is str and value and value.strip() == value, reason)
    _require(not any(ord(char) < 32 or ord(char) == 127 for char in value), reason)
    return value


def _positive_decimal(value, reason):
    _require(type(value) is str and POSITIVE_DECIMAL.fullmatch(value), reason)
    return value


def _strict_json_bytes(data, *, top_level, reason):
    _require(type(data) is bytes and bool(data), reason)

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def reject_constant(_value):
        raise CompatibilityInputError("nonfinite_json")

    try:
        parsed = json.loads(
            data,
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except CompatibilityInputError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise CompatibilityInputError(reason) from exc
    _require(type(parsed) is top_level, reason)
    return parsed


def _sha256(data):
    _require(type(data) is bytes, "hash_input_not_bytes")
    return hashlib.sha256(data).hexdigest()


def _parse_utc(value, reason):
    _require(type(value) is str and UTC_TEXT.fullmatch(value), reason)
    parseable = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise CompatibilityInputError(reason) from exc
    _require(
        parsed.tzinfo is not None
        and parsed.utcoffset() is not None
        and parsed.utcoffset().total_seconds() == 0,
        reason,
    )
    return parsed


def _scope_value(value, expected, reason):
    if type(value) is int:
        _require(value > 0 and str(value) == expected, reason)
    elif type(value) is str:
        _require(value == expected and POSITIVE_DECIMAL.fullmatch(value), reason)
    else:
        raise CompatibilityInputError(reason)


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _not_cancelled(row, reason):
    for field in ("cancelled", "canceled", "is_cancelled", "is_canceled"):
        if field in row:
            _require(row[field] is False, reason)
    for field in ("status", "session_status"):
        if field in row:
            status = _text(row[field], reason).lower()
            _require(status not in {"cancelled", "canceled"}, reason)


def _session_identity(row, *, session_id, meeting_id, name, kind, reason):
    _require(type(row) is dict, reason)
    _scope_value(row.get("session_key"), session_id, reason)
    _scope_value(row.get("meeting_key"), meeting_id, reason)
    _require(row.get("session_name") == name and row.get("session_type") == kind,
             reason)
    _not_cancelled(row, reason + "_cancelled")
    year = _positive_decimal(str(row.get("year")), reason)
    country = _text(row.get("country_name"), reason)
    location = _text(row.get("location"), reason)
    circuit = _text(row.get("circuit_short_name"), reason)
    start = _parse_utc(row.get("date_start"), reason)
    end = _parse_utc(row.get("date_end"), reason)
    _require(start < end, reason + "_chronology")
    return {
        "session_id": session_id,
        "session_name": name,
        "session_type": kind,
        "year": year,
        "country_name": country,
        "location": location,
        "circuit_short_name": circuit,
        "start": start,
        "end": end,
        "start_utc": row["date_start"],
        "end_utc": row["date_end"],
    }


def _matching_session_rows(sessions, session_id):
    matches = []
    for row in sessions:
        _require(type(row) is dict, "malformed_session_discovery_row")
        value = row.get("session_key")
        if (type(value) is int and value > 0 and str(value) == session_id) or (
            type(value) is str and value == session_id
        ):
            matches.append(row)
    return matches


def _validate_sessions(
    sessions, *, event_id, meeting_id, practice_session_id,
    qualifying_source_session_id, target_race_session_id,
):
    _require(bool(sessions), "empty_session_discovery")
    ids = []
    for row in sessions:
        _require(type(row) is dict, "malformed_session_discovery_row")
        value = row.get("session_key")
        if type(value) is int:
            _require(value > 0, "malformed_discovery_session_id")
            normalized = str(value)
        else:
            normalized = _positive_decimal(
                value, "malformed_discovery_session_id"
            )
        _require(normalized not in ids, "duplicate_discovery_session_id")
        ids.append(normalized)

    selected = []
    for session_id, name, kind, reason in (
        (practice_session_id, "Practice 2", "Practice", "practice_session_invalid"),
        (qualifying_source_session_id, "Qualifying", "Qualifying",
         "qualifying_session_invalid"),
        (target_race_session_id, "Race", "Race", "target_race_session_invalid"),
    ):
        matches = _matching_session_rows(sessions, session_id)
        _require(len(matches) == 1, reason + "_not_unique")
        selected.append(_session_identity(
            matches[0], session_id=session_id, meeting_id=meeting_id,
            name=name, kind=kind, reason=reason,
        ))

    practice, qualifying, race = selected
    event_tuple = (
        practice["year"], practice["country_name"], practice["location"],
        practice["circuit_short_name"],
    )
    _require(
        all((item["year"], item["country_name"], item["location"],
             item["circuit_short_name"]) == event_tuple
            for item in (qualifying, race)),
        "cross_event_session_identity_mismatch",
    )
    expected_event_id = "_".join((
        practice["year"], meeting_id, _slug(practice["country_name"]),
        _slug(practice["location"]), _slug(practice["circuit_short_name"]),
    ))
    _require(event_id == expected_event_id, "event_id_discovery_mismatch")
    _require(
        practice["end"] < qualifying["start"] < qualifying["end"]
        < race["start"] < race["end"],
        "session_chronology_invalid",
    )

    same_meeting = []
    for row in sessions:
        meeting_value = row.get("meeting_key")
        if ((type(meeting_value) is int and meeting_value > 0
             and str(meeting_value) == meeting_id)
                or (type(meeting_value) is str and meeting_value == meeting_id)):
            same_meeting.append(row)
    for row in same_meeting:
        name = row.get("session_name")
        kind = row.get("session_type")
        _require(
            not ((type(name) is str and "Sprint" in name)
                 or (type(kind) is str and "Sprint" in kind)),
            "sprint_weekend_not_supported",
        )
    qualifying_rows = [row for row in same_meeting
                       if row.get("session_name") == "Qualifying"
                       or row.get("session_type") == "Qualifying"]
    race_rows = [row for row in same_meeting
                 if row.get("session_name") == "Race"
                 or row.get("session_type") == "Race"]
    _require(len(qualifying_rows) == 1, "qualifying_session_ambiguous")
    _require(len(race_rows) == 1, "target_race_session_ambiguous")
    return practice, qualifying, race


def _validated_adapter(result, *, expected_status, source_name, scope):
    _require(type(result) is dict, source_name + "_adapter_result_malformed")
    if result.get("status") != expected_status:
        reasons = result.get("reason_codes")
        reason = reasons[0] if type(reasons) is list and reasons else "unspecified"
        raise CompatibilityInputError(source_name + "_adapter_hold:" + str(reason))
    _require(result.get("scope") == scope, source_name + "_adapter_scope_mismatch")
    data = result.get("producer_input_csv_bytes")
    digest = result.get("producer_input_sha256")
    _require(type(data) is bytes and bool(data), source_name + "_derived_csv_missing")
    _require(type(digest) is str and HEX64.fullmatch(digest)
             and _sha256(data) == digest, source_name + "_derived_hash_mismatch")
    manifest = result.get("frozen_evidence_manifest")
    _require(type(manifest) is dict, source_name + "_frozen_manifest_missing")
    _require(
        manifest.get("trust", {}).get("binding_status") == "UNBOUND",
        source_name + "_raw_evidence_not_unbound",
    )
    false_flags = (
        tuple(grid_adapter.CLAIM_CEILINGS)
        if source_name == "starting_grid"
        else ADAPTER_FALSE_FLAGS
    )
    for flag in false_flags:
        _require(result.get(flag) is False,
                 source_name + "_forbidden_claim:" + flag)
    if source_name == "starting_grid":
        for flag in (
            "source_session_classification_authenticated",
            "target_race_session_classification_authenticated",
            "producer_input_csv_is_target_race_scoped",
            "cross_session_join_authorized",
            "commercial_or_redistribution_permission_claimed",
        ):
            _require(result.get(flag) is False,
                     source_name + "_forbidden_claim:" + flag)
    return data


def _receipt_metadata(receipt_bytes, *, result, raw_bytes, source_name):
    receipt = _strict_json_bytes(
        receipt_bytes, top_level=dict, reason=source_name + "_receipt_malformed"
    )
    payload = receipt.get("payload")
    _require(type(payload) is dict, source_name + "_receipt_payload_malformed")
    receipt_id = receipt.get("receipt_id")
    source_id = payload.get("source_id")
    raw_hash = payload.get("source_sha256")
    _require(type(receipt_id) is str and receipt_id.startswith("source_capture:")
             and HEX64.fullmatch(receipt_id.split(":", 1)[1]),
             source_name + "_receipt_id_malformed")
    _require(type(source_id) is str and source_id.startswith("openf1:"),
             source_name + "_source_id_malformed")
    _require(type(raw_hash) is str and HEX64.fullmatch(raw_hash)
             and raw_hash == _sha256(raw_bytes)
             and result.get("raw_source_sha256") == raw_hash,
             source_name + "_raw_hash_mismatch")
    _require(result.get("source_receipt_id") == receipt_id,
             source_name + "_receipt_identity_mismatch")
    first = _parse_utc(payload.get("first_observed_utc"),
                       source_name + "_first_observed_invalid")
    ingested = _parse_utc(payload.get("ingested_utc"),
                          source_name + "_ingested_invalid")
    created = _parse_utc(receipt.get("receipt_created_utc"),
                         source_name + "_receipt_created_invalid")
    _require(first <= ingested <= created,
             source_name + "_receipt_time_order_invalid")
    return {
        "receipt": receipt,
        "receipt_id": receipt_id,
        "source_id": source_id,
        "raw_sha256": raw_hash,
        "first_observed": first,
        "first_observed_utc": payload["first_observed_utc"],
    }


def _csv_driver_numbers(csv_bytes, *, expected_fields, number_field, reason):
    try:
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"), newline=""))
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CompatibilityInputError(reason) from exc
    _require(tuple(reader.fieldnames or ()) == expected_fields, reason)
    _require(bool(rows), reason)
    numbers = set()
    for row in rows:
        _require(None not in row and all(value is not None for value in row.values()),
                 reason)
        value = row[number_field]
        _require(type(value) is str and POSITIVE_DECIMAL.fullmatch(value), reason)
        number = int(value)
        _require(number not in numbers, reason)
        numbers.add(number)
    return rows, numbers


def _validate_grid_manifest(
    manifest, *, sessions_sha, grid_sha, grid_receipt, event_id, meeting_id,
    qualifying_source_session_id, target_race_session_id,
):
    required = {
        "status": capture_contract.VALIDATED,
        "k4r1_status": capture_contract.VALIDATED,
        "k4r14_status": grid_adapter.VALIDATED,
        "selected_endpoint": "starting_grid",
        "event_id": event_id,
        "meeting_id": meeting_id,
        "session_id": qualifying_source_session_id,
        "grid_source_session_id": qualifying_source_session_id,
        "grid_source_session_kind": "Qualifying",
        "grid_target_race_session_id": target_race_session_id,
        "grid_target_race_session_kind": "Race",
        "source_to_race_link_evidence_type": PROVIDER_LINK,
        "session_discovery_raw_sha256": sessions_sha,
        "discovery_response_sha256": sessions_sha,
        "starting_grid_raw_sha256": grid_sha,
        "raw_response_sha256": grid_sha,
        "source_receipt_id": grid_receipt["receipt_id"],
        "raw_source_id": grid_receipt["source_id"],
        "frozen_evidence_binding_status": "UNBOUND",
    }
    for field, expected in required.items():
        _require(manifest.get(field) == expected,
                 "grid_shadow_manifest_mismatch:" + field)
    for flag in (
        "source_session_classification_authenticated",
        "target_race_session_classification_authenticated",
        "producer_input_csv_is_target_race_scoped",
        "cross_session_join_authorized",
        "official_fia_grid_authenticated",
        "historical_pre_race_availability_proven",
        "blind_validation_eligible",
        "stable_engine_execution_proven",
        "production_forecast_generated",
        "dr002_activated",
        "promotion_allowed",
    ):
        _require(manifest.get(flag) is False,
                 "grid_shadow_manifest_forbidden_claim:" + flag)


def _hold(reason):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HOLD,
        "reason_codes": [reason],
        **{flag: False for flag in COMMON_FALSE_FLAGS},
    }


def assess_openf1_three_source_event_compatibility(
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
    """Assess historical event compatibility without authorizing a join.

    The result is deterministic JSON-serializable metadata.  VALIDATED means
    only that the three already-observed sources are mechanically compatible at
    event level after the Race; it never means prediction eligibility.
    """
    try:
        event = _text(event_id, "malformed_event_id")
        meeting = _positive_decimal(meeting_id, "malformed_meeting_id")
        practice_id = _positive_decimal(
            practice_session_id, "malformed_practice_session_id"
        )
        qualifying_id = _positive_decimal(
            qualifying_source_session_id,
            "malformed_qualifying_source_session_id",
        )
        race_id = _positive_decimal(
            target_race_session_id, "malformed_target_race_session_id"
        )
        _require(len({practice_id, qualifying_id, race_id}) == 3,
                 "source_and_target_session_ids_not_distinct")
        if implementation_git_sha is not None:
            _require(type(implementation_git_sha) is str
                     and HEX40.fullmatch(implementation_git_sha),
                     "implementation_git_sha_malformed")

        sessions = _strict_json_bytes(
            sessions_response_bytes, top_level=list,
            reason="session_discovery_malformed",
        )
        manifest = _strict_json_bytes(
            grid_shadow_manifest_bytes, top_level=dict,
            reason="grid_shadow_manifest_malformed",
        )
        practice, qualifying, race = _validate_sessions(
            sessions,
            event_id=event,
            meeting_id=meeting,
            practice_session_id=practice_id,
            qualifying_source_session_id=qualifying_id,
            target_race_session_id=race_id,
        )

        practice_scope = {
            "event_id": event, "meeting_id": meeting, "session_id": practice_id,
        }
        qualifying_scope = {
            "event_id": event, "meeting_id": meeting, "session_id": qualifying_id,
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
        weather_csv = _validated_adapter(
            weather_result, expected_status=weather_adapter.VALIDATED,
            source_name="weather", scope=practice_scope,
        )
        drivers_csv = _validated_adapter(
            drivers_result, expected_status=drivers_adapter.VALIDATED,
            source_name="drivers", scope=practice_scope,
        )
        grid_csv = _validated_adapter(
            grid_result, expected_status=grid_adapter.VALIDATED,
            source_name="starting_grid", scope=qualifying_scope,
        )

        weather_receipt = _receipt_metadata(
            weather_source_capture_receipt_bytes, result=weather_result,
            raw_bytes=raw_weather_response_bytes, source_name="weather",
        )
        drivers_receipt = _receipt_metadata(
            drivers_source_capture_receipt_bytes, result=drivers_result,
            raw_bytes=raw_drivers_response_bytes, source_name="drivers",
        )
        grid_receipt = _receipt_metadata(
            starting_grid_source_capture_receipt_bytes, result=grid_result,
            raw_bytes=raw_starting_grid_response_bytes, source_name="starting_grid",
        )
        receipts = (weather_receipt, drivers_receipt, grid_receipt)
        _require(len({item["receipt_id"] for item in receipts}) == 3,
                 "duplicate_source_receipt_identity")
        _require(len({item["source_id"] for item in receipts}) == 3,
                 "duplicate_raw_source_identity")
        _require(all(item["first_observed"] > race["end"] for item in receipts),
                 "source_not_first_observed_after_race")

        driver_rows, driver_numbers = _csv_driver_numbers(
            drivers_csv,
            expected_fields=drivers_adapter.CSV_FIELDS,
            number_field="driver_number",
            reason="drivers_derived_csv_invalid",
        )
        grid_rows, grid_numbers = _csv_driver_numbers(
            grid_csv,
            expected_fields=grid_adapter.CSV_FIELDS,
            number_field="driver_number",
            reason="starting_grid_derived_csv_invalid",
        )
        _require(driver_numbers == grid_numbers,
                 "drivers_and_grid_roster_mismatch")
        positions = []
        for row in grid_rows:
            _require(POSITIVE_DECIMAL.fullmatch(row["position"]),
                     "starting_grid_position_invalid")
            positions.append(int(row["position"]))
        _require(sorted(positions) == list(range(1, len(grid_rows) + 1)),
                 "starting_grid_slots_not_contiguous")
        _require(
            len(driver_rows) == drivers_result.get("row_count")
            == drivers_result.get("unique_driver_count")
            == len(grid_rows) == grid_result.get("row_count")
            == grid_result.get("unique_driver_count")
            == grid_result.get("slot_count"),
            "three_source_driver_count_mismatch",
        )

        derived_ids = {
            "derived:openf1-weather-csv:" + weather_result["producer_input_sha256"],
            drivers_result.get("derived_runtime_identity"),
            grid_result.get("derived_runtime_identity"),
        }
        _require(None not in derived_ids and len(derived_ids) == 3,
                 "derived_source_identity_collision")
        _require(derived_ids.isdisjoint(
            {item["source_id"] for item in receipts}
        ), "raw_and_derived_source_identity_collision")

        sessions_sha = _sha256(sessions_response_bytes)
        _validate_grid_manifest(
            manifest,
            sessions_sha=sessions_sha,
            grid_sha=grid_receipt["raw_sha256"],
            grid_receipt=grid_receipt,
            event_id=event,
            meeting_id=meeting,
            qualifying_source_session_id=qualifying_id,
            target_race_session_id=race_id,
        )

        result = {
            "schema_version": SCHEMA_VERSION,
            "status": VALIDATED,
            "reason_codes": [],
            "classification": "POST_EVENT_MECHANICS_ONLY_NOT_A_PREDICTION",
            "event_id": event,
            "meeting_id": meeting,
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
            "source_to_target_link_evidence_type": PROVIDER_LINK,
            "session_discovery_raw_sha256": sessions_sha,
            "weather": {
                "source_receipt_id": weather_receipt["receipt_id"],
                "raw_source_id": weather_receipt["source_id"],
                "raw_source_sha256": weather_receipt["raw_sha256"],
                "derived_runtime_identity": (
                    "derived:openf1-weather-csv:"
                    + weather_result["producer_input_sha256"]
                ),
                "derived_csv_sha256": weather_result["producer_input_sha256"],
                "row_count": weather_result["row_count"],
                "first_observed_utc": weather_receipt["first_observed_utc"],
                "raw_frozen_evidence_binding_status": "UNBOUND",
            },
            "drivers": {
                "source_receipt_id": drivers_receipt["receipt_id"],
                "raw_source_id": drivers_receipt["source_id"],
                "raw_source_sha256": drivers_receipt["raw_sha256"],
                "derived_runtime_identity": drivers_result["derived_runtime_identity"],
                "derived_csv_sha256": drivers_result["producer_input_sha256"],
                "row_count": drivers_result["row_count"],
                "unique_driver_count": drivers_result["unique_driver_count"],
                "first_observed_utc": drivers_receipt["first_observed_utc"],
                "raw_frozen_evidence_binding_status": "UNBOUND",
            },
            "starting_grid": {
                "source_receipt_id": grid_receipt["receipt_id"],
                "raw_source_id": grid_receipt["source_id"],
                "raw_source_sha256": grid_receipt["raw_sha256"],
                "derived_runtime_identity": grid_result["derived_runtime_identity"],
                "derived_csv_sha256": grid_result["producer_input_sha256"],
                "row_count": grid_result["row_count"],
                "unique_driver_count": grid_result["unique_driver_count"],
                "slot_count": grid_result["slot_count"],
                "first_observed_utc": grid_receipt["first_observed_utc"],
                "raw_frozen_evidence_binding_status": "UNBOUND",
            },
            "event_level_compatibility_assessed": True,
            "combined_frozen_producer_manifest_created": False,
            "source_receipts_remain_distinct": True,
            **{flag: False for flag in COMMON_FALSE_FLAGS},
        }
        if implementation_git_sha is not None:
            result["implementation_git_sha"] = implementation_git_sha
        json.dumps(result, sort_keys=True, allow_nan=False)
        _require(not any(type(value) is bytes for value in result.values()),
                 "bytes_in_result")
        return result
    except (
        CompatibilityInputError,
        TypeError,
        ValueError,
        KeyError,
        UnicodeDecodeError,
        OverflowError,
        AttributeError,
    ) as exc:
        reason = str(exc) or type(exc).__name__
        return _hold(reason)
