"""Contained K4R4-weather to real frozen-producer CLI composition.

The OpenF1 receipt and exact raw bytes remain the only scientific source
evidence.  The weather CSV is a derived runtime representation.  Drivers and
starting grid are deterministic synthetic mechanics fixtures.  All producer
writes occur inside one disposable temporary sandbox and are copied only into
the returned in-memory result before that sandbox is removed.
"""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

import dr002_openf1_weather_producer_adapter_v1 as weather_adapter


REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCER_PATH = REPO_ROOT / "scripts/forecasts/produce_actual_forecast_rows_v1.py"
PRODUCER_BLOB_SHA = "af27586668c767de126af829c1131c6bae4634ad"
FROZEN_SCHEMA = "dr002-frozen-producer-input-v1"
SCHEMA_VERSION = "dr002-openf1-weather-frozen-producer-composition-v1"
VALIDATED = "MIXED_INPUT_FROZEN_PRODUCER_COMPOSITION_VALIDATED_NOT_A_PREDICTION"
HOLD = "HOLD"
GATE = "post_event"
LANE = "experimental_challenger"
RACE_NAME = "Mixed-input provenance weather mechanics shadow - NOT A PREDICTION"
EXPECTED_SOURCE_NAMES = ("drivers", "starting_grid", "weather")
PRODUCER_SOURCE_NAMES = (
    "drivers",
    "starting_grid",
    "intervals",
    "stints",
    "weather",
    "race_control",
    "pit",
    "position",
    "source_readiness",
)
DEPENDENCY_BLOBS = {
    "scripts/forecast_bundles/dr002_openf1_weather_producer_adapter_v1.py":
        "5061d8007d06c37e164df2c6cc643e385be885f8",
    "tests/test_dr002_openf1_weather_producer_adapter_v1.py":
        "6ef4b05456a9c26687755206dcaea32b2ed7f8d0",
    "scripts/forecasts/produce_actual_forecast_rows_v1.py":
        "af27586668c767de126af829c1131c6bae4634ad",
    "scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py":
        "1d3bfaf713807e799a6323875de670dc8d4e1a85",
    "scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py":
        "8dfd855184b172ce88235ee7de3ea33a68031b2e",
    "scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py":
        "ccd17a28744f0e7c6706c3be9562d57b7dcea0ae",
    "docs/DR002_PRE2B7K4R3_ONE_HISTORICAL_OPENF1_REST_SHADOW_RUN_2026-10-08.md":
        "db92fb23ff0adf95e59a80f14dcd527b6d1f9906",
    "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md":
        "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
}


class CompositionError(ValueError):
    """A composition invariant failed and the result must HOLD."""


def _require(condition, reason):
    if not condition:
        raise CompositionError(reason)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _git_blob_sha(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def _json_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _read_csv(data):
    _require(type(data) is bytes and bool(data), "empty_csv_bytes")
    try:
        reader = csv.DictReader(
            io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True
        )
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CompositionError("malformed_csv") from exc
    _require(reader.fieldnames and rows, "empty_or_headerless_csv")
    _require(all(None not in row and all(value is not None for value in row.values())
                 for row in rows), "malformed_csv_row_width")
    return rows


def _scope_text(value):
    _require(type(value) is str and value.strip() == value and bool(value),
             "malformed_scope")
    _require(not any(ord(character) < 32 or ord(character) == 127
                     for character in value), "malformed_scope")
    return value


def _synthetic_inputs(event_id, meeting_id, session_id):
    drivers = (
        "driver_number,full_name,team_name,event_id,meeting_id,session_id\n"
        f"10,Synthetic Ten,Synthetic Team A,{event_id},{meeting_id},{session_id}\n"
        f"20,Synthetic Twenty,Synthetic Team B,{event_id},{meeting_id},{session_id}\n"
    ).encode("utf-8")
    starting_grid = (
        "driver_number,position,event_id,meeting_id,session_id\n"
        f"20,1,{event_id},{meeting_id},{session_id}\n"
        f"10,2,{event_id},{meeting_id},{session_id}\n"
    ).encode("utf-8")
    return {"drivers": drivers, "starting_grid": starting_grid}


def _source_id(name, data):
    digest = _digest(data)
    if name == "weather":
        return "derived:openf1-weather-csv:" + digest
    return "synthetic:" + name.replace("_", "-") + "-csv:" + digest


def _build_manifest(event_id, meeting_id, session_id, inputs):
    _require(set(inputs) == set(EXPECTED_SOURCE_NAMES),
             "unexpected_producer_input_set")
    sources = []
    for name in EXPECTED_SOURCE_NAMES:
        data = inputs[name]
        sources.append({
            "source_name": name,
            "source_id": _source_id(name, data),
            "relative_path": name + ".csv",
            "source_sha256": _digest(data),
        })
    return {
        "schema_version": FROZEN_SCHEMA,
        "event_id": event_id,
        "meeting_id": meeting_id,
        "session_id": session_id,
        "sources": sources,
    }


def _write_checked(path, data):
    _require(type(data) is bytes and bool(data), "empty_materialized_input")
    _require(not path.exists() and not path.is_symlink(),
             "unexpected_existing_sandbox_input")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _require(path.read_bytes() == data, "sandbox_input_readback_mismatch")


def _tree_metadata_fingerprint(root):
    """Cheaply detect any checked-out latest/history tree mutation.

    File content is not reread; path, type, size, mode and nanosecond mtime are
    sufficient to detect ordinary writes while avoiding ceremonial rehashing of
    the repository's large accepted generated-output history.
    """
    if not root.exists():
        return "absent"
    records = []
    for current, directories, files in os.walk(root, followlinks=False):
        directories.sort()
        files.sort()
        current_path = Path(current)
        for name in directories + files:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            kind = "link" if stat.S_ISLNK(info.st_mode) else (
                "dir" if stat.S_ISDIR(info.st_mode) else "file"
            )
            target = os.readlink(path) if kind == "link" else ""
            records.append((relative, kind, info.st_size,
                            stat.S_IMODE(info.st_mode), info.st_mtime_ns, target))
    return _digest(_json_bytes(records))


def _checked_out_output_fingerprint():
    return {
        "latest": _tree_metadata_fingerprint(REPO_ROOT / "latest"),
        "history": _tree_metadata_fingerprint(REPO_ROOT / "history"),
    }


def _expected_counts(manifest, inputs):
    counts = {name: 0 for name in PRODUCER_SOURCE_NAMES}
    records = []
    for entry in sorted(manifest["sources"], key=lambda item: item["source_name"]):
        row_count = len(_read_csv(inputs[entry["source_name"]]))
        counts[entry["source_name"]] = row_count
        records.append(dict(entry, row_count=row_count))
    return records, counts


def _verify_producer_evidence(*, audit, metadata, forecast_rows, snapshot,
                              manifest, manifest_bytes, inputs, adapter_result):
    expected_sources, expected_counts = _expected_counts(manifest, inputs)
    scope = {
        "event_id": manifest["event_id"],
        "meeting_id": manifest["meeting_id"],
        "session_id": manifest["session_id"],
    }
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

    _require(audit.get("status") == "forecast_rows_created",
             "producer_did_not_create_rows")
    _require(audit.get("requested_gate") == GATE and audit.get("gates") == [GATE],
             "producer_gate_mismatch")
    _require(audit.get("requested_lane") == LANE and audit.get("lanes") == [LANE],
             "producer_lane_mismatch")
    _require(audit.get("race_name") == RACE_NAME,
             "producer_race_name_mismatch")
    _require(audit.get("driver_universe_count") == 2
             and audit.get("forecast_rows_created") == 2
             and audit.get("gate_lane_files_created") == 1,
             "unexpected_producer_execution_shape")
    _require(metadata.get("gate") == GATE and metadata.get("engine_lane") == LANE
             and metadata.get("row_count") == 2,
             "producer_metadata_mismatch")
    _require(len(forecast_rows) == 2
             and {row.get("driver_number") for row in forecast_rows} == {"10", "20"},
             "unexpected_generated_driver_rows")
    _require(all(row.get("event_id") == scope["event_id"]
                 and row.get("gate") == GATE
                 and row.get("engine_lane") == LANE
                 and row.get("race_name") == RACE_NAME
                 for row in forecast_rows), "forecast_row_scope_mismatch")

    readiness_values = {float(row["source_readiness_score"])
                        for row in forecast_rows}
    _require(readiness_values == {0.48}, "unexpected_source_readiness")
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

    weather = by_name["weather"]
    _require(weather["source_sha256"] == adapter_result["producer_input_sha256"]
             and weather["row_count"] == adapter_result["row_count"],
             "weather_adapter_propagation_mismatch")
    return expected_sources, expected_counts, next(iter(generation_times))


def _sandbox_evidence(sandbox, producer_run_id, event_id):
    runtime = sandbox / "_runtime/actual_forecast_producer_v1" / producer_run_id
    latest = sandbox / "latest/forecasts" / event_id / GATE / LANE
    history = sandbox / "history/forecasts" / event_id / producer_run_id / GATE / LANE
    latest_mirror = sandbox / "latest/forecast_outputs" / event_id / GATE / LANE
    history_mirror = (
        sandbox / "history/forecast_outputs" / event_id / producer_run_id / GATE / LANE
    )
    evidence = {
        "producer_audit.json":
            (runtime / "actual_forecast_producer_audit.json").read_bytes(),
        "source_snapshot_manifest.csv":
            (runtime / "source_snapshot_manifest.csv").read_bytes(),
        "forecast_rows.csv": (latest / "forecast_rows.csv").read_bytes(),
        "forecast_metadata.json":
            (latest / "forecast_metadata.json").read_bytes(),
    }
    for base in (latest, history):
        for name in ("forecast_rows.csv", "source_snapshot_manifest.csv",
                     "forecast_metadata.json"):
            _require((base / name).read_bytes() == evidence[name],
                     "producer_latest_history_mismatch")
    for base in (latest_mirror, history_mirror):
        for name in ("forecast_rows.csv", "forecast_metadata.json"):
            _require((base / name).read_bytes() == evidence[name],
                     "producer_compatibility_mirror_mismatch")
    return evidence


def _verify_sandbox_files(sandbox, producer_run_id, event_id):
    expected = {
        "inputs/drivers.csv",
        "inputs/starting_grid.csv",
        "inputs/weather.csv",
        "inputs/frozen_input_manifest.json",
        f"_runtime/actual_forecast_producer_v1/{producer_run_id}/actual_forecast_producer_audit.json",
        f"_runtime/actual_forecast_producer_v1/{producer_run_id}/source_snapshot_manifest.csv",
    }
    for prefix in (
        f"latest/forecasts/{event_id}/{GATE}/{LANE}",
        f"history/forecasts/{event_id}/{producer_run_id}/{GATE}/{LANE}",
    ):
        expected.update({f"{prefix}/forecast_rows.csv",
                         f"{prefix}/source_snapshot_manifest.csv",
                         f"{prefix}/forecast_metadata.json"})
    for prefix in (
        f"latest/forecast_outputs/{event_id}/{GATE}/{LANE}",
        f"history/forecast_outputs/{event_id}/{producer_run_id}/{GATE}/{LANE}",
    ):
        expected.update({f"{prefix}/forecast_rows.csv",
                         f"{prefix}/forecast_metadata.json"})
    actual = set()
    for path in sandbox.rglob("*"):
        _require(not path.is_symlink(), "unexpected_sandbox_symlink")
        if path.is_file():
            actual.add(path.relative_to(sandbox).as_posix())
    _require(actual == expected, "unexpected_sandbox_output_set")
    return sorted(actual)


def _hold(reason, *, producer_attempted=False):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HOLD,
        "reason_codes": [reason],
        "producer_execution_attempted": producer_attempted,
        "new_scientific_receipt_created": False,
        "verified_receipt_bindings_created": False,
        "stable_engine_executed": False,
        "production_forecast_generated": False,
        "blind_validation_eligible": False,
        "production_authenticated": False,
        "historical_availability_proven": False,
        "dr002_activated": False,
        "promotion_allowed": False,
    }


def compose_openf1_weather_into_frozen_producer(
    *,
    source_capture_receipt_bytes,
    raw_weather_response_bytes,
    event_id,
    meeting_id,
    session_id,
    implementation_git_sha,
):
    """Run one contained mixed-input producer composition and return evidence.

    No caller supplies forecast time.  The real producer emits its own runtime
    time.  Any failure returns HOLD and never retries the producer subprocess.
    """
    producer_attempted = False
    try:
        event_id = _scope_text(event_id)
        meeting_id = _scope_text(meeting_id)
        session_id = _scope_text(session_id)
        _require(type(implementation_git_sha) is str
                 and re.fullmatch(r"[0-9a-f]{40}", implementation_git_sha),
                 "invalid_implementation_git_sha")

        adapter_result = weather_adapter.adapt_openf1_weather_to_producer_input(
            source_capture_receipt_bytes=source_capture_receipt_bytes,
            raw_weather_response_bytes=raw_weather_response_bytes,
            event_id=event_id,
            meeting_id=meeting_id,
            session_id=session_id,
        )
        _require(adapter_result.get("status") == weather_adapter.VALIDATED,
                 "k4r4_adapter_hold")

        receipt = json.loads(source_capture_receipt_bytes)
        raw_source_id = receipt["payload"]["source_id"]
        weather_bytes = adapter_result["producer_input_csv_bytes"]
        inputs = _synthetic_inputs(event_id, meeting_id, session_id)
        inputs["weather"] = weather_bytes
        manifest = _build_manifest(event_id, meeting_id, session_id, inputs)
        manifest_bytes = _json_bytes(manifest)
        weather_entry = next(entry for entry in manifest["sources"]
                             if entry["source_name"] == "weather")
        _require(weather_entry["source_id"] != raw_source_id,
                 "raw_source_id_reused_for_derived_weather")
        _require(weather_entry["source_sha256"]
                 == adapter_result["producer_input_sha256"],
                 "derived_weather_hash_mismatch")

        producer_code = PRODUCER_PATH.read_bytes()
        _require(_git_blob_sha(producer_code) == PRODUCER_BLOB_SHA,
                 "producer_fingerprint_changed")
        checkout_before = _checked_out_output_fingerprint()

        with tempfile.TemporaryDirectory(
            prefix="dr002-openf1-weather-frozen-producer-composition-"
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
                    adapter_result=adapter_result,
                )
            )
            sandbox_files = _verify_sandbox_files(
                sandbox, producer_run_id, event_id
            )
            evidence_hashes = {name: _digest(data)
                               for name, data in sorted(evidence.items())}
        _require(not sandbox.exists(), "producer_sandbox_not_disposed")

        checkout_after = _checked_out_output_fingerprint()
        _require(checkout_after == checkout_before,
                 "checked_out_production_output_mutation")
        _require(_git_blob_sha(PRODUCER_PATH.read_bytes()) == PRODUCER_BLOB_SHA,
                 "producer_fingerprint_changed_after_execution")

        return {
            "schema_version": SCHEMA_VERSION,
            "status": VALIDATED,
            "reason_codes": [],
            "scope": {
                "event_id": event_id,
                "meeting_id": meeting_id,
                "session_id": session_id,
            },
            "implementation_git_sha": implementation_git_sha,
            "raw_weather_source_receipt_id": adapter_result["source_receipt_id"],
            "raw_weather_source_id": raw_source_id,
            "raw_weather_sha256": adapter_result["raw_source_sha256"],
            "k4r4_frozen_evidence_manifest_sha256":
                adapter_result["frozen_evidence_manifest_sha256"],
            "derived_weather_csv_sha256":
                adapter_result["producer_input_sha256"],
            "derived_weather_source_id": weather_entry["source_id"],
            "weather_row_count": adapter_result["row_count"],
            "weather_source_evidence_real": True,
            "drivers_synthetic": True,
            "starting_grid_synthetic": True,
            "mixed_input_mechanics_only": True,
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
            "new_scientific_receipt_created": False,
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
        reason = str(exc) or type(exc).__name__
        return _hold(reason, producer_attempted=producer_attempted)
