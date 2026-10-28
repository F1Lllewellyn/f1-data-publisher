"""Pure offline FIA final-starting-grid custody and comparison verifier.

This experimental verifier composes the accepted FIA document-candidate and
verified-source-consumer contracts.  It recognizes exactly one reviewed source
profile: Austin 2026 FIA Document 50.  It never fetches, parses, corrects, or
publishes a grid and never upgrades historical evidence to forecast eligibility.
"""
import math

from . import dr002_fia_grid_document_candidate_v1 as candidate
from . import dr002_verified_source_consumer_v1 as consumer


SCHEMA_VERSION = "dr002-fia-final-grid-provenance-verifier-v1"
VERIFIED_MATCH = "FIA_FINAL_GRID_MATCH_VERIFIED_RETROSPECTIVE_ONLY"
DISCREPANCY_HOLD = "HOLD_FIA_FINAL_GRID_DISCREPANCY"

AUSTIN_PROFILE_ID = "fia:2026-united-states-grand-prix:document-50"
AUSTIN_EVENT_ID = "2026_1297_united_states_austin_austin"
AUSTIN_MEETING_ID = "1297"
AUSTIN_RACE_SESSION_ID = "11396"
AUSTIN_OBSERVED_SOURCE_SESSION_ID = 11392
AUSTIN_DOCUMENT_URI = (
    "https://www.fia.com/system/files/decision-document/"
    "2026_united_states_grand_prix_-_final_starting_grid.pdf"
)
AUSTIN_INDEX_URI = (
    "https://www.fia.com/documents/championships/"
    "fia-formula-one-world-championship-14/season/season-2026-2072/"
    "event/United%20States%20Grand%20Prix"
)
AUSTIN_DOCUMENT_SHA256 = "68175d2f0e065da67b78ef38486b0d0aca4e8e370c7b35266614c0afb7bd0454"
AUSTIN_DOCUMENT_SIZE_BYTES = 510017
AUSTIN_OBSERVED_GRID_SHA256 = "06ce29fdf7afd9a731012aa4de60a80945f8fa0c735103afedfe903b16aa1e38"
AUSTIN_PUBLISHED_UTC = "2026-10-25T19:00:00Z"
AUSTIN_RACE_START_UTC = "2026-10-25T20:00:00Z"

# Position, car number.  Document 50 has 21 conventional slots and one
# separately classified pit-lane starter, car 18.
AUSTIN_CONVENTIONAL_GRID = (
    (1, 12), (2, 3), (3, 6), (4, 16), (5, 44), (6, 63), (7, 81),
    (8, 1), (9, 30), (10, 10), (11, 27), (12, 14), (13, 87),
    (14, 41), (15, 31), (16, 55), (17, 23), (18, 11), (19, 77),
    (20, 43), (21, 5),
)
AUSTIN_PIT_LANE_DRIVERS = (18,)

_PROFILE_FIELDS = {
    "profile_id", "event_id", "meeting_id", "race_session_id",
    "observed_source_session_id", "document_uri", "official_index_uri",
    "document_number", "document_title", "document_type",
    "raw_document_sha256", "raw_document_size_bytes",
    "observed_grid_sha256", "published_utc", "race_start_utc",
    "index_publication_text", "document_header_date", "document_header_time",
    "conventional_grid", "pit_lane_drivers",
}

_ALWAYS_FALSE = {
    "forecast_as_of_eligible": False,
    "historical_availability_proven": False,
    "first_observed_clock_authenticated": False,
    "publisher_authenticated": False,
    "publication_time_authenticated": False,
    "race_predictions_unlocked": False,
    "fantasy_predictions_unlocked": False,
    "corrected_grid_published": False,
    "session_processor_modified": False,
    "production_authenticated": False,
    "stable_engine_modified": False,
    "dr002_activated": False,
    "promotion_allowed": False,
}


def _austin_profile():
    return {
        "profile_id": AUSTIN_PROFILE_ID,
        "event_id": AUSTIN_EVENT_ID,
        "meeting_id": AUSTIN_MEETING_ID,
        "race_session_id": AUSTIN_RACE_SESSION_ID,
        "observed_source_session_id": AUSTIN_OBSERVED_SOURCE_SESSION_ID,
        "document_uri": AUSTIN_DOCUMENT_URI,
        "official_index_uri": AUSTIN_INDEX_URI,
        "document_number": 50,
        "document_title": "Final Starting Grid",
        "document_type": "final_starting_grid",
        "raw_document_sha256": AUSTIN_DOCUMENT_SHA256,
        "raw_document_size_bytes": AUSTIN_DOCUMENT_SIZE_BYTES,
        "observed_grid_sha256": AUSTIN_OBSERVED_GRID_SHA256,
        "published_utc": AUSTIN_PUBLISHED_UTC,
        "race_start_utc": AUSTIN_RACE_START_UTC,
        "index_publication_text": "25.10.26 20:00 CET",
        "document_header_date": "25 October 2026",
        "document_header_time": "14:00",
        "conventional_grid": AUSTIN_CONVENTIONAL_GRID,
        "pit_lane_drivers": AUSTIN_PIT_LANE_DRIVERS,
    }


class VerificationHold(ValueError):
    """An invariant failed before a usable retrospective comparison."""


def _require(condition, reason):
    if not condition:
        raise VerificationHold(reason)


def _hold(reason):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "HOLD",
        "reason_codes": [reason],
        "document_custody_verified": False,
        "official_final_grid_reference_verified": False,
        "observed_grid_matches_official": False,
        "differences": [],
        **_ALWAYS_FALSE,
    }


def _validate_profile(profile):
    _require(type(profile) is dict and set(profile) == _PROFILE_FIELDS,
             "malformed_reference_profile")
    _require(profile["document_number"] == 50
             and profile["document_title"] == "Final Starting Grid"
             and profile["document_type"] == "final_starting_grid",
             "document_identity_mismatch")
    _require(profile["published_utc"] == profile["race_start_utc"][:11] + "19:00:00Z",
             "publication_time_evidence_mismatch")
    _require(profile["index_publication_text"] == "25.10.26 20:00 CET"
             and profile["document_header_date"] == "25 October 2026"
             and profile["document_header_time"] == "14:00",
             "publication_time_evidence_mismatch")
    conventional = profile["conventional_grid"]
    pit_lane = profile["pit_lane_drivers"]
    _require(type(conventional) is tuple and type(pit_lane) is tuple,
             "malformed_official_grid")
    _require(len(conventional) == 21 and len(pit_lane) == 1,
             "official_grid_count_mismatch")
    _require(tuple(position for position, _ in conventional) == tuple(range(1, 22)),
             "official_grid_positions_not_contiguous")
    conventional_drivers = [driver for _, driver in conventional]
    _require(all(type(driver) is int and driver > 0 for driver in conventional_drivers + list(pit_lane)),
             "invalid_official_driver_number")
    _require(len(set(conventional_drivers + list(pit_lane))) == 22,
             "duplicate_official_driver")
    return conventional, pit_lane


def _strict_observed_grid(raw, profile):
    _require(type(raw) is bytes, "observed_grid_exact_bytes_required")
    _require(consumer.receipts.sha256(raw) == profile["observed_grid_sha256"],
             "unrecognized_observed_grid_revision")
    try:
        rows = consumer.frozen.strict_json(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise VerificationHold("malformed_observed_grid") from exc
    _require(type(rows) is list and len(rows) == 22, "observed_grid_row_count_mismatch")
    legacy_fields = {"position", "driver_number", "lap_duration", "meeting_key", "session_key"}
    classified_fields = {"position", "driver_number", "start_classification",
                         "meeting_key", "session_key"}
    row_schema = None
    observed = {}
    grid_positions = set()
    drivers = set()
    for row in rows:
        _require(type(row) is dict, "observed_grid_schema_mismatch")
        current_schema = "legacy" if set(row) == legacy_fields else (
            "classified" if set(row) == classified_fields else None
        )
        _require(current_schema is not None, "observed_grid_schema_mismatch")
        if row_schema is None:
            row_schema = current_schema
        _require(current_schema == row_schema, "mixed_observed_grid_schema")
        position = row["position"]
        driver = row["driver_number"]
        _require(type(driver) is int and driver > 0, "invalid_observed_driver")
        _require(type(row["meeting_key"]) is int
                 and str(row["meeting_key"]) == profile["meeting_id"],
                 "observed_meeting_mismatch")
        _require(type(row["session_key"]) is int
                 and row["session_key"] == profile["observed_source_session_id"],
                 "observed_source_session_mismatch")
        if row_schema == "legacy":
            _require(type(position) is int and position > 0, "invalid_observed_position")
            classification = "grid"
            lap_duration = row["lap_duration"]
            _require(lap_duration is None or (
                type(lap_duration) in (int, float)
                and math.isfinite(lap_duration) and lap_duration >= 0
            ), "invalid_observed_lap_duration")
        else:
            classification = row["start_classification"]
            _require(classification in {"grid", "pit_lane"},
                     "invalid_observed_classification")
            _require((classification == "grid" and type(position) is int and position > 0)
                     or (classification == "pit_lane" and position is None),
                     "invalid_observed_position")
        if classification == "grid":
            _require(position not in grid_positions, "duplicate_observed_position")
            grid_positions.add(position)
        _require(driver not in drivers, "duplicate_observed_driver")
        observed[driver] = (classification, position)
        drivers.add(driver)
    expected_grid_count = 22 if row_schema == "legacy" else 21
    _require(grid_positions == set(range(1, expected_grid_count + 1)),
             "observed_grid_positions_not_contiguous")
    if row_schema == "classified":
        _require(sum(value[0] == "pit_lane" for value in observed.values()) == 1,
                 "observed_pit_lane_count_mismatch")
    return observed, drivers


def _comparison(observed, official_conventional, official_pit_lane):
    official = {driver: ("grid", position) for position, driver in official_conventional}
    official.update({driver: ("pit_lane", None) for driver in official_pit_lane})
    _require(set(observed) == set(official), "driver_universe_mismatch")
    differences = []
    order = [driver for _, driver in official_conventional] + list(official_pit_lane)
    for driver in order:
        if observed[driver] != official[driver]:
            differences.append({
                "driver_number": driver,
                "observed_classification": observed[driver][0],
                "observed_position": observed[driver][1],
                "official_classification": official[driver][0],
                "official_position": official[driver][1],
            })
    return differences


def _verify(*, raw_document_bytes, source_capture_receipt_bytes, bridge_result,
            observed_grid_bytes, profile):
    official_conventional, official_pit_lane = _validate_profile(profile)
    _require(type(raw_document_bytes) is bytes, "raw_document_exact_bytes_required")
    _require(len(raw_document_bytes) == profile["raw_document_size_bytes"],
             "unrecognized_document_size")
    _require(consumer.receipts.sha256(raw_document_bytes) == profile["raw_document_sha256"],
             "unrecognized_document_revision")

    scope = {
        "event_id": profile["event_id"],
        "meeting_id": profile["meeting_id"],
        "allowed_session_ids": [profile["race_session_id"]],
    }
    custody = consumer.consume_verified_source(
        receipt_bytes=source_capture_receipt_bytes,
        source_bytes=raw_document_bytes,
        request_scope=scope,
        bridge_result=bridge_result,
    )
    _require(custody.get("status") == "OFFLINE_VERIFIED_SOURCE_CONSUMER_VALIDATED",
             "document_custody_not_verified")
    receipt = consumer.frozen.strict_json(source_capture_receipt_bytes)
    payload = receipt["payload"]
    _require(payload["source_uri"] == profile["document_uri"], "document_uri_mismatch")
    _require(payload["publisher_time_utc"] == profile["published_utc"],
             "publication_time_receipt_mismatch")

    assessment = candidate.assess_fia_grid_document_candidate(
        raw_document_bytes=raw_document_bytes,
        document_type=profile["document_type"],
        document_number=profile["document_number"],
        document_title=profile["document_title"],
        document_uri=profile["document_uri"],
        official_index_uri=profile["official_index_uri"],
        event_id=profile["event_id"],
        meeting_id=profile["meeting_id"],
        session_id=profile["race_session_id"],
        published_utc=profile["published_utc"],
        first_observed_utc=payload["first_observed_utc"],
        ingested_utc=payload["ingested_utc"],
        receipt_created_utc=receipt["receipt_created_utc"],
        forecast_cutoff_utc=receipt["receipt_created_utc"],
    )
    _require(assessment.get("status") == candidate.VALIDATED_STATUS,
             "fia_candidate_not_validated")
    document = assessment["document_candidate"]
    _require(document["raw_document_sha256"] == profile["raw_document_sha256"]
             and document["raw_document_size_bytes"] == profile["raw_document_size_bytes"],
             "candidate_document_identity_mismatch")
    _require(payload["source_id"] == document["claimed_source_id"],
             "receipt_source_identity_mismatch")

    observed, observed_drivers = _strict_observed_grid(observed_grid_bytes, profile)
    differences = _comparison(observed, official_conventional, official_pit_lane)
    official_grid_sha256 = consumer.receipts.sha256(consumer.receipts.canonical_json_bytes({
        "conventional": [
            {"position": position, "driver_number": driver}
            for position, driver in official_conventional
        ],
        "pit_lane": [{"driver_number": driver} for driver in official_pit_lane],
    }))
    status = DISCREPANCY_HOLD if differences else VERIFIED_MATCH
    reasons = ["observed_grid_differs_from_fia_final_grid"] if differences else []
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reason_codes": reasons,
        "profile_id": profile["profile_id"],
        "event_id": profile["event_id"],
        "meeting_id": profile["meeting_id"],
        "race_session_id": profile["race_session_id"],
        "observed_source_session_id": profile["observed_source_session_id"],
        "document_number": profile["document_number"],
        "document_uri": profile["document_uri"],
        "document_sha256": profile["raw_document_sha256"],
        "document_size_bytes": profile["raw_document_size_bytes"],
        "document_custody_verified": True,
        "custody_trust_scope": custody["binding_trust_scope"],
        "official_final_grid_reference_verified": True,
        "publication_time_evidence": {
            "official_index_uri": profile["official_index_uri"],
            "index_publication_text": profile["index_publication_text"],
            "document_header_date": profile["document_header_date"],
            "document_header_time": profile["document_header_time"],
            "normalized_utc": profile["published_utc"],
            "race_start_utc": profile["race_start_utc"],
            "retrospective_only": True,
        },
        "official_grid_sha256": official_grid_sha256,
        "official_driver_count": 22,
        "official_conventional_position_count": 21,
        "official_pit_lane_driver_count": 1,
        "observed_driver_count": len(observed_drivers),
        "observed_grid_matches_official": not differences,
        "differences": differences,
        **_ALWAYS_FALSE,
    }


def verify_austin_final_starting_grid(*, raw_document_bytes,
                                      source_capture_receipt_bytes,
                                      bridge_result, observed_grid_bytes):
    """Verify exact Austin Doc 50 custody and compare retained grid evidence."""
    try:
        return _verify(
            raw_document_bytes=raw_document_bytes,
            source_capture_receipt_bytes=source_capture_receipt_bytes,
            bridge_result=bridge_result,
            observed_grid_bytes=observed_grid_bytes,
            profile=_austin_profile(),
        )
    except (VerificationHold, ValueError, TypeError, KeyError, IndexError,
            AttributeError, OverflowError, RecursionError, UnicodeError) as exc:
        return _hold(str(exc) or "malformed_verification_input")
