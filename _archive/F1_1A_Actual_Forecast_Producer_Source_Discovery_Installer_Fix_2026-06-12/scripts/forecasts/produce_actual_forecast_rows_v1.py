#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

GATES = ["pre_weekend", "post_fp3", "post_qualifying", "race_result", "post_event"]
LANES = ["stable_baseline", "control_room_overlay", "experimental_challenger"]

SOURCE_DIR_CANDIDATES = [
    # Current OpenF1 Lightweight Source Closure publisher writes lane CSVs under /data.
    "latest/openf1_lightweight_source_closure/data",
    "latest/openf1_lightweight_source_closure",
    "latest/source_closure/data",
    "latest/source_closure",
    "latest/openf1/data",
    "latest/openf1",
    "data/latest/openf1_lightweight_source_closure/data",
    "data/latest/openf1_lightweight_source_closure",
    "data/latest/source_closure/data",
    "data/latest/source_closure",
]

SOURCE_RECURSIVE_ROOTS = [
    "latest/openf1_lightweight_source_closure",
    "latest/source_closure",
    "latest/openf1",
    "history/openf1_lightweight_source_closure",
    "history/source_closure",
    "data/latest/openf1_lightweight_source_closure",
]

SOURCE_FILES = {
    "drivers": ["openf1_drivers.csv", "drivers.csv"],
    "starting_grid": ["openf1_starting_grid.csv", "starting_grid.csv"],
    "intervals": ["openf1_intervals.csv", "intervals.csv"],
    "stints": ["openf1_stints.csv", "stints.csv"],
    "weather": ["openf1_weather.csv", "weather.csv"],
    "race_control": ["openf1_race_control.csv", "race_control.csv"],
    "pit": ["openf1_pit.csv", "pit.csv"],
    "position": ["openf1_position.csv", "position.csv"],
    "source_readiness": ["source_readiness_summary.csv"],
}

# Conservative fallback priors used only for tie-breaking once real driver/source rows exist.
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except UnicodeDecodeError:
        with path.open("r", encoding="latin-1", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _candidate_priority(path: Path, repo: Path) -> Tuple[int, int, int, str]:
    try:
        rel = path.relative_to(repo).as_posix()
    except Exception:
        rel = path.as_posix()
    latest_bonus = 0 if rel.startswith("latest/") else 1
    source_closure_bonus = 0 if "openf1_lightweight_source_closure" in rel else 1
    data_bonus = 0 if "/data/" in rel else 1
    return (latest_bonus, source_closure_bonus, data_bonus, rel)


def find_sources(repo: Path) -> Tuple[Dict[str, Path], Dict[str, int]]:
    found: Dict[str, Path] = {}
    counts: Dict[str, int] = {}
    for source_name, filenames in SOURCE_FILES.items():
        candidates: List[Path] = []

        # 1) Fast exact paths, including the /data subfolder used by the current publisher.
        for base_rel in SOURCE_DIR_CANDIDATES:
            base = repo / base_rel
            for filename in filenames:
                candidates.append(base / filename)

        # 2) Recursive fallback. This catches minor publisher path changes without creating rows from unrelated files.
        for root_rel in SOURCE_RECURSIVE_ROOTS:
            root = repo / root_rel
            if root.exists():
                for filename in filenames:
                    candidates.extend(root.rglob(filename))

        # 3) De-duplicate and choose the best non-empty candidate.
        usable: List[Tuple[Tuple[int, int, int, str], Path, int]] = []
        seen = set()
        for candidate in candidates:
            try:
                key = candidate.resolve()
            except Exception:
                key = candidate
            if key in seen:
                continue
            seen.add(key)
            if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
                rows = read_csv(candidate)
                if rows:
                    usable.append((_candidate_priority(candidate, repo), candidate, len(rows)))
        if usable:
            usable.sort(key=lambda x: x[0])
            _, best_path, row_count = usable[0]
            found[source_name] = best_path
            counts[source_name] = row_count
        else:
            counts[source_name] = 0
    return found, counts


def clean_str(x) -> str:
    if x is None:
        return ""
    return str(x).strip()


def find_key(row: Dict[str, str], keys: Iterable[str]) -> str:
    lowered = {k.lower(): k for k in row.keys()}
    for key in keys:
        if key.lower() in lowered:
            val = clean_str(row.get(lowered[key.lower()], ""))
            if val:
                return val
    return ""


def to_int(x, default=None):
    try:
        if x is None or str(x).strip() == "":
            return default
        return int(float(str(x).strip()))
    except Exception:
        return default


def to_float(x, default=0.0):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(str(x).strip())
    except Exception:
        return default


def build_driver_universe(sources: Dict[str, Path]) -> List[Dict[str, object]]:
    drivers: Dict[int, Dict[str, object]] = {}
    if "drivers" in sources:
        for row in read_csv(sources["drivers"]):
            dn = to_int(find_key(row, ["driver_number", "number", "driverNumber"]))
            if dn is None:
                continue
            drivers[dn] = {
                "driver_number": dn,
                "driver_name": find_key(row, ["broadcast_name", "full_name", "name", "driver_name"]) or f"Driver {dn}",
                "team_name": find_key(row, ["team_name", "team", "constructor", "constructor_name"]) or "Unknown",
            }
    if "starting_grid" in sources:
        for row in read_csv(sources["starting_grid"]):
            dn = to_int(find_key(row, ["driver_number", "number", "driverNumber"]))
            if dn is None:
                continue
            if dn not in drivers:
                drivers[dn] = {"driver_number": dn, "driver_name": f"Driver {dn}", "team_name": "Unknown"}
    return [drivers[k] for k in sorted(drivers.keys())]


def starting_grid_map(sources: Dict[str, Path]) -> Dict[int, int]:
    grid: Dict[int, int] = {}
    if "starting_grid" not in sources:
        return grid
    for row in read_csv(sources["starting_grid"]):
        dn = to_int(find_key(row, ["driver_number", "number", "driverNumber"]))
        pos = to_int(find_key(row, ["position", "grid_position", "starting_grid_position", "grid"]), None)
        if dn is not None and pos is not None and pos > 0:
            grid[dn] = pos
    return grid


def source_readiness_score(counts: Dict[str, int], gate: str) -> float:
    weights = {
        "drivers": 0.18,
        "starting_grid": 0.20 if gate in ["post_qualifying", "race_result", "post_event"] else 0.10,
        "intervals": 0.12,
        "stints": 0.10,
        "weather": 0.10,
        "race_control": 0.10,
        "pit": 0.08,
        "position": 0.08,
        "source_readiness": 0.04,
    }
    total = sum(weights.values())
    earned = sum(w for k, w in weights.items() if counts.get(k, 0) > 0)
    return round(max(0.0, min(1.0, earned / total)), 4)


def probability_from_rank(rank: int, n: int, target: str) -> float:
    if n <= 0:
        return 0.0
    x = (rank - 1) / max(1, n - 1)
    if target == "win":
        return max(0.002, min(0.55, 0.42 * math.exp(-5.4 * x)))
    if target == "podium":
        return max(0.01, min(0.82, 0.72 * math.exp(-3.2 * x)))
    if target == "top10":
        return max(0.03, min(0.98, 1.0 / (1.0 + math.exp((rank - 10.5) / 1.8))))
    return 0.0


def reliability_risk(driver: Dict[str, object], counts: Dict[str, int], gate: str, lane: str) -> float:
    team = str(driver.get("team_name", "Unknown"))
    base = 0.055 + TEAM_PRIOR.get(team, 0.30) * 0.08
    missing_penalty = max(0.0, 1.0 - source_readiness_score(counts, gate)) * 0.035
    if lane == "stable_baseline":
        risk = base + missing_penalty * 0.35
    elif lane == "control_room_overlay":
        risk = base + missing_penalty * 0.65
    else:
        # v2.1 keeps the EOL centerline calibrated and does not over-penalize source-limited anomalies.
        risk = base + missing_penalty * 0.55
    if gate in ["race_result", "post_event"]:
        risk *= 0.95
    return round(max(0.015, min(0.42, risk)), 4)


def score_driver(driver: Dict[str, object], grid: Dict[int, int], fallback_rank: int, counts: Dict[str, int], gate: str, lane: str) -> Dict[str, object]:
    dn = int(driver["driver_number"])
    grid_pos = grid.get(dn)
    n = max(20, len(grid) if grid else 20)
    team = str(driver.get("team_name", "Unknown"))
    team_prior = TEAM_PRIOR.get(team, 0.36)
    grid_component = float(grid_pos if grid_pos else fallback_rank)
    prior_component = team_prior * 20.0
    sr = source_readiness_score(counts, gate)

    # Gate/lane weighting. Lower score is better.
    if gate == "pre_weekend":
        grid_weight = 0.05 if grid_pos else 0.0
        prior_weight = 0.70
        uncertainty_weight = 0.25
    elif gate == "post_fp3":
        grid_weight = 0.10 if grid_pos else 0.0
        prior_weight = 0.55
        uncertainty_weight = 0.35
    elif gate == "post_qualifying":
        grid_weight = 0.62 if grid_pos else 0.18
        prior_weight = 0.28
        uncertainty_weight = 0.10
    else:
        grid_weight = 0.60 if grid_pos else 0.18
        prior_weight = 0.25
        uncertainty_weight = 0.15

    if lane == "stable_baseline":
        lane_aggression = 0.00
        overlay_adjust = 0.0
    elif lane == "control_room_overlay":
        lane_aggression = 0.10
        overlay_adjust = (1.0 - sr) * 1.10
    else:
        lane_aggression = 0.16
        overlay_adjust = (1.0 - sr) * 0.80

    deterministic_tie = (dn % 97) / 1000.0
    base_score = grid_weight * grid_component + prior_weight * prior_component + uncertainty_weight * fallback_rank
    risk = reliability_risk(driver, counts, gate, lane)
    degradation = round(min(1.0, 0.28 + team_prior * 0.55 + (1.0 - sr) * 0.12), 4)
    track_position_score = round(1.0 - ((grid_component - 1.0) / max(1.0, n - 1.0)), 4)
    final_score = base_score + overlay_adjust + risk * (2.0 + lane_aggression) + degradation * 0.35 + deterministic_tie

    return {
        "driver_number": dn,
        "driver_name": driver.get("driver_name", f"Driver {dn}"),
        "team_name": team,
        "grid_position": grid_pos if grid_pos is not None else "",
        "raw_rank_score_low_better": round(final_score, 6),
        "source_readiness_score": sr,
        "reliability_eol_score": risk,
        "performance_degradation_score": degradation,
        "track_position_score": track_position_score,
    }


def produce_rows(event_id: str, race_name: str, gate: str, lane: str, drivers: List[Dict[str, object]], grid: Dict[int, int], counts: Dict[str, int], sources: Dict[str, Path]) -> List[Dict[str, object]]:
    scored: List[Dict[str, object]] = []
    for i, driver in enumerate(drivers, start=1):
        scored.append(score_driver(driver, grid, i, counts, gate, lane))
    scored.sort(key=lambda r: (float(r["raw_rank_score_low_better"]), int(r["driver_number"])))
    n = len(scored)
    now = utc_now()
    rows: List[Dict[str, object]] = []
    confidence_gate_cap = {
        "pre_weekend": 0.62,
        "post_fp3": 0.72,
        "post_qualifying": 0.84,
        "race_result": 0.50,
        "post_event": 0.40,
    }.get(gate, 0.65)
    for rank, row in enumerate(scored, start=1):
        win = probability_from_rank(rank, n, "win")
        podium = probability_from_rank(rank, n, "podium")
        top10 = probability_from_rank(rank, n, "top10")
        sr = float(row["source_readiness_score"])
        confidence = round(min(confidence_gate_cap, max(0.05, sr * confidence_gate_cap)), 4)
        rows.append({
            "event_id": event_id,
            "race_name": race_name,
            "gate": gate,
            "engine_lane": lane,
            "driver_number": row["driver_number"],
            "driver_name": row["driver_name"],
            "team_name": row["team_name"],
            "grid_position": row["grid_position"],
            "predicted_position": rank,
            "predicted_rank_score_low_better": row["raw_rank_score_low_better"],
            "win_probability": round(win * confidence, 5),
            "podium_probability": round(podium * confidence, 5),
            "top10_probability": round(top10 * confidence, 5),
            "dnf_probability": row["reliability_eol_score"],
            "confidence_score": confidence,
            "source_readiness_score": sr,
            "reliability_eol_score": row["reliability_eol_score"],
            "performance_degradation_score": row["performance_degradation_score"],
            "track_position_score": row["track_position_score"],
            "forecast_generation_utc": now,
            "forecast_status": "actual_forecast_row_generated_from_available_sources",
            "forecast_basis": "source_closure_plus_engine_lane_policy",
            "stable_output_overwrite_allowed": "false",
            "promotion_eligible_from_this_row": "false",
            "blind_validation_note": "Eligible only if locked before outcome by Forecast Bundle Locker.",
        })
    return rows


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def copy_to_latest_and_history(repo: Path, event_id: str, run_id: str, gate: str, lane: str, rows: List[Dict[str, object]], source_manifest: List[Dict[str, object]], meta: Dict[str, object]) -> None:
    latest_dir = repo / "latest" / "forecasts" / event_id / gate / lane
    history_dir = repo / "history" / "forecasts" / event_id / run_id / gate / lane
    for base in [latest_dir, history_dir]:
        write_csv(base / "forecast_rows.csv", rows)
        write_csv(base / "source_snapshot_manifest.csv", source_manifest)
        write_json(base / "forecast_metadata.json", meta)
        # Compatibility mirror for older chain components.
        mirror = repo / "latest" / "forecast_outputs" / event_id / gate / lane if base == latest_dir else repo / "history" / "forecast_outputs" / event_id / run_id / gate / lane
        write_csv(mirror / "forecast_rows.csv", rows)
        write_json(mirror / "forecast_metadata.json", meta)


def main() -> int:
    ap = argparse.ArgumentParser(description="Produce actual forecast rows for F1 gate/lane validation.")
    ap.add_argument("--event-id", required=True)
    ap.add_argument("--race-name", default="F1 Event")
    ap.add_argument("--gate", default="all")
    ap.add_argument("--lane", default="all")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--strict-source", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    gates = GATES if args.gate == "all" else [args.gate]
    lanes = LANES if args.lane == "all" else [args.lane]
    invalid_gates = [g for g in gates if g not in GATES]
    invalid_lanes = [l for l in lanes if l not in LANES]
    if invalid_gates or invalid_lanes:
        raise SystemExit(f"Invalid gates={invalid_gates} lanes={invalid_lanes}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runtime_dir = repo / "_runtime" / "actual_forecast_producer_v1" / run_id
    runtime_dir.mkdir(parents=True, exist_ok=True)

    sources, counts = find_sources(repo)
    drivers = build_driver_universe(sources)
    grid = starting_grid_map(sources)
    source_manifest = []
    for source_name in sorted(SOURCE_FILES.keys()):
        p = sources.get(source_name)
        source_manifest.append({
            "source_name": source_name,
            "found": bool(p),
            "row_count": counts.get(source_name, 0),
            "path": str(p.relative_to(repo)) if p else "",
        })

    audit = {
        "run_id": run_id,
        "event_id": args.event_id,
        "race_name": args.race_name,
        "requested_gate": args.gate,
        "requested_lane": args.lane,
        "gates": gates,
        "lanes": lanes,
        "driver_universe_count": len(drivers),
        "sources_found": {k: str(v.relative_to(repo)) for k, v in sources.items()},
        "source_counts": counts,
        "forecast_rows_created": 0,
        "gate_lane_files_created": 0,
        "status": "pending",
        "promotion_allowed": False,
        "stable_output_overwrite_allowed": False,
        "source_discovery_version": "v1.1_data_subfolder_recursive_hotfix",
    }

    if not drivers:
        audit["status"] = "pending_required_driver_source_rows"
        audit["reason"] = "No usable drivers or starting-grid source rows found. No forecast rows created."
        write_json(runtime_dir / "actual_forecast_producer_audit.json", audit)
        write_csv(runtime_dir / "source_snapshot_manifest.csv", source_manifest)
        print(json.dumps(audit, indent=2, sort_keys=True))
        if args.strict_source:
            return 2
        return 0

    total_rows = 0
    files_created = 0
    for gate in gates:
        for lane in lanes:
            rows = produce_rows(args.event_id, args.race_name, gate, lane, drivers, grid, counts, sources)
            meta = {
                "run_id": run_id,
                "event_id": args.event_id,
                "race_name": args.race_name,
                "gate": gate,
                "engine_lane": lane,
                "row_count": len(rows),
                "generated_utc": utc_now(),
                "validation_classification": "actual_forecast_rows_generated_from_available_prelock_sources",
                "blind_validity": "not_blind_until_locked_before_outcome",
                "promotion_allowed": False,
                "stable_output_overwrite_allowed": False,
                "source_counts": counts,
            }
            copy_to_latest_and_history(repo, args.event_id, run_id, gate, lane, rows, source_manifest, meta)
            total_rows += len(rows)
            files_created += 1

    audit["forecast_rows_created"] = total_rows
    audit["gate_lane_files_created"] = files_created
    audit["status"] = "forecast_rows_created" if total_rows > 0 else "no_forecast_rows_created"
    write_json(runtime_dir / "actual_forecast_producer_audit.json", audit)
    write_csv(runtime_dir / "source_snapshot_manifest.csv", source_manifest)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
