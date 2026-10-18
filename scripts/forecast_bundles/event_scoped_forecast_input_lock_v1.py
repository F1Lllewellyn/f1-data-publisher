#!/usr/bin/env python3
"""Offline event-scoped bridge from frozen producer inputs to forecast locking.

The bridge performs no discovery, provider request, workflow dispatch, model
execution, publication, or trust upgrade.  Exact input bytes and pre-existing
source-capture receipts are supplied explicitly by the caller.
"""
from __future__ import annotations

from contextlib import ExitStack
from contextlib import redirect_stdout
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
FORECASTS = HERE.parent / "forecasts"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FORECASTS))

import produce_actual_forecast_rows_v1 as producer
import dr002_lock_boundary_revision_v1 as locker
import forecast_integrity_contract_v1 as integrity
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
    "product_contract_id",
    "execution_mode",
    "contract_approved",
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
DRIVER_REQUIRED_SOURCES = frozenset(
    ("drivers", "starting_grid", "intervals", "stints", "pit", "position")
)
# These are observation clocks in the accepted OpenF1 row contracts.  Static
# sources and scheduled-event metadata (for example date_start/date_end) are
# deliberately excluded: a future event time is not a future observation.
OBSERVATION_TIMESTAMP_FIELDS = {
    "intervals": "date",
    "weather": "date",
    "race_control": "date",
    "pit": "date",
    "position": "date",
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


def source_utc(value, reason):
    require(type(value) is str and bool(value.strip()), reason)
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise EventScopedInputError(reason) from exc
    require(
        parsed.tzinfo is not None
        and parsed.utcoffset() == timezone.utc.utcoffset(parsed),
        reason,
    )
    return parsed


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
        "product_contract_id",
    ):
        require(type(request[key]) is str and bool(request[key].strip()), "missing_" + key)
    require(request["gate"] in PREDICTION_GATES, "unsupported_prediction_gate")
    require(request["lane_name"] in producer.LANES, "unsupported_lane")
    require(
        request["execution_mode"] in ("prospective", "manual_validation"),
        "unsupported_execution_mode",
    )
    require(type(request["contract_approved"]) is bool, "invalid_contract_approval")
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


def _driver_numbers(rows, *, source_name, unique=False):
    values = set()
    for row in rows:
        raw = producer.find_key(row, ("driver_number", "number", "driverNumber"))
        value = producer.to_int(raw)
        if source_name in DRIVER_REQUIRED_SOURCES:
            require(
                value is not None and value > 0,
                "missing_or_invalid_driver_number:" + source_name,
            )
        if value is not None:
            require(
                value > 0 and (not unique or value not in values),
                "duplicate_or_invalid_driver_number",
            )
            values.add(value)
    return values


def _observation_time_bounds(source_name, rows, cutoff):
    field = OBSERVATION_TIMESTAMP_FIELDS.get(source_name)
    if field is None:
        return None
    parsed = []
    for row in rows:
        columns = {key.lower(): key for key in row}
        require(field in columns, "missing_observation_timestamp:" + source_name)
        observed = source_utc(
            row.get(columns[field]), "malformed_observation_timestamp:" + source_name
        )
        require(observed <= cutoff, "source_observation_after_cutoff:" + source_name)
        parsed.append(observed)
    require(bool(parsed), "missing_observation_timestamp:" + source_name)
    return {
        "field": field,
        "earliest_utc": min(parsed).isoformat().replace("+00:00", "Z"),
        "latest_utc": max(parsed).isoformat().replace("+00:00", "Z"),
    }


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
    cutoff_time = utc(cutoff)
    expected_participants = set(request["participants"]["driver_numbers"])
    source_records = []
    source_bytes = {}
    receipt_records = []
    receipt_bytes = {}
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
                source_driver_sets[source["source_name"]] = _driver_numbers(
                    rows,
                    source_name=source["source_name"],
                    unique=source["source_name"] == "drivers",
                )
                observation_bounds = _observation_time_bounds(
                    source["source_name"], rows, cutoff_time
                )
                source_bytes[source["source_name"]] = data
                source_records.append(
                    {
                        **source,
                        "row_count": len(rows),
                        "receipt_id": receipt["receipt_id"],
                        "first_observed_utc": payload["first_observed_utc"],
                        "ingested_utc": payload["ingested_utc"],
                        "observation_time_bounds": observation_bounds,
                    }
                )
                receipt_records.append(receipt)
                receipt_bytes[source["source_name"]] = receipt_data

    require(
        source_driver_sets["drivers"] == expected_participants,
        "participant_source_universe_mismatch",
    )
    participant_record = next(
        item for item in source_records if item["source_name"] == "drivers"
    )
    require(
        participant_record["session_id"] == request["target_session_id"],
        "participant_source_not_target_session",
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
        "source_capture_receipt_bytes": receipt_bytes,
        "source_driver_sets": {
            name: sorted(values) for name, values in sorted(source_driver_sets.items())
        },
        "broad_discovery_used": False,
        "provider_request_made": False,
        "production_authenticated": False,
        "dr002_activated": False,
        "promotion_allowed": False,
    }


def _producer_identity(repo_root, git_commit):
    relative = "scripts/forecasts/produce_actual_forecast_rows_v1.py"
    checkout_bytes = (Path(repo_root) / relative).read_bytes()
    try:
        committed_bytes = subprocess.run(
            ["git", "show", f"{git_commit}:{relative}"],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EventScopedInputError("producer_git_identity_unverifiable") from exc
    require(checkout_bytes == committed_bytes, "producer_checkout_differs_from_declared_commit")
    return sha256(checkout_bytes)


def _read_forecast_driver_numbers(payload_bytes):
    try:
        rows = list(csv.DictReader(io.StringIO(payload_bytes.decode("utf-8"), newline=""), strict=True))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise EventScopedInputError("malformed_producer_output") from exc
    require(bool(rows), "empty_producer_output")
    numbers = []
    for row in rows:
        value = producer.to_int(row.get("driver_number"))
        require(value is not None and value > 0, "invalid_output_driver")
        numbers.append(value)
    require(len(numbers) == len(set(numbers)), "duplicate_output_driver")
    return rows, set(numbers)


def _receipt(kind, request, parent_ids, payload, created):
    scope = {
        "event_id": request["event_id"],
        "meeting_id": request["meeting_id"],
        "session_id": request["target_session_id"],
        "product_id": "actual-forecast-rows-v1",
        "forecast_id": "forecast:" + sha256(canonical_json_bytes({
            "event_id": request["event_id"],
            "meeting_id": request["meeting_id"],
            "session_id": request["target_session_id"],
            "gate": request["gate"],
            "lane_name": request["lane_name"],
            "cutoff": request["forecast_cutoff_utc"],
        })),
        "gate": request["gate"],
        "lane_name": request["lane_name"],
    }
    identity = {
        "receipt_type": kind,
        "scope": scope,
        "parent_receipt_ids": parent_ids,
        "payload": payload,
    }
    result = {
        "schema_version": receipts.VERSION,
        "receipt_id": kind + ":" + sha256(canonical_json_bytes(identity)),
        "receipt_created_utc": created,
        **identity,
    }
    receipts.validate_receipt_envelope(result)
    receipts.verify_temporal_bindings(result)
    return result


def produce_and_lock_event_scoped_forecast(package_root, request_bytes, output_dir, *, repo_root):
    """Run the unchanged frozen producer once and retain exact inputs beside its lock.

    The caller must supply externally verified capture-receipt bindings.  They
    are retained but not authenticated or upgraded by this offline bridge.
    """
    validated = validate_event_scoped_input_package(package_root, request_bytes)
    request = validated["request"]
    output = Path(output_dir)
    require(not output.exists(), "output_already_exists")
    producer_code_sha256 = _producer_identity(repo_root, request["producer_git_commit"])

    with tempfile.TemporaryDirectory(prefix="event-scoped-forecast-run-") as directory:
        sandbox = Path(directory)
        inputs = sandbox / "frozen_inputs"
        inputs.mkdir()
        sources = {}
        counts = {name: 0 for name in producer.SOURCE_FILES}
        source_audit = {}
        for record in validated["sources"]:
            name = record["source_name"]
            path = inputs / (name + ".csv")
            path.write_bytes(validated["source_bytes"][name])
            require(sha256(path.read_bytes()) == record["source_sha256"], "snapshot_readback_mismatch")
            sources[name] = path
            counts[name] = record["row_count"]
            source_audit[name] = {
                key: record[key]
                for key in ("source_name", "source_id", "relative_path", "source_sha256", "row_count")
            }
        frozen_audit = {
            "input_mode": "event_scoped_frozen_manifest",
            "schema_version": SCHEMA,
            "frozen_manifest_sha256": validated["request_sha256"],
            "event_id": request["event_id"],
            "meeting_id": request["meeting_id"],
            "session_id": request["target_session_id"],
            "sources": [source_audit[name] for name in sorted(source_audit)],
            "broad_discovery_used": False,
            "production_authenticated": False,
            "historical_availability_proven": False,
            "stable_engine_execution_proven": False,
            "dr002_activated": False,
        }
        args = SimpleNamespace(
            event_id=request["event_id"],
            race_name=request["race_name"],
            gate=request["gate"],
            lane=request["lane_name"],
            strict_source=True,
        )
        generation_time = utc(request["forecast_generation_utc"])

        class FixedProducerDateTime:
            @classmethod
            def now(cls, tz=None):
                return generation_time

        with (
            redirect_stdout(io.StringIO()),
            patch.object(producer, "utc_now", lambda: request["forecast_generation_utc"]),
            patch.object(producer, "datetime", FixedProducerDateTime),
        ):
            code = producer._run_producer(
                args,
                sandbox,
                [request["gate"]],
                [request["lane_name"]],
                sources,
                counts,
                frozen_audit,
            )
        require(code == 0, "producer_failed")
        generated = sandbox / "latest" / "forecasts" / request["event_id"] / request["gate"] / request["lane_name"]
        payload_bytes = (generated / "forecast_rows.csv").read_bytes()
        rows, output_drivers = _read_forecast_driver_numbers(payload_bytes)
        require(
            output_drivers == set(validated["participant_driver_numbers"]),
            "producer_output_participant_universe_mismatch",
        )
        for row in rows:
            require(
                row.get("event_id") == request["event_id"]
                and row.get("gate") == request["gate"]
                and row.get("engine_lane") == request["lane_name"]
                and row.get("forecast_generation_utc") == request["forecast_generation_utc"],
                "producer_output_scope_mismatch",
            )

        product_id = "actual-forecast-rows-v1"
        forecast_id = "forecast:" + sha256(canonical_json_bytes({
            "event_id": request["event_id"],
            "meeting_id": request["meeting_id"],
            "session_id": request["target_session_id"],
            "gate": request["gate"],
            "lane_name": request["lane_name"],
            "cutoff": request["forecast_cutoff_utc"],
        }))
        evidence = []
        for record, capture in zip(validated["sources"], validated["source_capture_receipts"]):
            capture_payload = capture["payload"]
            evidence.append({
                "event_id": request["event_id"],
                "meeting_id": request["meeting_id"],
                "session_id": record["session_id"],
                "source_id": record["source_id"],
                "source_uri": capture_payload["source_uri"],
                "source_sha256": record["source_sha256"],
                "event_time_utc": capture_payload["event_time_utc"],
                "publisher_time_utc": capture_payload["publisher_time_utc"],
                "first_observed_utc": capture_payload["first_observed_utc"],
                "ingested_utc": capture_payload["ingested_utc"],
                "capture_evidence_ref": capture["receipt_id"],
                "ingestion_required_at_cutoff": record["ingestion_required_at_cutoff"],
            })
        evidence.sort(key=lambda item: item["source_id"])
        base = {
            "schema_version": integrity.VERSION,
            "legacy": False,
            "execution_mode": request["execution_mode"],
            "contract_approved": request["contract_approved"],
            "forecast_id": forecast_id,
            "product_id": product_id,
            "product_contract_id": request["product_contract_id"],
            "gate": request["gate"],
            "lane_name": request["lane_name"],
            "event_id": request["event_id"],
            "meeting_id": request["meeting_id"],
            "session_id": request["target_session_id"],
            "allowed_session_ids": request["allowed_session_ids"],
            "evidence_cutoff_utc": request["forecast_cutoff_utc"],
            "forecast_generation_utc": request["forecast_generation_utc"],
            "forecast_deadline_utc": request["forecast_deadline_utc"],
            "mandatory_source_ids": [item["source_id"] for item in evidence],
            "revision_policy": "none",
            "evidence": evidence,
            "revisions": [],
        }
        manifest_hash = integrity.input_manifest_sha256(base)
        payload_hash = sha256(payload_bytes)
        execution_id = "execution:" + sha256(canonical_json_bytes({
            "input_manifest_sha256": manifest_hash,
            "forecast_payload_sha256": payload_hash,
            "producer_git_commit": request["producer_git_commit"],
        }))
        producer_projection = {
            "implementation": "scripts/forecasts/produce_actual_forecast_rows_v1.py",
            "git_commit": request["producer_git_commit"],
            "code_sha256": producer_code_sha256,
            "execution_id": execution_id,
            "input_manifest_sha256": manifest_hash,
            "forecast_payload_sha256": payload_hash,
            "engine_implementation": None,
        }
        base["producer"] = producer_projection
        producer_receipt = _receipt(
            "producer_execution",
            request,
            sorted(item["receipt_id"] for item in validated["source_capture_receipts"]),
            {
                **producer_projection,
                "forecast_generation_utc": request["forecast_generation_utc"],
                "input_receipt_manifest_sha256": receipts.input_receipt_manifest_sha256(
                    validated["source_capture_receipts"]
                ),
                "engine_receipt_id": None,
                "engine_result_sha256": None,
            },
            request["forecast_generation_utc"],
        )
        lock_receipt = locker.build_forecast_lock(
            base,
            producer_receipt,
            payload_bytes,
            lock_utc=request["forecast_lock_utc"],
            receipt_created_utc=request["forecast_lock_utc"],
            storage_ref="bundle-relative:forecast_payload.csv",
        )
        base.update(
            forecast_lock_utc=request["forecast_lock_utc"],
            lock_receipt_ref=lock_receipt["receipt_id"],
            outcome_availability_boundary_utc=None,
            outcome_boundary_evidence_ref=None,
        )

        staging = output.parent / ("." + output.name + ".staging")
        require(not staging.exists(), "staging_output_exists")
        staging.mkdir(parents=True)
        try:
            retained = {
                "event_scoped_input_request.json": request_bytes,
                "forecast_payload.csv": payload_bytes,
                "forecast_input_contract.json": canonical_json_bytes(base),
                "producer_execution_receipt.json": canonical_json_bytes(producer_receipt),
                "forecast_lock_receipt.json": canonical_json_bytes(lock_receipt),
                "producer_audit.json": (next((sandbox / "_runtime" / "actual_forecast_producer_v1").iterdir()) / "actual_forecast_producer_audit.json").read_bytes(),
                "producer_source_snapshot_manifest.csv": (generated / "source_snapshot_manifest.csv").read_bytes(),
                "forecast_metadata.json": (generated / "forecast_metadata.json").read_bytes(),
            }
            for record in validated["sources"]:
                retained[record["relative_path"]] = validated["source_bytes"][record["source_name"]]
                retained[record["receipt_relative_path"]] = validated["source_capture_receipt_bytes"][record["source_name"]]
            for relative, data in sorted(retained.items()):
                path = staging / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                require(path.read_bytes() == data, "retained_evidence_readback_mismatch")
            file_manifest = [
                {"relative_path": relative, "byte_count": len(data), "sha256": sha256(data)}
                for relative, data in sorted(retained.items())
            ]
            evidence_manifest = {
                "schema_version": "f1-event-scoped-forecast-lock-package-v1",
                "status": "LOCKED_OUTPUT_WITH_RETAINED_INPUT_EVIDENCE",
                "event_id": request["event_id"],
                "meeting_id": request["meeting_id"],
                "target_session_id": request["target_session_id"],
                "forecast_cutoff_utc": request["forecast_cutoff_utc"],
                "participant_driver_numbers": validated["participant_driver_numbers"],
                "files": file_manifest,
                "production_authenticated": False,
                "contract_approved": request["contract_approved"],
                "dr002_activated": False,
                "promotion_allowed": False,
            }
            manifest_bytes = canonical_json_bytes(evidence_manifest)
            (staging / "bundle_evidence_manifest.json").write_bytes(manifest_bytes)
            for item in file_manifest:
                data = (staging / item["relative_path"]).read_bytes()
                require(len(data) == item["byte_count"] and sha256(data) == item["sha256"], "final_bundle_readback_mismatch")
            staging.rename(output)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    return {
        "status": "LOCKED_OUTPUT_WITH_RETAINED_INPUT_EVIDENCE",
        "output_dir": str(output),
        "forecast_payload_sha256": payload_hash,
        "input_manifest_sha256": manifest_hash,
        "producer_receipt_sha256": receipts.receipt_sha256(producer_receipt),
        "forecast_lock_receipt_sha256": receipts.receipt_sha256(lock_receipt),
        "bundle_evidence_manifest_sha256": sha256(manifest_bytes),
        "participant_driver_numbers": validated["participant_driver_numbers"],
        "row_count": len(rows),
        "production_authenticated": False,
        "contract_approved": request["contract_approved"],
        "dr002_activated": False,
        "promotion_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate event-scoped frozen inputs and retain them beside one locked forecast."
    )
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-root", default=str(HERE.parents[1]))
    args = parser.parse_args()
    request_path = Path(args.request)
    result = produce_and_lock_event_scoped_forecast(
        args.package_root,
        request_path.read_bytes(),
        args.output_dir,
        repo_root=args.repo_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
