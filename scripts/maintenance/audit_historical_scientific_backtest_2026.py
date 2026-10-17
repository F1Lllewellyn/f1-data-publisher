#!/usr/bin/env python3
"""Audit the 2026 historical test environment and gate scientific backtesting.

This script is deliberately read-only outside its requested output directory. It
does not fetch providers, execute a forecast producer, or modify production data.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


ALLOWED_PREDICTION_GATES = {"pre_weekend", "post_fp3", "post_qualifying"}
TEAM_PRIOR = {
    "McLaren": 0.10,
    "Ferrari": 0.12,
    "Red Bull Racing": 0.13,
    "Mercedes": 0.14,
    "Aston Martin": 0.30,
    "Williams": 0.34,
    "Haas F1 Team": 0.38,
    "Racing Bulls": 0.40,
    "Alpine": 0.44,
    "Kick Sauber": 0.46,
    "Sauber": 0.46,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def git_text(repo: Path, commit: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{commit}:{path}"], cwd=repo, stderr=subprocess.DEVNULL
    ).decode("utf-8-sig")


def build_origin_index(repo: Path) -> dict[str, tuple[str, datetime]]:
    raw = subprocess.check_output(
        [
            "git", "log", "--diff-filter=A", "--format=@@%H%x09%cI", "--name-only", "--",
            "history/forecast_bundles",
        ],
        cwd=repo,
        text=True,
    )
    current: tuple[str, datetime] | None = None
    origins: dict[str, tuple[str, datetime]] = {}
    for line in raw.splitlines():
        if line.startswith("@@"):
            commit, committed = line[2:].split("\t", 1)
            current = (commit, datetime.fromisoformat(committed))
        elif line and current is not None:
            origins[line] = current
    return origins


def manifest_and_root(repo: Path, recovery_root: Path, evidence_path: str) -> tuple[Path, Path]:
    if evidence_path.startswith("audit/2026-10-17/recovery/processor_outputs/"):
        return (
            recovery_root / evidence_path,
            recovery_root / "audit/2026-10-17/recovery/processor_outputs",
        )
    return repo / evidence_path, repo


def rank_metrics(predicted: dict[int, int], actual: dict[int, int]) -> dict[str, float | bool]:
    drivers = sorted(actual)
    differences = [predicted[driver] - actual[driver] for driver in drivers]
    count = len(drivers)
    predicted_podium = {driver for driver in drivers if predicted[driver] <= 3}
    actual_podium = {driver for driver in drivers if actual[driver] <= 3}
    predicted_top10 = {driver for driver in drivers if predicted[driver] <= 10}
    actual_top10 = {driver for driver in drivers if actual[driver] <= 10}
    predicted_winner = next(driver for driver in drivers if predicted[driver] == 1)
    actual_winner = next(driver for driver in drivers if actual[driver] == 1)
    return {
        "mae": sum(abs(value) for value in differences) / count,
        "rmse": math.sqrt(sum(value * value for value in differences) / count),
        "spearman_rho": 1 - 6 * sum(value * value for value in differences) / (count * (count * count - 1)),
        "podium_overlap": len(predicted_podium & actual_podium) / 3,
        "top10_overlap": len(predicted_top10 & actual_top10) / 10,
        "winner_hit": predicted_winner == actual_winner,
    }


def event_scoped_input_manifest(rows: list[dict[str, str]], event_id: str) -> tuple[bool, str]:
    if not rows:
        return False, "missing_producer_source_manifest"
    required = {"source_id", "source_sha256", "relative_path"}
    if not required.issubset(rows[0]):
        return False, "producer_inputs_not_hash_bound"
    if any(not row.get("source_sha256") or not row.get("source_id") for row in rows):
        return False, "producer_inputs_not_hash_bound"
    if any(event_id not in (row.get("relative_path") or row.get("path") or "") for row in rows):
        return False, "producer_inputs_not_event_scoped"
    return True, "event_scoped_hash_bound_inputs"


def normalized_source_path(source_path: str) -> str:
    marker = "/latest/"
    if marker not in source_path:
        raise RuntimeError(f"FORECAST_SOURCE_PATH_HOLD:{source_path}")
    return "latest/" + source_path.split(marker, 1)[1]


def audit_bundle(
    repo: Path,
    forecast_path: Path,
    event: dict,
    origins: dict[str, tuple[str, datetime]],
) -> dict:
    rows = read_csv(forecast_path)
    if not rows:
        raise RuntimeError(f"EMPTY_FORECAST_BUNDLE_HOLD:{forecast_path}")
    lock_time = datetime.fromisoformat(rows[0]["forecast_lock_utc"].replace("Z", "+00:00"))
    relative_forecast = forecast_path.relative_to(repo).as_posix()
    if relative_forecast not in origins:
        raise RuntimeError(f"FORECAST_GIT_ORIGIN_HOLD:{relative_forecast}")
    commit, commit_time = origins[relative_forecast]
    bundle_root = forecast_path.parent
    lock = json.loads((bundle_root / "bundle_lock_manifest.json").read_text(encoding="utf-8"))
    driver_numbers = [int(row["driver_number"]) for row in rows]
    exact_participants = (
        len(driver_numbers) == len(set(driver_numbers)) == 22
        and set(driver_numbers) == set(event["actual_rank"])
    )
    timing_valid = lock_time < event["race_start"] and commit_time < event["race_start"]
    gate_valid = rows[0]["gate"] in ALLOWED_PREDICTION_GATES
    lock_valid = lock.get("bundle_status") == "locked" and lock.get("blind_validation_eligible") is True
    snapshot = read_csv(bundle_root / "source_snapshot_manifest.csv")
    if len(snapshot) != 1:
        raise RuntimeError(f"FORECAST_SNAPSHOT_CARDINALITY_HOLD:{forecast_path}")
    source_hash_bound = False
    producer_manifest_path = ""
    input_scoped = False
    input_reason = "not_evaluated_before_basic_cutoff_gates"
    if timing_valid and gate_valid and lock_valid and exact_participants:
        source_path = normalized_source_path(snapshot[0]["source_path_or_uri"])
        source_bytes = subprocess.check_output(
            ["git", "show", f"{commit}:{source_path}"], cwd=repo, stderr=subprocess.DEVNULL
        )
        source_hash_bound = hashlib.sha256(source_bytes).hexdigest() == snapshot[0]["source_sha256"]
        producer_manifest_path = str(Path(source_path).with_name("source_snapshot_manifest.csv"))
        try:
            producer_manifest = list(csv.DictReader(git_text(repo, commit, producer_manifest_path).splitlines()))
        except subprocess.CalledProcessError:
            producer_manifest = []
        input_scoped, input_reason = event_scoped_input_manifest(producer_manifest, event["event_id"])
    scientifically_eligible = all(
        (timing_valid, gate_valid, lock_valid, source_hash_bound, exact_participants, input_scoped)
    )
    return {
        "event_id": event["event_id"],
        "grand_prix": event["name"],
        "meeting_key": event["meeting_key"],
        "race_session_key": event["session_key"],
        "bundle_path": forecast_path.relative_to(repo).as_posix(),
        "bundle_git_blob": git_blob(forecast_path),
        "origin_commit": commit,
        "origin_commit_utc": commit_time.isoformat(),
        "gate": rows[0]["gate"],
        "forecast_lock_utc": lock_time.isoformat(),
        "race_start_utc": event["race_start"].isoformat(),
        "forecast_rows": len(rows),
        "actual_participants": len(event["actual_rank"]),
        "participant_overlap": len(set(driver_numbers) & set(event["actual_rank"])),
        "exact_participant_universe": exact_participants,
        "pre_race_git_and_lock": timing_valid,
        "allowed_prediction_gate": gate_valid,
        "lock_contract_valid": lock_valid,
        "forecast_source_sha256": snapshot[0]["source_sha256"],
        "forecast_source_hash_bound_at_origin_commit": source_hash_bound,
        "producer_input_manifest_path": producer_manifest_path,
        "producer_inputs_event_scoped_and_hash_bound": input_scoped,
        "input_scope_reason": input_reason,
        "scientifically_eligible": scientifically_eligible,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--recovery-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    recovery_root = args.recovery_root.resolve()
    out = (repo / args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    audit = repo / "audit/2026-10-17"

    coverage = read_csv(audit / "F1_2026_SESSION_COVERAGE.csv")
    if len(coverage) != 935 or len({row["session_key"] for row in coverage}) != 85:
        raise RuntimeError("HISTORICAL_COVERAGE_CARDINALITY_HOLD")
    optional_partial = [row for row in coverage if row["coverage_status"] == "PARTIAL"]
    if len(optional_partial) != 159 or any(row["required_by_processor"] != "no" for row in optional_partial):
        raise RuntimeError("OPTIONAL_PARTIAL_ACCOUNTING_HOLD")
    if any(row["coverage_status"] in {"HOLD", "MISSING"} for row in coverage):
        raise RuntimeError("REQUIRED_SOURCE_HOLD")

    terminal = json.loads((audit / "F1_2026_HISTORICAL_SCIENTIFIC_VALIDATION.json").read_text())
    overlays = json.loads((audit / "F1_2026_OFFICIAL_FINAL_GRID_OVERLAYS.json").read_text())
    miami = json.loads((audit / "F1_2026_MIAMI_FP1_DUPLICATE_RESOLUTION.json").read_text())
    if terminal["coverage"]["clean_sessions"] != 85 or overlays["document_count"] != 23:
        raise RuntimeError("ACCEPTED_CLOSURE_BINDING_HOLD")

    reader = load_module(
        "historical_reader", repo / "scripts/session_data_processor/f1_1b_output_contract_v16.py"
    )
    producer = load_module(
        "historical_producer_consumer", repo / "scripts/forecasts/produce_actual_forecast_rows_v1.py"
    )
    manifests: dict[int, tuple[Path, Path, dict]] = {}
    fixture_sessions: list[dict] = []
    source_files = 0
    source_rows = 0
    for row in coverage:
        if row["source"] != "sessions":
            continue
        manifest_path, root = manifest_and_root(repo, recovery_root, row["source_evidence_path"])
        manifest = reader.load_json(manifest_path) or {}
        key = int(row["session_key"])
        if int(manifest.get("session", {}).get("session_key") or -1) != key:
            raise RuntimeError(f"SESSION_IDENTITY_HOLD:{key}")
        manifests[key] = (manifest_path, root, manifest)
        session_coverage = [item for item in coverage if int(item["session_key"]) == key]
        source_fixture: dict[str, dict] = {}
        for source, report in manifest.get("sources", {}).items():
            raw = root / report["json_path"]
            value = reader.load_json(raw)
            value = value.get("value") if isinstance(value, dict) and "value" in value else value
            if not isinstance(value, list) or len(value) != int(report.get("rows") or 0):
                raise RuntimeError(f"READER_ROW_COUNT_HOLD:{key}:{source}")
            if report.get("json_sha256") and sha256(raw) != report["json_sha256"]:
                raise RuntimeError(f"READER_SOURCE_HASH_HOLD:{key}:{source}")
            source_files += 1
            source_rows += len(value)
            coverage_row = next(item for item in session_coverage if item["source"] == source.removeprefix("openf1_"))
            source_fixture[source] = {
                "json_path": report["json_path"],
                "json_sha256": report.get("json_sha256"),
                "rows": len(value),
                "coverage_status": coverage_row["coverage_status"],
                "required_by_processor": coverage_row["required_by_processor"] == "yes",
            }
        fixture_sessions.append({
            "meeting_key": int(row["meeting_key"]),
            "session_key": key,
            "session_name": row["session_name"],
            "session_type": row["session_type"],
            "scheduled_start_utc": row["scheduled_start_utc"],
            "manifest_evidence_path": row["source_evidence_path"],
            "manifest_sha256": sha256(manifest_path),
            "manifest_git_blob": git_blob(manifest_path),
            "storage_class": "ISOLATED_RECOVERY_ARCHIVE" if root != repo else "REPOSITORY_RETAINED_HISTORY",
            "sources": source_fixture,
        })
    if len(manifests) != 85 or source_files != 935 or source_rows != 538111:
        raise RuntimeError("OFFLINE_READER_TOTAL_HOLD")

    # Prove the unchanged producer-side readers can consume the corrected views.
    with tempfile.TemporaryDirectory(prefix="f1-historical-test-consumer-") as temp:
        temp_root = Path(temp)
        for document in overlays["documents"]:
            path = temp_root / f"grid_{document['target_session_key']}.csv"
            rows = [
                {
                    "driver_number": item["driver_number"],
                    "position": item["official_position"] if item["official_position"] is not None else "",
                    "start_status": item["start_status"],
                }
                for item in document["participants"]
            ]
            write_csv(path, rows, ["driver_number", "position", "start_status"])
            parsed = producer.read_csv(path)
            universe = producer.build_driver_universe({"starting_grid": path})
            grid = producer.starting_grid_map({"starting_grid": path})
            pit_count = sum(item["start_status"] == "PIT_LANE" for item in document["participants"])
            if len(parsed) != 22 or len(universe) != 22 or len(grid) != 22 - pit_count:
                raise RuntimeError(f"GRID_CONSUMER_HOLD:{document['target_session_key']}")
        for lane, expected in (("position", 621), ("weather", 100)):
            source = repo / miami["sources"][lane]["derived_relative_path"]
            rows = json.loads(source.read_text(encoding="utf-8"))
            path = temp_root / f"miami_{lane}.csv"
            write_csv(path, rows, list(rows[0]))
            if len(producer.read_csv(path)) != expected:
                raise RuntimeError(f"MIAMI_CONSUMER_HOLD:{lane}")

    events: dict[int, dict] = {}
    for row in coverage:
        if row["session_name"] == "Race" and row["source"] == "sessions":
            meeting = int(row["meeting_key"])
            event_id = Path(row["source_evidence_path"]).parts[-3]
            events[meeting] = {
                "meeting_key": meeting,
                "event_id": event_id,
                "name": row["grand_prix"],
                "session_key": int(row["session_key"]),
                "race_start": datetime.fromisoformat(row["scheduled_start_utc"]),
            }
    if len(events) != 17:
        raise RuntimeError("RACE_EVENT_CARDINALITY_HOLD")

    for event in events.values():
        _, root, manifest = manifests[event["session_key"]]
        result_report = manifest["sources"]["openf1_session_result"]
        result_path = root / result_report["json_path"]
        result_rows = json.loads(result_path.read_text(encoding="utf-8"))
        if len(result_rows) != 22:
            raise RuntimeError(f"RACE_RESULT_PARTICIPANT_HOLD:{event['session_key']}")
        event["actual_rows"] = result_rows
        event["actual_rank"] = {int(row["driver_number"]): index for index, row in enumerate(result_rows, 1)}
        event["result_sha256"] = result_report["json_sha256"]

    bundle_audits: list[dict] = []
    origins = build_origin_index(repo)
    for forecast_path in sorted(
        (repo / "history/forecast_bundles").glob("*/*/*/experimental_challenger/forecast_rows.csv")
    ):
        event_id = forecast_path.parts[-5]
        try:
            meeting = int(event_id.split("_")[1])
        except (IndexError, ValueError):
            continue
        if meeting in events:
            bundle_audits.append(audit_bundle(repo, forecast_path, events[meeting], origins))

    diagnostic_candidates = [
        row for row in bundle_audits
        if row["pre_race_git_and_lock"]
        and row["allowed_prediction_gate"]
        and row["lock_contract_valid"]
        and row["forecast_source_hash_bound_at_origin_commit"]
        and row["exact_participant_universe"]
    ]
    scientifically_eligible = [row for row in diagnostic_candidates if row["scientifically_eligible"]]

    race_rows: list[dict] = []
    for event in sorted(events.values(), key=lambda item: item["meeting_key"]):
        audited = [row for row in bundle_audits if row["meeting_key"] == event["meeting_key"]]
        pre_race = [row for row in audited if row["pre_race_git_and_lock"] and row["allowed_prediction_gate"]]
        exact = [row for row in pre_race if row["exact_participant_universe"]]
        scoped = [row for row in exact if row["producer_inputs_event_scoped_and_hash_bound"]]
        if scoped:
            classification, reason = "ELIGIBLE", "event_scoped_hash_bound_pre_race_inputs"
        elif exact:
            classification, reason = "HOLD", "producer_inputs_are_season_wide_and_not_hash_bound"
        elif pre_race:
            classification, reason = "HOLD", "forecast_participant_universe_not_exactly_the_event_entry"
        else:
            classification, reason = "HOLD", "no_saved_pre_race_experimental_bundle"
        race_rows.append({
            "meeting_key": event["meeting_key"],
            "event_id": event["event_id"],
            "grand_prix": event["name"],
            "race_session_key": event["session_key"],
            "race_start_utc": event["race_start"].isoformat(),
            "race_result_sha256": event["result_sha256"],
            "saved_experimental_bundles": len(audited),
            "saved_pre_race_prediction_cutoffs": len(pre_race),
            "exact_participant_cutoffs": len(exact),
            "event_scoped_hash_bound_cutoffs": len(scoped),
            "scientifically_eligible_cutoffs": sum(row["scientifically_eligible"] for row in scoped),
            "classification": classification,
            "reason": reason,
        })

    grid_by_meeting = {
        int(document["meeting_key"]): document
        for document in overlays["documents"]
        if document["target_session_type"] == "Race"
    }
    diagnostic_rows: list[dict] = []
    for candidate in diagnostic_candidates:
        event = events[candidate["meeting_key"]]
        forecast_rows = candidate.pop("rows")
        predicted = {
            int(row["driver_number"]): int(row["predicted_race_finish_position"])
            for row in forecast_rows
        }
        team = {int(row["driver_number"]): row["team_name"] for row in forecast_rows}
        team_order = sorted(predicted, key=lambda driver: (TEAM_PRIOR.get(team[driver], 0.50), driver))
        team_rank = {driver: index for index, driver in enumerate(team_order, 1)}
        grid_document = grid_by_meeting[event["meeting_key"]]
        grid_order = [int(row["driver_number"]) for row in grid_document["participants"]]
        grid_rank = {driver: index for index, driver in enumerate(grid_order, 1)}
        model_metrics = rank_metrics(predicted, event["actual_rank"])
        team_metrics = rank_metrics(team_rank, event["actual_rank"])
        grid_metrics = rank_metrics(grid_rank, event["actual_rank"])
        actual_by_driver = {int(row["driver_number"]): row for row in event["actual_rows"]}
        dnf_brier = sum(
            (
                float(row["predicted_dnf_probability"])
                - float(any(actual_by_driver[int(row["driver_number"])].get(flag) for flag in ("dnf", "dns", "dsq")))
            ) ** 2
            for row in forecast_rows
        ) / len(forecast_rows)
        diagnostic_rows.append({
            "event_id": candidate["event_id"],
            "grand_prix": candidate["grand_prix"],
            "gate": candidate["gate"],
            "forecast_lock_utc": candidate["forecast_lock_utc"],
            "origin_commit": candidate["origin_commit"],
            "forecast_source_sha256": candidate["forecast_source_sha256"],
            "classification": "DIAGNOSTIC_ONLY_NOT_SCIENTIFICALLY_ELIGIBLE",
            "hold_reason": candidate["input_scope_reason"],
            "model_mae": round(model_metrics["mae"], 6),
            "model_rmse": round(model_metrics["rmse"], 6),
            "model_spearman_rho": round(model_metrics["spearman_rho"], 6),
            "model_podium_overlap": round(model_metrics["podium_overlap"], 6),
            "model_top10_overlap": round(model_metrics["top10_overlap"], 6),
            "model_winner_hit": model_metrics["winner_hit"],
            "model_nonfinish_brier": round(dnf_brier, 6),
            "team_prior_mae": round(team_metrics["mae"], 6),
            "team_prior_spearman_rho": round(team_metrics["spearman_rho"], 6),
            "retrospective_final_grid_mae": round(grid_metrics["mae"], 6),
            "retrospective_final_grid_spearman_rho": round(grid_metrics["spearman_rho"], 6),
            "final_grid_cutoff_eligible": False,
            "final_grid_limitation": "FIA final grid first observed post-event and official document time is after saved cutoff",
            "podium_top10_probability_calibration_supported": False,
            "energy_traffic_feature_attribution_supported": False,
        })

    optional_by_source = collections.Counter(row["source"] for row in optional_partial)
    environment = {
        "schema": "f1_2026_historical_test_environment_v1",
        "status": "PHASE_1_PASS",
        "base_pr": 310,
        "base_head": "61a865a9440720902c739c371da0a8c8b88979b8",
        "sessions": 85,
        "events": 17,
        "source_files": source_files,
        "source_rows": source_rows,
        "required_source_holds": 0,
        "optional_partial_records": len(optional_partial),
        "optional_partial_by_source": dict(sorted(optional_by_source.items())),
        "fia_grid_documents": overlays["document_count"],
        "fia_grid_participants": overlays["participant_records"],
        "miami_position_rows": miami["sources"]["position"]["derived_rows"],
        "miami_weather_rows": miami["sources"]["weather"]["derived_rows"],
        "reader_contract": "scripts/session_data_processor/f1_1b_output_contract_v16.py",
        "analytical_consumer": "scripts/forecasts/produce_actual_forecast_rows_v1.py",
        "grid_overlay_consumer_checks": 23,
        "miami_overlay_consumer_checks": 2,
        "original_archive_sha256": sha256(
            audit / "recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz"
        ),
        "protected_systems_modified": False,
    }
    if environment["original_archive_sha256"] != "ed72021596ed3968c78dfd6690580af3a8c9a292a74df6eadd6ca24f6afec303":
        raise RuntimeError("RECOVERY_ARCHIVE_HASH_HOLD")

    aggregate_diagnostic = {}
    if diagnostic_rows:
        numeric = [
            "model_mae", "model_rmse", "model_spearman_rho", "model_podium_overlap",
            "model_top10_overlap", "model_nonfinish_brier", "team_prior_mae",
            "team_prior_spearman_rho", "retrospective_final_grid_mae",
            "retrospective_final_grid_spearman_rho",
        ]
        aggregate_diagnostic = {
            key: round(sum(float(row[key]) for row in diagnostic_rows) / len(diagnostic_rows), 6)
            for key in numeric
        }
        aggregate_diagnostic["model_winner_hit_rate"] = round(
            sum(row["model_winner_hit"] is True for row in diagnostic_rows) / len(diagnostic_rows), 6
        )

    summary = {
        "schema": "f1_2026_scientific_backtest_gate_v1",
        "terminal_status": "PHASE_1_PASS_PHASE_2_HOLD_EVENT_SCOPE",
        "phase_1": environment,
        "phase_2": {
            "completed_events_considered": 17,
            "archived_experimental_bundles_audited": len(bundle_audits),
            "pre_race_gate_bundles": sum(
                row["pre_race_git_and_lock"] and row["allowed_prediction_gate"] for row in bundle_audits
            ),
            "exact_participant_pre_race_bundles": len(diagnostic_candidates),
            "diagnostic_events": len({row["event_id"] for row in diagnostic_rows}),
            "diagnostic_cutoffs": len(diagnostic_rows),
            "scientifically_eligible_events": len({row["event_id"] for row in scientifically_eligible}),
            "scientifically_eligible_cutoffs": len(scientifically_eligible),
            "full_walk_forward_executed": False,
            "primary_hold": "Existing producer input manifests are season-wide, not event-scoped, and do not hash-bind underlying input bytes.",
            "diagnostic_metrics_not_accuracy_claim": aggregate_diagnostic,
        },
        "ranked_corrective_priorities": [
            "Persist immutable event-scoped input bytes and hashes at every future forecast cutoff.",
            "Restrict the producer driver universe and every feature row to the target event/session relationship.",
            "Persist nonblank win, podium and top-10 probabilities through the bundle-lock schema.",
            "Numerically integrate energy, harvesting, battery and traffic features only when cutoff-safe observations exist.",
            "Accumulate independently locked prospective events before model selection or calibration claims.",
        ],
        "scientific_limitations": [
            "The four exact-participant saved outputs cover only Belgium and Hungary and are correlated repeated cutoffs.",
            "Underlying producer inputs are broad season snapshots with row counts but no immutable source hashes.",
            "Final FIA grids were first observed post-event and their official document times follow all four saved cutoffs.",
            "Only non-finish probability is populated; podium/top-10 calibration is unsupported.",
            "Energy, harvesting, battery and traffic sources influence readiness counts only, not numeric predictions.",
            "No DRS assumption was introduced.",
        ],
        "negative_claims": {
            "scientifically_valid_full_backtest_completed": False,
            "retrospective_accuracy_claimed": False,
            "provider_requested": False,
            "workflow_dispatched": False,
            "stable_engine_modified_or_executed": False,
            "canonical_workbook_modified": False,
            "production_latest_or_history_modified": False,
            "issue_309_modified": False,
            "dr002_activated": False,
            "predictions_published": False,
            "merged_or_promoted": False,
        },
    }

    overlay_targets = {int(document["target_session_key"]): document for document in overlays["documents"]}
    for session in fixture_sessions:
        effective_overlays = []
        if session["session_key"] in overlay_targets:
            document = overlay_targets[session["session_key"]]
            effective_overlays.append({
                "type": "FIA_FINAL_GRID",
                "source_url": document["official_source_url"],
                "source_sha256": document["fia_pdf_sha256"],
                "source_first_observed_utc": document["first_local_observation_utc"],
                "facts_path": "audit/2026-10-17/F1_2026_OFFICIAL_FINAL_GRID_OVERLAYS.json",
            })
        if session["session_key"] == 11270:
            for lane in ("position", "weather"):
                effective_overlays.append({
                    "type": "SOURCE_PRESERVING_EXACT_DEDUPLICATION",
                    "source": lane,
                    "raw_sha256": miami["sources"][lane]["raw_sha256"],
                    "derived_sha256": miami["sources"][lane]["derived_sha256"],
                    "derived_path": miami["sources"][lane]["derived_relative_path"],
                })
        session["effective_overlays"] = effective_overlays
    fixture = {
        "schema": "f1_2026_historical_test_fixture_manifest_v1",
        "base_pr": 310,
        "base_head": "61a865a9440720902c739c371da0a8c8b88979b8",
        "session_count": len(fixture_sessions),
        "source_count": source_files,
        "source_rows": source_rows,
        "coverage_manifest": "audit/2026-10-17/F1_2026_SESSION_COVERAGE.csv",
        "recovery_archive": "audit/2026-10-17/recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz",
        "recovery_archive_sha256": environment["original_archive_sha256"],
        "sessions": sorted(fixture_sessions, key=lambda item: (item["meeting_key"], item["scheduled_start_utc"])),
    }

    environment_path = out / "F1_2026_HISTORICAL_TEST_ENVIRONMENT.json"
    fixture_path = out / "F1_2026_HISTORICAL_TEST_FIXTURE_MANIFEST.json"
    eligibility_path = out / "F1_2026_RACE_BACKTEST_ELIGIBILITY.csv"
    diagnostics_path = out / "F1_2026_SAVED_FORECAST_DIAGNOSTICS.csv"
    summary_path = out / "F1_2026_SCIENTIFIC_BACKTEST_RESULT.json"
    environment_path.write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fixture_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(eligibility_path, race_rows, list(race_rows[0]))
    write_csv(diagnostics_path, diagnostic_rows, list(diagnostic_rows[0]))
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = f"""# F1 2026 historical testing and scientific backtest — 17 October 2026

**Terminal result: PHASE 1 PASS / PHASE 2 HOLD.** The isolated historical environment is complete and readable, but the saved experimental producer inputs do not satisfy event-isolated, immutable source binding. A comprehensive scientific walk-forward was therefore not executed and no retrospective accuracy claim is made.

## Historical environment

| Check | Result |
|---|---:|
| Completed events | 17 |
| Expected sessions | 85 |
| Required-source clean sessions | 85 |
| Original source files parsed | {source_files} |
| Original source rows parsed | {source_rows:,} |
| Optional partial source records | {len(optional_partial)} |
| FIA final-grid overlays consumed | 23 |
| Miami corrected analytical views consumed | 2 |
| Reader or consumer failures | 0 |

All 159 partial records are optional and remain explicitly partial: {dict(sorted(optional_by_source.items()))}. They are not silently promoted to observed data.

## Scientific backtest gate

| Measure | Result |
|---|---:|
| Archived experimental bundles audited | {len(bundle_audits)} |
| Saved pre-race prediction-gate bundles | {sum(row['pre_race_git_and_lock'] and row['allowed_prediction_gate'] for row in bundle_audits)} |
| Exact 22-driver pre-race bundles | {len(diagnostic_candidates)} |
| Events represented by those exact bundles | {len({row['event_id'] for row in diagnostic_rows})} |
| Event-scoped, hash-bound eligible cutoffs | {len(scientifically_eligible)} |
| Scientifically eligible events | {len({row['event_id'] for row in scientifically_eligible})} |

The four exact saved outputs are from Belgium and Hungary at pre-weekend and post-qualifying gates. Their output bytes are Git-timestamped before each race and bind exactly to the locker source hash, but their producer manifests point to season-wide source tables and record only mutable paths and row counts. This violates the required event-isolation and immutable-input gates.

## Diagnostic-only results

The four saved outputs were scored only to preserve all usable evidence. These figures are **not** a valid model-accuracy or calibration claim:

- Mean model finishing-order MAE: {aggregate_diagnostic.get('model_mae', 'n/a')}; simple team-prior MAE: {aggregate_diagnostic.get('team_prior_mae', 'n/a')}.
- Mean model Spearman rho: {aggregate_diagnostic.get('model_spearman_rho', 'n/a')}; team-prior rho: {aggregate_diagnostic.get('team_prior_spearman_rho', 'n/a')}.
- Mean podium overlap: {aggregate_diagnostic.get('model_podium_overlap', 'n/a')}; top-10 overlap: {aggregate_diagnostic.get('model_top10_overlap', 'n/a')}.
- Mean non-finish Brier score: {aggregate_diagnostic.get('model_nonfinish_brier', 'n/a')}.
- Retrospective final-grid MAE: {aggregate_diagnostic.get('retrospective_final_grid_mae', 'n/a')}; it is not cutoff-eligible because the official grids postdate the saved cutoffs and were first observed post-event.

## Weaknesses and smallest safe remedies

1. **Event scope and immutable provenance:** freeze every actual producer input by event/session/cutoff and hash it into the bundle.
2. **Participant contamination:** enforce the exact target-event entry before producing rows; 126 of 130 saved pre-race bundles fail this today.
3. **Probability persistence:** carry win, podium and top-10 probabilities through locking before calibration analysis.
4. **Feature attribution:** energy deployment, harvesting, battery and traffic currently affect readiness only; add numeric features only after prospective cutoff-safe evidence exists.
5. **Sample size:** accumulate independently locked prospective races before tuning or promotion.

No DRS assumption was introduced. No provider request, workflow dispatch, producer/model execution, stable-engine or workbook change, production archive mutation, prediction publication, DR-002 activation, merge or promotion occurred. Issue #309 remains unchanged.
"""
    (out / "F1_2026_HISTORICAL_TESTING_REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
