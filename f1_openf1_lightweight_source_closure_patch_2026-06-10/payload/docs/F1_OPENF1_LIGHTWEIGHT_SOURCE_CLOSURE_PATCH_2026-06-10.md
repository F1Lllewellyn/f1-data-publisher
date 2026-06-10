# F1 OpenF1 Lightweight Source Closure Patch

## Executive summary

This patch adds a GitHub-side source closure workflow that captures lightweight OpenF1 source lanes after completed sessions. It is designed to reduce or eliminate manual Colab catch-up work.

## Problem solved

The engine previously had blank or incomplete workbook/source lanes even though the data was sourceable. The correct elite-engine behaviour is:

1. Detect the blank.
2. Check whether the data already exists in GitHub artifacts.
3. If missing, retrieve only the lightweight missing lane.
4. Diagnose zero-row endpoints using endpoint-specific retry logic.
5. Preserve the output in GitHub for reuse.

## Installed workflow

`F1 OpenF1 Lightweight Source Closure`

## Installed publisher

`scripts/openf1/publish_openf1_lightweight_source_closure.py`

## Outputs created by each run

- `latest/openf1_lightweight_source_closure/latest_manifest.json`
- `latest/openf1_lightweight_source_closure/data_readiness.json`
- `latest/openf1_lightweight_source_closure/source_readiness_summary.csv`
- `latest/openf1_lightweight_source_closure/combined_source_manifest.csv`
- `latest/openf1_lightweight_source_closure/zero_lane_diagnostics.csv`
- `latest/openf1_lightweight_source_closure/request_log.csv`
- `latest/openf1_lightweight_source_closure/openf1_lightweight_source_closure.zip`
- `history/openf1_lightweight_source_closure/<timestamp>/...`

## Endpoint policy

Required lightweight lanes:

- weather
- race_control
- intervals
- position
- stints
- pit
- starting_grid
- drivers

Opportunistic lane:

- team_radio

Excluded by default:

- car_data
- location

## Zero-lane repair logic

- Position uses session-key retrieval plus meeting-key fallback.
- Pit is retrieved only for race/sprint-like sessions.
- Drivers uses session-level lookup and observed driver-number fallback.
- Team radio is opportunistic and not a hard failure when absent.

## Python UTC fix

The publisher uses timezone-aware UTC timestamps:

`dt.datetime.now(dt.UTC)`

This avoids the Colab/runtime issue found during the repair work.

## Governance

This patch does not alter the canonical workbook, stable model baseline, automations, or prediction logic. It creates GitHub-side source artifacts and diagnostics only.
