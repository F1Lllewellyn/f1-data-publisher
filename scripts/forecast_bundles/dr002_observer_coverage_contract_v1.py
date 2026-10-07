"""Pure offline observer-schedule coverage assessment.

This module proves only coverage of an explicitly declared observation window.
It cannot prove publisher history, changes between slots, or global completeness.
"""
import json

from verify_forecast_integrity_receipts_v1 import (
    ReceiptError,
    _time,
    canonical_json_bytes,
    sha256,
    validate_receipt_envelope,
    verify_temporal_bindings,
)


SCHEMA_VERSION = "dr002-observer-coverage-assessment-v1"
PROVEN = "DECLARED_WINDOW_SCHEDULE_COVERAGE_PROVEN"
INCOMPLETE = "DECLARED_WINDOW_SCHEDULE_COVERAGE_INCOMPLETE"
HOLD = "HOLD"
ATTEMPT_STATUSES = frozenset(("SUCCESS", "FAILED", "CANCELLED"))
SCOPE_FIELDS = ("source_id", "source_uri", "event_id", "meeting_id", "session_id")
TRUST_CEILINGS = (
    "publisher_revision_completeness_proven",
    "global_observation_completeness_proven",
    "publisher_source_authenticated",
    "observation_clock_authenticated",
    "historical_availability_proven",
    "production_revision_tracking_proven",
    "full_gate2b1_chain_verified",
    "stable_engine_execution_proven",
    "blind_validation_eligible",
    "dr002_activated",
    "promotion_allowed",
)


class ObserverCoverageInputError(ValueError):
    """Malformed, ambiguous, or tampered caller-supplied evidence."""


def _require(condition, reason):
    if not condition:
        raise ObserverCoverageInputError(reason)


def _strict_json_bytes(data):
    _require(isinstance(data, bytes), "receipt_bytes_not_bytes")

    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, "duplicate_receipt_json_key")
            value[key] = item
        return value

    try:
        value = json.loads(data, object_pairs_hook=pairs)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ObserverCoverageInputError("malformed_receipt_json")
    _require(canonical_json_bytes(value) == data, "noncanonical_receipt_bytes")
    return value


def _assessment(*, status, reason_codes, scope, window, planned_slot_count,
                attempt_count, successful_attempt_count, missed_or_failed_slots,
                receipt_bound):
    result = {
        "schema_version": SCHEMA_VERSION,
        "assessment_type": "DECLARED_OBSERVER_WINDOW_COVERAGE",
        "status": status,
        "reason_codes": list(reason_codes),
        "scope": scope,
        "window": window,
        "planned_slot_count": planned_slot_count,
        "attempt_count": attempt_count,
        "successful_attempt_count": successful_attempt_count,
        "missed_or_failed_slots": list(missed_or_failed_slots),
        "declared_window_schedule_coverage_proven": status == PROVEN,
        "all_successful_observations_receipt_bound": receipt_bound,
    }
    result.update({field: False for field in TRUST_CEILINGS})
    return result


def assess_observer_coverage(
    *,
    scope,
    window,
    planned_slots,
    attempts,
    receipt_bytes_by_slot,
    source_bytes_by_slot,
    publisher_revision_completeness_proven=False,
    global_observation_completeness_proven=False,
):
    """Assess explicit schedule coverage from caller-supplied bytes and facts.

    This returns an assessment envelope, never a scientific receipt. Timestamps
    are structurally checked but are not authenticated by this contract.
    """
    scope_fact = None
    window_fact = None
    planned_count = len(planned_slots) if isinstance(planned_slots, list) else 0
    attempt_count = len(attempts) if isinstance(attempts, list) else 0
    successful_count = 0
    try:
        _require(
            isinstance(publisher_revision_completeness_proven, bool)
            and isinstance(global_observation_completeness_proven, bool),
            "malformed_completeness_assertion",
        )
        _require(
            not publisher_revision_completeness_proven
            and not global_observation_completeness_proven,
            "unsupported_completeness_assertion",
        )
        _require(
            isinstance(scope, dict)
            and set(scope) == set(SCOPE_FIELDS)
            and all(isinstance(scope[field], str) and scope[field].strip() for field in SCOPE_FIELDS),
            "malformed_observer_scope",
        )
        scope_fact = {field: scope[field] for field in SCOPE_FIELDS}
        _require(
            isinstance(window, dict) and set(window) == {"start_utc", "end_utc"},
            "malformed_observation_window",
        )
        start = _time(window["start_utc"])
        end = _time(window["end_utc"])
        _require(start < end, "invalid_observation_window")
        window_fact = {"start_utc": window["start_utc"], "end_utc": window["end_utc"]}

        _require(isinstance(planned_slots, list) and bool(planned_slots), "missing_planned_slots")
        planned = []
        previous_due = None
        for slot in planned_slots:
            _require(
                isinstance(slot, dict)
                and set(slot) == {"slot_id", "due_utc"}
                and isinstance(slot["slot_id"], str)
                and slot["slot_id"].strip(),
                "malformed_planned_slot",
            )
            due = _time(slot["due_utc"])
            _require(start <= due <= end, "slot_due_outside_window")
            _require(previous_due is None or previous_due < due, "duplicate_or_unordered_slot_due_time")
            previous_due = due
            planned.append((slot["slot_id"], slot["due_utc"]))
        slot_ids = [slot_id for slot_id, _ in planned]
        _require(len(slot_ids) == len(set(slot_ids)), "duplicate_slot_id")
        planned_index = dict(planned)

        _require(isinstance(attempts, list), "malformed_attempts")
        attempt_index = {}
        for attempt in attempts:
            _require(
                isinstance(attempt, dict)
                and set(attempt) == {"slot_id", "status", "observed_utc"}
                and isinstance(attempt["slot_id"], str)
                and attempt["slot_id"].strip()
                and attempt["status"] in ATTEMPT_STATUSES,
                "malformed_observation_attempt",
            )
            slot_id = attempt["slot_id"]
            _require(slot_id in planned_index, "undeclared_attempt_slot")
            _require(slot_id not in attempt_index, "duplicate_attempt_slot")
            observed = _time(attempt["observed_utc"])
            _require(start <= observed <= end, "attempt_outside_window")
            attempt_index[slot_id] = attempt

        _require(isinstance(receipt_bytes_by_slot, dict), "malformed_receipt_byte_map")
        _require(isinstance(source_bytes_by_slot, dict), "malformed_source_byte_map")
        successful_ids = {
            slot_id for slot_id, attempt in attempt_index.items()
            if attempt["status"] == "SUCCESS"
        }
        successful_count = len(successful_ids)
        _require(set(receipt_bytes_by_slot) == successful_ids, "successful_receipt_set_mismatch")
        _require(set(source_bytes_by_slot) == successful_ids, "successful_source_byte_set_mismatch")

        for slot_id in slot_ids:
            attempt = attempt_index.get(slot_id)
            if attempt is None or attempt["status"] != "SUCCESS":
                continue
            receipt = _strict_json_bytes(receipt_bytes_by_slot[slot_id])
            validate_receipt_envelope(receipt)
            verify_temporal_bindings(receipt)
            _require(receipt["receipt_type"] == "source_capture", "wrong_receipt_type")
            _require(receipt["parent_receipt_ids"] == [], "source_capture_not_parentless")
            _require(isinstance(source_bytes_by_slot[slot_id], bytes), "source_content_not_bytes")
            payload = receipt["payload"]
            _require(sha256(source_bytes_by_slot[slot_id]) == payload["source_sha256"], "source_content_hash_mismatch")
            _require(payload["source_id"] == scope["source_id"], "source_id_mismatch")
            _require(payload["source_uri"] == scope["source_uri"], "source_uri_mismatch")
            for field in ("event_id", "meeting_id", "session_id"):
                _require(receipt["scope"][field] == scope[field], field + "_mismatch")
            _require(attempt["observed_utc"] == payload["first_observed_utc"], "attempt_observed_time_mismatch")
            _require(_time(payload["ingested_utc"]) >= _time(payload["first_observed_utc"]), "ingestion_before_observation")

        missed = [
            slot_id for slot_id in slot_ids
            if slot_id not in attempt_index or attempt_index[slot_id]["status"] != "SUCCESS"
        ]
        incomplete_reasons = [
            ("missing_slot:" + slot_id) if slot_id not in attempt_index
            else (attempt_index[slot_id]["status"].lower() + "_slot:" + slot_id)
            for slot_id in missed
        ]
        status = INCOMPLETE if missed else PROVEN
        return _assessment(
            status=status,
            reason_codes=incomplete_reasons,
            scope=scope_fact,
            window=window_fact,
            planned_slot_count=len(slot_ids),
            attempt_count=len(attempt_index),
            successful_attempt_count=successful_count,
            missed_or_failed_slots=missed,
            receipt_bound=True,
        )
    except (ObserverCoverageInputError, ReceiptError, KeyError, TypeError, ValueError) as exc:
        reason = exc.code if isinstance(exc, ReceiptError) else str(exc)
        return _assessment(
            status=HOLD,
            reason_codes=[reason or "malformed_or_tampered_input"],
            scope=scope_fact,
            window=window_fact,
            planned_slot_count=planned_count,
            attempt_count=attempt_count,
            successful_attempt_count=successful_count,
            missed_or_failed_slots=[],
            receipt_bound=False,
        )
