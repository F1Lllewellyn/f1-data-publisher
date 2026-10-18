#!/usr/bin/env python3
"""Offline event-scoped bridge from frozen producer inputs to forecast locking.

The bridge performs no discovery, provider request, workflow dispatch, model
execution, publication, or trust upgrade.  Exact input bytes and pre-existing
source-capture receipts are supplied explicitly by the caller.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile


HERE = Path(__file__).resolve().parent
FORECASTS = HERE.parent / "forecasts"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FORECASTS))

import produce_actual_forecast_rows_v1 as producer
import verify_forecast_integrity_receipts_v1 as receipts


SCHEMA = "f1-event-scoped-forecast-input-lock-v1"
PREDICTION_GATES = frozenset(("pre_weekend", "post_fp3", "post_qualifying"))
REQUEST_FIELDS = {
    "schema_version",
    "event_id",
    "meeting_id",
    "target_session_id",
    "allowed_session_ids",
    "forecast_cutoff_utc",
    "forecast_deadline_utc",
    "forecast_generation_utc",
    "forecast_lock_utc",
    "gate",
    "lane_name",
    "race_name",
    "participants",
    "sources",
    "producer_git_commit",
}
SOURCE_FIELDS = {
    "source_name",
    "source_id",
    "session_id",
    "relative_path",
    "source_sha256",
    "receipt_relative_path",
    "receipt_sha256",
    "ingestion_required_at_cutoff",
    "verified_binding",
}


class EventScopedInputError(ValueError):
    """Fail-closed input package rejection."""


def require(condition, reason):
    if not condition:
        raise EventScopedInputError(reason)


def sha256(data):
    require(type(data) is bytes, "hash_input_not_bytes")
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value):
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise EventScopedInputError("noncanonical_json") from exc


def strict_json(data):
    require(type(data) is bytes, "json_input_not_bytes")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    try:
        return json.loads(
            data,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                EventScopedInputError("nonfinite_json")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EventScopedInputError("malformed_json") from exc


def utc(value):
    try:
        result = receipts._time(value)
    except (ValueError, TypeError, receipts.ReceiptError) as exc:
        raise EventScopedInputError("malformed_utc") from exc
    require(result.utcoffset() == timezone.utc.utcoffset(result), "non_utc_timestamp")
    return result


def canonical_relative_path(value):
    require(type(value) is str and bool(value), "missing_relative_path")
    require("\\" not in value and ":" not in value, "noncanonical_relative_path")
    path = Path(value)
    require(
        not path.is_absolute()
        and all(part not in ("", ".", "..") for part in value.split("/")),
        "noncanonical_relative_path",
    )
    return path


def read_package_file(root, relative_path):
    path = canonical_relative_path(relative_path)
    current = root
    for part in path.parts:
        current = current / part
        require(not current.is_symlink(), "ambiguous_symlink_path")
    require(current.is_file(), "missing_package_file")
    require(current.resolve().is_relative_to(root.resolve()), "package_path_escape")
    return current.read_bytes()


def _validate_request_shape(request):
    require(type(request) is dict and set(request) == REQUEST_FIELDS, "malformed_request")
    require(request["schema_version"] == SCHEMA, "unsupported_schema")
    for key in (
        "event_id",
        "meeting_id",
        "target_session_id",
        "race_name",
        "lane_name",
    ):
        require(type(request[key]) is str and bool(request[key].strip()), "missing_" + key)
    require(request["gate"] in PREDICTION_GATES, "unsupported_prediction_gate")
    require(request["lane_name"] in producer.LANES, "unsupported_lane")
    require(
        type(request["producer_git_commit"]) is str
        and re.fullmatch(r"[0-9a-f]{40}", request["producer_git_commit"]),
        "invalid_producer_git_commit",
    )

    allowed = request["allowed_session_ids"]
    require(
        type(allowed) is list
        and bool(allowed)
        and all(type(value) is str and bool(value) for value in allowed)
        and allowed == sorted(set(allowed)),
        "ambiguous_allowed_sessions",
    )
    require(request["target_session_id"] in allowed, "target_session_not_allowed")

    cutoff = utc(request["forecast_cutoff_utc"])
    deadline = utc(request["forecast_deadline_utc"])
    generated = utc(request["forecast_generation_utc"])
    locked = utc(request["forecast_lock_utc"])
    require(cutoff <= generated <= locked <= deadline, "inconsistent_forecast_timeline")

    participants = request["participants"]
    require(
        type(participants) is dict
        and set(participants) == {"source_name", "driver_numbers"}
        and participants["source_name"] == "drivers",
        "malformed_participant_contract",
    )
    numbers = participants["driver_numbers"]
    require(
        type(numbers) is list
        and bool(numbers)
        and all(type(value) is int and value > 0 for value in numbers)
        and numbers == sorted(set(numbers)),
        "ambiguous_participant_universe",
    )

    sources = request["sources"]
    require(type(sources) is list and bool(sources), "empty_source_set")
    require(
        sources == sorted(sources, key=lambda item: item.get("source_name", "")),
        "noncanonical_source_order",
    )
    names, ids, paths, receipt_paths = set(), set(), set(), set()
    for source in sources:
        require(type(source) is dict and set(source) == SOURCE_FIELDS, "malformed_source")
        name = source["source_name"]
        require(name in producer.SOURCE_FILES and name not in names, "unknown_or_duplicate_source")
        require(
            type(source["source_id"]) is str
            and bool(source["source_id"])
            and source["source_id"] not in ids,
            "missing_or_duplicate_source_id",
        )
        require(source["session_id"] in allowed, "source_session_not_allowed")
        path = source["relative_path"]
        receipt_path = source["receipt_relative_path"]
        canonical_relative_path(path)
        canonical_relative_path(receipt_path)
        require(path not in paths and receipt_path not in receipt_paths, "duplicate_package_path")
        require(
            type(source["source_sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", source["source_sha256"]),
            "malformed_source_hash",
        )
        require(
            type(source["receipt_sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", source["receipt_sha256"]),
            "malformed_receipt_hash",
        )
        require(
            type(source["ingestion_required_at_cutoff"]) is bool,
            "invalid_ingestion_policy",
        )
        binding = source["verified_binding"]
        require(
            type(binding) is dict
            and set(binding) == {"receipt_sha256", "verification_ref"}
            and binding["receipt_sha256"] == source["receipt_sha256"]
            and type(binding["verification_ref"]) is str
            and bool(binding["verification_ref"].strip()),
            "missing_or_malformed_verified_binding",
        )
        names.add(name)
        ids.add(source["source_id"])
        paths.add(path)
        receipt_paths.add(receipt_path)
    require("drivers" in names, "missing_participant_source")


def _driver_numbers(rows):
    values = set()
    for row in rows:
        value = producer.to_int(
            producer.find_key(row, ("driver_number", "number", "driverNumber"))
        )
        if value is not None:
            require(value > 0 and value not in values, "duplicate_or_invalid_driver_number")
            values.add(value)
    return values


def validate_event_scoped_input_package(package_root, request_bytes):
    """Validate exact bytes, receipts, cutoff and participant scope once.

    This reuses the producer's existing frozen input context separately for
    every declared source session.  No broad source discovery is performed.
    """
    root = Path(package_root)
    require(root.is_dir() and not root.is_symlink(), "invalid_package_root")
    request = strict_json(request_bytes)
    _validate_request_shape(request)
    cutoff = request["forecast_cutoff_utc"]
    expected_participants = set(request["participants"]["driver_numbers"])
    source_records = []
    source_bytes = {}
    receipt_records = []
    source_driver_sets = {}

    with tempfile.TemporaryDirectory(prefix="event-scoped-input-validation-") as temp:
        temp_root = Path(temp)
        with ExitStack() as stack:
            for index, source in enumerate(request["sources"]):
                data = read_package_file(root, source["relative_path"])
                require(bool(data) and sha256(data) == source["source_sha256"], "source_hash_mismatch")
                receipt_data = read_package_file(root, source["receipt_relative_path"])
                receipt = strict_json(receipt_data)
                try:
                    receipts.validate_receipt_envelope(receipt)
                    receipts.verify_temporal_bindings(
                        receipt,
                        cutoff=cutoff,
                        ingestion_required=source["ingestion_required_at_cutoff"],
                    )
                except (ValueError, TypeError, KeyError, receipts.ReceiptError) as exc:
                    raise EventScopedInputError("invalid_source_capture_receipt") from exc
                require(receipt["receipt_type"] == "source_capture", "wrong_receipt_type")
                require(receipt["parent_receipt_ids"] == [], "capture_receipt_has_parent")
                require(receipts.receipt_sha256(receipt) == source["receipt_sha256"], "receipt_hash_mismatch")
                require(
                    receipt["scope"]
                    == {
                        "event_id": request["event_id"],
                        "meeting_id": request["meeting_id"],
                        "session_id": source["session_id"],
                    },
                    "receipt_scope_mismatch",
                )
                payload = receipt["payload"]
                require(
                    payload["source_id"] == source["source_id"]
                    and payload["source_sha256"] == source["source_sha256"],
                    "receipt_source_binding_mismatch",
                )
                require(
                    utc(receipt["receipt_created_utc"]) <= utc(cutoff),
                    "receipt_created_after_cutoff",
                )

                source_dir = temp_root / f"source_{index:02d}"
                source_dir.mkdir()
                source_path = source_dir / Path(source["relative_path"]).name
                source_path.write_bytes(data)
                v1 = {
                    "schema_version": producer.FROZEN_SCHEMA,
                    "event_id": request["event_id"],
                    "meeting_id": request["meeting_id"],
                    "session_id": source["session_id"],
                    "sources": [
                        {
                            "source_name": source["source_name"],
                            "source_id": source["source_id"],
                            "relative_path": source_path.name,
                            "source_sha256": source["source_sha256"],
                        }
                    ],
                }
                manifest_path = source_dir / "frozen_input_manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(v1))
                frozen = stack.enter_context(
                    producer.frozen_sources(
                        manifest_path,
                        request["event_id"],
                        request["meeting_id"],
                        source["session_id"],
                    )
                )
                validated_sources, counts, _ = frozen
                rows = producer.read_csv(validated_sources[source["source_name"]])
                require(counts[source["source_name"]] == len(rows) > 0, "source_row_count_mismatch")
                source_driver_sets[source["source_name"]] = _driver_numbers(rows)
                source_bytes[source["source_name"]] = data
                source_records.append(
                    {
                        **source,
                        "row_count": len(rows),
                        "receipt_id": receipt["receipt_id"],
                        "first_observed_utc": payload["first_observed_utc"],
                        "ingested_utc": payload["ingested_utc"],
                    }
                )
                receipt_records.append(receipt)

    require(
        source_driver_sets["drivers"] == expected_participants,
        "participant_source_universe_mismatch",
    )
    for name, observed in source_driver_sets.items():
        require(observed <= expected_participants, "cross_event_driver_in_source:" + name)

    return {
        "schema_version": SCHEMA,
        "status": "EVENT_SCOPED_INPUT_PACKAGE_VALIDATED",
        "request": request,
        "request_sha256": sha256(request_bytes),
        "canonical_request_sha256": sha256(canonical_json_bytes(request)),
        "participant_driver_numbers": sorted(expected_participants),
        "sources": source_records,
        "source_bytes": source_bytes,
        "source_capture_receipts": receipt_records,
        "source_driver_sets": {
            name: sorted(values) for name, values in sorted(source_driver_sets.items())
        },
        "broad_discovery_used": False,
        "provider_request_made": False,
        "production_authenticated": False,
        "dr002_activated": False,
        "promotion_allowed": False,
    }

