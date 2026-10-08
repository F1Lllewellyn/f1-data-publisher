"""Contained dual-OpenF1-source to real frozen-producer CLI composition.

Exact parentless weather and drivers source-capture receipts and raw bytes stay
the scientific evidence. Their adapter CSVs are derived runtime forms. The
starting grid is a deterministic synthetic mechanics fixture. All producer
writes are confined to one disposable sandbox and copied only into the returned
in-memory result before disposal.
"""
import csv
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import dr002_openf1_drivers_producer_adapter_v1 as drivers_adapter
import dr002_openf1_weather_frozen_producer_composition_v1 as k4r5
import dr002_openf1_weather_producer_adapter_v1 as weather_adapter


REPO_ROOT = k4r5.REPO_ROOT
PRODUCER_PATH = k4r5.PRODUCER_PATH
PRODUCER_BLOB_SHA = k4r5.PRODUCER_BLOB_SHA
FROZEN_SCHEMA = k4r5.FROZEN_SCHEMA
SCHEMA_VERSION = (
    "dr002-openf1-weather-drivers-frozen-producer-composition-v1"
)
VALIDATED = (
    "DUAL_SOURCE_FROZEN_PRODUCER_MECHANICS_ONLY_NOT_A_PREDICTION"
)
HOLD = "HOLD"
GATE = k4r5.GATE
LANE = k4r5.LANE
RACE_NAME = (
    "Dual provenance weather and drivers with synthetic grid mechanics shadow "
    "- NOT A PREDICTION"
)
EXPECTED_SOURCE_NAMES = ("drivers", "starting_grid", "weather")
PRODUCER_SOURCE_NAMES = k4r5.PRODUCER_SOURCE_NAMES
DEPENDENCY_BLOBS = {
    "scripts/forecast_bundles/dr002_openf1_weather_producer_adapter_v1.py":
        "5061d8007d06c37e164df2c6cc643e385be885f8",
    "scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py":
        "357ac56a6cfe317e21d9ce71d78c58683e444a5a",
    "scripts/forecast_bundles/dr002_openf1_weather_frozen_producer_composition_v1.py":
        "090c61af27ef932aae51a8fb83fe828c20c13a68",
    "tests/test_dr002_openf1_weather_frozen_producer_composition_v1.py":
        "4079b6ba65b582b67112fa291afad46d3b44b7bd",
    "scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py":
        "8dfd855184b172ce88235ee7de3ea33a68031b2e",
    "scripts/forecasts/produce_actual_forecast_rows_v1.py":
        "af27586668c767de126af829c1131c6bae4634ad",
    "docs/DR002_PRE2B7K4R3_ONE_HISTORICAL_OPENF1_REST_SHADOW_RUN_2026-10-08.md":
        "db92fb23ff0adf95e59a80f14dcd527b6d1f9906",
    "docs/DR002_PRE2B7K4R8_ONE_HISTORICAL_OPENF1_DRIVERS_SHADOW_RUN_2026-10-08.md":
        "943440c604163913a95690322bdcdfc850e03b58",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}

# Reuse the accepted K4R5 containment and evidence-reading helpers.
_digest = k4r5._digest
_git_blob_sha = k4r5._git_blob_sha
_json_bytes = k4r5._json_bytes
_read_csv = k4r5._read_csv
_scope_text = k4r5._scope_text
_write_checked = k4r5._write_checked
_checked_out_output_fingerprint = k4r5._checked_out_output_fingerprint
_expected_counts = k4r5._expected_counts
_sandbox_evidence = k4r5._sandbox_evidence
_verify_sandbox_files = k4r5._verify_sandbox_files


class CompositionError(ValueError):
    """A composition invariant failed and the complete result must HOLD."""


def _require(condition, reason):
    if not condition:
        raise CompositionError(reason)


def _receipt(data):
    _require(type(data) is bytes and bool(data), "receipt_not_nonempty_bytes")
    value = weather_adapter.frozen_contract.strict_json(data)
    _require(type(value) is dict, "malformed_source_receipt")
    return value


def _driver_records(drivers_csv_bytes):
    _require(type(drivers_csv_bytes) is bytes and bool(drivers_csv_bytes),
             "empty_drivers_csv")
    try:
        reader = csv.DictReader(
            io.StringIO(drivers_csv_bytes.decode("utf-8"), newline=""),
            strict=True,
        )
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CompositionError("malformed_drivers_csv") from exc
    _require(tuple(reader.fieldnames or ()) == drivers_adapter.CSV_FIELDS,
             "drivers_csv_header_mismatch")
    _require(bool(rows), "empty_drivers_csv")
    records = {}
    for row in rows:
        _require(None not in row and all(value is not None for value in row.values()),
                 "malformed_drivers_csv_row")
        try:
            number = int(row["driver_number"])
        except (TypeError, ValueError) as exc:
            raise CompositionError("malformed_driver_number") from exc
        _require(number > 0 and str(number) == row["driver_number"],
                 "malformed_driver_number")
        _require(number not in records, "duplicate_driver_number")
        _require(row["broadcast_name"] and row["full_name"] and row["team_name"],
                 "missing_driver_identity")
        records[number] = {
            "driver_number": str(number),
            "driver_name": row["broadcast_name"],
            "full_name": row["full_name"],
            "team_name": row["team_name"],
        }
    return records


def _synthetic_grid(drivers_csv_bytes, event_id, meeting_id, session_id):
    records = _driver_records(drivers_csv_bytes)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("driver_number", "position", "event_id", "meeting_id",
                     "session_id"))
    for position, number in enumerate(sorted(records), start=1):
        writer.writerow((number, position, event_id, meeting_id, session_id))
    return stream.getvalue().encode("utf-8"), records


def _validate_adapter_result(result, *, adapter_status, scope, source_name,
                             filename, receipt, raw_bytes):
    _require(result.get("status") == adapter_status,
             "k4r4_adapter_hold" if source_name == "weather"
             else "k4r6_adapter_hold")
    _require(result.get("scope") == scope, "adapter_scope_mismatch")
    _require(result.get("producer_input_source_name") == source_name
             and result.get("producer_input_filename") == filename,
             "adapter_output_identity_mismatch")
    _require(type(result.get("row_count")) is int
             and result["row_count"] > 0, "adapter_row_count_invalid")
    _require(type(result.get("producer_input_csv_bytes")) is bytes
             and bool(result["producer_input_csv_bytes"]),
             "adapter_csv_missing")
    _require(result.get("producer_input_sha256")
             == _digest(result["producer_input_csv_bytes"]),
             "adapter_csv_hash_mismatch")
    payload = receipt["payload"]
    _require(result.get("source_receipt_id") == receipt["receipt_id"],
             "adapter_receipt_identity_mismatch")
    _require(result.get("raw_source_sha256") == _digest(raw_bytes)
             == payload["source_sha256"], "adapter_raw_hash_mismatch")
    manifest = result.get("frozen_evidence_manifest")
    _require(type(manifest) is dict
             and manifest.get("trust") == weather_adapter.frozen_contract.TRUST,
             "adapter_raw_trust_changed")
    evidence = manifest.get("evidence")
    _require(type(evidence) is list and len(evidence) == 1,
             "adapter_raw_manifest_shape_mismatch")
    bound = evidence[0]
    _require(bound.get("receipt_id") == receipt["receipt_id"]
             and bound.get("source_id") == payload["source_id"]
             and bound.get("source_sha256") == payload["source_sha256"]
             and bound.get("session_id") == scope["session_id"],
             "adapter_raw_binding_mismatch")
    _require(result.get("frozen_evidence_manifest_sha256")
             == _digest(_json_bytes(manifest)),
             "adapter_raw_manifest_hash_mismatch")
    for field in ("derived_csv_is_source_evidence",
                  "new_scientific_receipt_created",
                  "normalization_receipt_created",
                  "verified_receipt_bindings_created",
                  "stable_engine_execution_proven",
                  "blind_validation_eligible",
                  "production_forecast_generated",
                  "dr002_activated", "promotion_allowed"):
        _require(result.get(field) is False, "adapter_trust_ceiling_changed")


def _build_manifest(event_id, meeting_id, session_id, inputs,
                    drivers_source_id, weather_source_id):
    _require(set(inputs) == set(EXPECTED_SOURCE_NAMES),
             "unexpected_producer_input_set")
    grid_hash = _digest(inputs["starting_grid"])
    identities = {
        "drivers": drivers_source_id,
        "starting_grid": "synthetic:starting-grid-csv:" + grid_hash,
        "weather": weather_source_id,
    }
    _require(len(set(identities.values())) == len(identities),
             "duplicate_runtime_source_identity")
    sources = []
    for name in EXPECTED_SOURCE_NAMES:
        sources.append({
            "source_name": name,
            "source_id": identities[name],
            "relative_path": name + ".csv",
            "source_sha256": _digest(inputs[name]),
        })
    return {
        "schema_version": FROZEN_SCHEMA,
        "event_id": event_id,
        "meeting_id": meeting_id,
        "session_id": session_id,
        "sources": sources,
    }


def _verify_producer_evidence(*, audit, metadata, forecast_rows, snapshot,
                              manifest, manifest_bytes, inputs,
                              weather_result, drivers_result, driver_records):
    """Verify the K4R9 dynamic-N differential against the unchanged producer."""
    expected_sources, expected_counts = _expected_counts(manifest, inputs)
    scope = {key: manifest[key] for key in
             ("event_id", "meeting_id", "session_id")}
    for record in (audit, metadata):
        _require(record.get("input_mode") == "frozen_manifest",
                 "producer_not_in_frozen_mode")
        _require(record.get("broad_discovery_used") is False,
                 "producer_used_broad_discovery")
        _require(record.get("schema_version") == FROZEN_SCHEMA,
                 "producer_frozen_schema_mismatch")
        _require(record.get("frozen_manifest_sha256") == _digest(manifest_bytes),
                 "producer_manifest_hash_mismatch")
        _require(all(record.get(key) == value for key, value in scope.items()),
                 "producer_scope_mismatch")
        _require(record.get("sources") == expected_sources,
                 "producer_source_binding_mismatch")
        _require(record.get("source_counts") == expected_counts,
                 "producer_source_counts_mismatch")
        _require(record.get("production_authenticated") is False
                 and record.get("historical_availability_proven") is False
                 and record.get("stable_engine_execution_proven") is False
                 and record.get("dr002_activated") is False,
                 "producer_unsupported_trust_claim")

    count = len(driver_records)
    _require(audit.get("status") == "forecast_rows_created",
             "producer_did_not_create_rows")
    _require(audit.get("requested_gate") == GATE and audit.get("gates") == [GATE],
             "producer_gate_mismatch")
    _require(audit.get("requested_lane") == LANE and audit.get("lanes") == [LANE],
             "producer_lane_mismatch")
    _require(audit.get("race_name") == RACE_NAME,
             "producer_race_name_mismatch")
    _require(audit.get("driver_universe_count") == count
             and audit.get("forecast_rows_created") == count
             and audit.get("gate_lane_files_created") == 1,
             "unexpected_producer_execution_shape")
    _require(metadata.get("gate") == GATE and metadata.get("engine_lane") == LANE
             and metadata.get("row_count") == count,
             "producer_metadata_mismatch")

    _require(len(forecast_rows) == count, "unexpected_generated_driver_rows")
    by_number = {}
    for row in forecast_rows:
        number = row.get("driver_number")
        try:
            numeric_number = int(number)
        except (TypeError, ValueError) as exc:
            raise CompositionError("unexpected_generated_driver_rows") from exc
        _require(numeric_number in driver_records and number not in by_number,
                 "unexpected_generated_driver_rows")
        expected = driver_records[numeric_number]
        _require(row.get("driver_name") == expected["driver_name"]
                 and row.get("team_name") == expected["team_name"],
                 "generated_driver_identity_mismatch")
        _require(row.get("grid_position")
                 == str(sorted(driver_records).index(numeric_number) + 1),
                 "synthetic_grid_position_mismatch")
        _require(row.get("event_id") == scope["event_id"]
                 and row.get("gate") == GATE
                 and row.get("engine_lane") == LANE
                 and row.get("race_name") == RACE_NAME,
                 "forecast_row_scope_mismatch")
        by_number[number] = row
    _require(set(by_number) == {str(number) for number in driver_records},
             "generated_driver_membership_mismatch")
    _require({float(row["source_readiness_score"]) for row in forecast_rows}
             == {0.48}, "unexpected_source_readiness")
    generation_times = {row.get("forecast_generation_utc")
                        for row in forecast_rows}
    _require(len(generation_times) == 1
             and next(iter(generation_times), "").endswith("Z"),
             "invalid_forecast_generation_time")

    _require(len(snapshot) == len(PRODUCER_SOURCE_NAMES)
             and {row["source_name"] for row in snapshot}
             == set(PRODUCER_SOURCE_NAMES), "source_snapshot_shape_mismatch")
    by_name = {entry["source_name"]: entry for entry in expected_sources}
    for row in snapshot:
        expected = by_name.get(row["source_name"])
        _require(row["row_count"] == str(expected_counts[row["source_name"]]),
                 "source_snapshot_row_count_mismatch")
        _require(row["found"] == ("True" if expected else "False"),
                 "source_snapshot_found_mismatch")
        _require(row.get("source_id") == (expected["source_id"] if expected else "")
                 and row.get("source_sha256")
                 == (expected["source_sha256"] if expected else "")
                 and row.get("relative_path")
                 == (expected["relative_path"] if expected else "")
                 and row.get("path") == row.get("relative_path"),
                 "source_snapshot_binding_mismatch")

    _require(by_name["weather"]["source_sha256"]
             == weather_result["producer_input_sha256"]
             and by_name["weather"]["row_count"] == weather_result["row_count"],
             "weather_adapter_propagation_mismatch")
    _require(by_name["drivers"]["source_id"]
             == drivers_result["derived_runtime_identity"]
             and by_name["drivers"]["source_sha256"]
             == drivers_result["producer_input_sha256"]
             and by_name["drivers"]["row_count"] == drivers_result["row_count"],
             "drivers_adapter_propagation_mismatch")
    _require(by_name["starting_grid"]["source_id"].startswith(
        "synthetic:starting-grid-csv:"), "grid_not_synthetic")
    return expected_sources, expected_counts, next(iter(generation_times))


def _hold(reason, *, producer_attempted=False):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HOLD,
        "reason_codes": [reason],
        "producer_execution_attempted": producer_attempted,
        "new_scientific_receipt_created": False,
        "normalization_receipt_created": False,
        "verified_receipt_bindings_created": False,
        "stable_engine_executed": False,
        "production_forecast_generated": False,
        "blind_validation_eligible": False,
        "production_authenticated": False,
        "historical_availability_proven": False,
        "dr002_activated": False,
        "promotion_allowed": False,
    }


def compose_openf1_weather_drivers_into_frozen_producer(
    *,
    weather_source_capture_receipt_bytes,
    raw_weather_response_bytes,
    drivers_source_capture_receipt_bytes,
    raw_drivers_response_bytes,
    event_id,
    meeting_id,
    session_id,
    implementation_git_sha,
):
    """Execute the unchanged real producer once with two evidenced sources.

    No source discovery, capture, network or caller-supplied forecast time is
    permitted. Any failure returns HOLD without partial evidence or CSV bytes;
    the producer subprocess is never retried.
    """
    producer_attempted = False
    try:
        event_id = _scope_text(event_id)
        meeting_id = _scope_text(meeting_id)
        session_id = _scope_text(session_id)
        scope = {
            "event_id": event_id,
            "meeting_id": meeting_id,
            "session_id": session_id,
        }
        _require(type(implementation_git_sha) is str
                 and re.fullmatch(r"[0-9a-f]{40}", implementation_git_sha),
                 "invalid_implementation_git_sha")

        # Both accepted adapters are always called before either result is used
        # to build the producer manifest or materialize derived input files.
        weather_result = weather_adapter.adapt_openf1_weather_to_producer_input(
            source_capture_receipt_bytes=weather_source_capture_receipt_bytes,
            raw_weather_response_bytes=raw_weather_response_bytes,
            **scope,
        )
        drivers_result = drivers_adapter.adapt_openf1_drivers_to_producer_input(
            source_capture_receipt_bytes=drivers_source_capture_receipt_bytes,
            raw_drivers_response_bytes=raw_drivers_response_bytes,
            **scope,
        )
        _require(weather_result.get("status") == weather_adapter.VALIDATED,
                 "k4r4_adapter_hold")
        _require(drivers_result.get("status") == drivers_adapter.VALIDATED,
                 "k4r6_adapter_hold")

        weather_receipt = _receipt(weather_source_capture_receipt_bytes)
        drivers_receipt = _receipt(drivers_source_capture_receipt_bytes)
        _validate_adapter_result(
            weather_result, adapter_status=weather_adapter.VALIDATED,
            scope=scope, source_name="weather", filename="weather.csv",
            receipt=weather_receipt, raw_bytes=raw_weather_response_bytes,
        )
        _validate_adapter_result(
            drivers_result, adapter_status=drivers_adapter.VALIDATED,
            scope=scope, source_name="drivers", filename="drivers.csv",
            receipt=drivers_receipt, raw_bytes=raw_drivers_response_bytes,
        )
        _require(weather_receipt["receipt_id"] != drivers_receipt["receipt_id"],
                 "duplicate_raw_receipt_identity")
        weather_raw_source_id = weather_receipt["payload"]["source_id"]
        drivers_raw_source_id = drivers_receipt["payload"]["source_id"]
        _require(weather_raw_source_id != drivers_raw_source_id,
                 "duplicate_raw_source_identity")
        _require(drivers_result.get("raw_source_id") == drivers_raw_source_id,
                 "drivers_raw_source_identity_mismatch")

        drivers_bytes = drivers_result["producer_input_csv_bytes"]
        weather_bytes = weather_result["producer_input_csv_bytes"]
        grid_bytes, driver_records = _synthetic_grid(
            drivers_bytes, event_id, meeting_id, session_id
        )
        _require(len(driver_records) == drivers_result["row_count"]
                 == drivers_result["unique_driver_count"],
                 "drivers_universe_count_mismatch")
        inputs = {
            "drivers": drivers_bytes,
            "starting_grid": grid_bytes,
            "weather": weather_bytes,
        }
        weather_source_id = (
            "derived:openf1-weather-csv:" + weather_result["producer_input_sha256"]
        )
        drivers_source_id = drivers_result["derived_runtime_identity"]
        manifest = _build_manifest(
            event_id, meeting_id, session_id, inputs,
            drivers_source_id, weather_source_id,
        )
        manifest_bytes = _json_bytes(manifest)
        runtime_ids = {entry["source_id"] for entry in manifest["sources"]}
        _require(runtime_ids.isdisjoint(
            {weather_raw_source_id, drivers_raw_source_id}
        ), "raw_source_id_reused_for_runtime_input")
        _require(weather_source_id != drivers_source_id,
                 "derived_source_id_collision")

        producer_code = PRODUCER_PATH.read_bytes()
        _require(_git_blob_sha(producer_code) == PRODUCER_BLOB_SHA,
                 "producer_fingerprint_changed")
        checkout_before = _checked_out_output_fingerprint()

        with tempfile.TemporaryDirectory(
            prefix="dr002-openf1-weather-drivers-frozen-producer-composition-"
        ) as directory:
            sandbox = Path(directory)
            inputs_root = sandbox / "inputs"
            for name in EXPECTED_SOURCE_NAMES:
                _write_checked(inputs_root / (name + ".csv"), inputs[name])
            manifest_path = inputs_root / "frozen_input_manifest.json"
            _write_checked(manifest_path, manifest_bytes)
            command = [
                sys.executable,
                str(PRODUCER_PATH),
                "--frozen-input-manifest", str(manifest_path),
                "--event-id", event_id,
                "--meeting-id", meeting_id,
                "--session-id", session_id,
                "--race-name", RACE_NAME,
                "--gate", GATE,
                "--lane", LANE,
                "--repo-root", str(sandbox),
                "--strict-source",
            ]
            producer_attempted = True
            completed = subprocess.run(
                command,
                cwd=sandbox,
                env={"PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            _require(completed.returncode == 0, "producer_subprocess_failed")
            _require(PRODUCER_PATH.read_bytes() == producer_code,
                     "producer_changed_during_execution")
            audit = json.loads(completed.stdout)
            producer_run_id = audit.get("run_id")
            _require(type(producer_run_id) is str
                     and re.fullmatch(r"\d{8}T\d{6}Z", producer_run_id),
                     "invalid_producer_run_id")
            evidence = _sandbox_evidence(sandbox, producer_run_id, event_id)
            _require(json.loads(evidence["producer_audit.json"]) == audit,
                     "producer_stdout_audit_mismatch")
            metadata = json.loads(evidence["forecast_metadata.json"])
            forecast_rows = _read_csv(evidence["forecast_rows.csv"])
            snapshot = _read_csv(evidence["source_snapshot_manifest.csv"])
            declared_sources, source_counts, generation_time = (
                _verify_producer_evidence(
                    audit=audit,
                    metadata=metadata,
                    forecast_rows=forecast_rows,
                    snapshot=snapshot,
                    manifest=manifest,
                    manifest_bytes=manifest_bytes,
                    inputs=inputs,
                    weather_result=weather_result,
                    drivers_result=drivers_result,
                    driver_records=driver_records,
                )
            )
            sandbox_files = _verify_sandbox_files(
                sandbox, producer_run_id, event_id
            )
            evidence_hashes = {name: _digest(data)
                               for name, data in sorted(evidence.items())}
        _require(not sandbox.exists(), "producer_sandbox_not_disposed")
        _require(_checked_out_output_fingerprint() == checkout_before,
                 "checked_out_production_output_mutation")
        _require(_git_blob_sha(PRODUCER_PATH.read_bytes()) == PRODUCER_BLOB_SHA,
                 "producer_fingerprint_changed_after_execution")

        grid_entry = next(entry for entry in manifest["sources"]
                          if entry["source_name"] == "starting_grid")
        return {
            "schema_version": SCHEMA_VERSION,
            "status": VALIDATED,
            "reason_codes": [],
            "scope": scope,
            "implementation_git_sha": implementation_git_sha,
            "raw_weather_source_receipt_id": weather_receipt["receipt_id"],
            "raw_weather_source_id": weather_raw_source_id,
            "raw_weather_sha256": weather_result["raw_source_sha256"],
            "weather_raw_frozen_evidence_manifest":
                weather_result["frozen_evidence_manifest"],
            "weather_raw_frozen_evidence_manifest_sha256":
                weather_result["frozen_evidence_manifest_sha256"],
            "raw_drivers_source_receipt_id": drivers_receipt["receipt_id"],
            "raw_drivers_source_id": drivers_raw_source_id,
            "raw_drivers_sha256": drivers_result["raw_source_sha256"],
            "drivers_raw_frozen_evidence_manifest":
                drivers_result["frozen_evidence_manifest"],
            "drivers_raw_frozen_evidence_manifest_sha256":
                drivers_result["frozen_evidence_manifest_sha256"],
            "derived_weather_source_id": weather_source_id,
            "derived_weather_csv_sha256": weather_result["producer_input_sha256"],
            "derived_weather_row_count": weather_result["row_count"],
            "derived_drivers_source_id": drivers_source_id,
            "derived_drivers_csv_sha256": drivers_result["producer_input_sha256"],
            "derived_drivers_row_count": drivers_result["row_count"],
            "driver_universe_count": len(driver_records),
            "starting_grid_synthetic": True,
            "synthetic_starting_grid_source_id": grid_entry["source_id"],
            "synthetic_starting_grid_sha256": grid_entry["source_sha256"],
            "synthetic_starting_grid_row_count": len(driver_records),
            "weather_source_receipt_validated": True,
            "drivers_source_receipt_validated": True,
            "dual_source_mechanics_only": True,
            "producer_implementation":
                "scripts/forecasts/produce_actual_forecast_rows_v1.py",
            "producer_git_blob_sha": PRODUCER_BLOB_SHA,
            "producer_code_sha256": _digest(producer_code),
            "frozen_producer_input_manifest": manifest,
            "frozen_producer_input_manifest_bytes": manifest_bytes,
            "frozen_producer_input_manifest_sha256": _digest(manifest_bytes),
            "producer_input_bytes": inputs,
            "declared_sources": declared_sources,
            "source_counts": source_counts,
            "producer_run_id": producer_run_id,
            "forecast_generation_utc": generation_time,
            "gate": GATE,
            "lane": LANE,
            "generated_row_count": len(forecast_rows),
            "source_readiness": 0.48,
            "producer_evidence_bytes": evidence,
            "producer_evidence_sha256": evidence_hashes,
            "producer_output_paths": sandbox_files,
            "producer_command": command,
            "producer_executed": True,
            "producer_subprocess_attempt_count": 1,
            "broad_discovery_used": False,
            "producer_output_sandbox_disposed": True,
            "checkout_latest_history_unchanged": True,
            "derived_weather_is_source_evidence": False,
            "derived_drivers_is_source_evidence": False,
            "synthetic_grid_is_observed_or_fia_official": False,
            "new_scientific_receipt_created": False,
            "normalization_receipt_created": False,
            "producer_execution_receipt_created": False,
            "verified_receipt_bindings_created": False,
            "stable_engine_executed": False,
            "production_forecast_generated": False,
            "blind_validation_eligible": False,
            "production_authenticated": False,
            "historical_availability_proven": False,
            "dr002_activated": False,
            "promotion_allowed": False,
        }
    except (CompositionError, OSError, ValueError, TypeError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as exc:
        return _hold(str(exc) or type(exc).__name__,
                     producer_attempted=producer_attempted)
