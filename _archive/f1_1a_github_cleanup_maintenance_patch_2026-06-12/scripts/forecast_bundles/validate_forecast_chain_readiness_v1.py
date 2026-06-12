#!/usr/bin/env python3
"""Forecast chain readiness validator.

Validates the upstream chain only when actual forecast rows exist. If rows are absent,
it exits successfully with status pending_actual_forecast_rows rather than fabricating bundles.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

GATES = ["pre_weekend", "post_fp3", "post_qualifying", "race_result", "post_event"]
LANES = ["stable_baseline", "control_room_overlay", "experimental_challenger"]
SOURCE_PATTERNS = [
    "latest/forecasts/{event_id}/{gate}/{lane}/forecast_rows.csv",
    "latest/forecast_outputs/{event_id}/{gate}/{lane}/forecast_rows.csv",
    "latest/method_e_control_room/forecasts/{event_id}/{gate}/{lane}.csv",
]
REQUIRED_COLUMNS_ANY = ["driver", "driver_name", "abbreviation", "position", "predicted_position", "rank"]


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def count_rows_csv(path: Path) -> tuple[int, list[str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            cols = list(reader.fieldnames or [])
            rows = sum(1 for _ in reader)
        return rows, cols
    except Exception:
        return 0, []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--event-id", required=True)
    ap.add_argument("--gate", default="all")
    ap.add_argument("--lane", default="all")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero if any required source is missing")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    gates = GATES if args.gate == "all" else [args.gate]
    lanes = LANES if args.lane == "all" else [args.lane]

    out_dir = repo / "latest" / "forecast_chain_readiness" / args.event_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    found_count = 0
    missing_count = 0
    invalid_count = 0
    for gate in gates:
        for lane in lanes:
            found_path = None
            row_count = 0
            cols = []
            for pattern in SOURCE_PATTERNS:
                candidate = repo / pattern.format(event_id=args.event_id, gate=gate, lane=lane)
                if candidate.exists():
                    r, c = count_rows_csv(candidate)
                    if r > 0:
                        found_path = candidate
                        row_count = r
                        cols = c
                        break
            has_required = bool(set(cols) & set(REQUIRED_COLUMNS_ANY))
            if found_path and has_required:
                status = "actual_forecast_rows_found"
                found_count += 1
            elif found_path and not has_required:
                status = "invalid_forecast_rows_missing_required_identity_or_rank_column"
                invalid_count += 1
            else:
                status = "pending_actual_forecast_rows"
                missing_count += 1
            rows.append({
                "event_id": args.event_id,
                "gate": gate,
                "lane": lane,
                "status": status,
                "source_path": str(found_path.relative_to(repo)) if found_path else "",
                "row_count": row_count,
                "columns": "|".join(cols),
            })

    summary = {
        "run_timestamp_utc": now_utc(),
        "event_id": args.event_id,
        "gate_request": args.gate,
        "lane_request": args.lane,
        "validation_basis": "actual_forecast_rows_only",
        "required_combinations": len(gates) * len(lanes),
        "actual_forecast_sources_found": found_count,
        "pending_actual_forecast_rows": missing_count,
        "invalid_sources": invalid_count,
        "status": "pass" if found_count == len(gates) * len(lanes) and invalid_count == 0 else "pass_with_warnings",
        "promotion_allowed": False,
        "notes": [
            "This validator does not fabricate bundles.",
            "If sources are pending, run the forecast-producing workflow/source writer first.",
        ],
    }

    with (out_dir / "forecast_chain_readiness_matrix.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "forecast_chain_readiness_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(
        "# Forecast Chain Readiness\n\n"
        f"Event: `{args.event_id}`\n\n"
        f"Status: `{summary['status']}`\n\n"
        f"Actual forecast source combinations found: {found_count}/{summary['required_combinations']}\n\n"
        "This is a validation/readiness artifact only. It does not create or promote forecasts.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    if args.strict and (missing_count or invalid_count):
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
