# F1 1B v27 — Session Gate Automation + Legacy Collision Hardening

Date: 2026-06-13

## Purpose

v27 moves the current working pre-race workflow closer to peak-elite automation without activating forecast gates or promoting model logic.

It addresses two observed problems:

1. The canonical Control Room chain was still too manual for race-weekend operations.
2. Legacy/parallel workflows could fail noisily or collide with the canonical Control Room commit path.

## What changes

- Scheduled Control Room runs now default to `full_run_chain` with `run_forecast_gate=false`.
- A v27 scheduled session-gate decision report is written under `latest/session_gate_watch_v27/`.
- The legacy integrated Auto-Repair workflow now shares the canonical write concurrency group and yields when a recent canonical Control Room/output-contract state exists.
- The legacy OpenF1 prereace workflow now classifies live-session unauthenticated OpenF1 401 restrictions as `source_temporarily_restricted/deferred` instead of failing the workflow.
- v27 acceptance tests validate workflow wiring, no inline Python heredocs, no raw git push, protected engine/workbook guards, and forecast gate off.

## Boundaries

- Does not activate forecast gate.
- Does not allow promotion.
- Does not touch `Engine_2026-06-07_STABLE`.
- Does not overwrite canonical workbooks.
- Does not delete, archive, or restructure files.
- Does not generate Race Predictions/Fantasy outputs automatically.

## Expected post-install test

Run:

`F1 Peak Elite Control Room - One Click v1`

with:

- `operation = full_run_chain`
- `commit_outputs = true`
- `run_forecast_gate = false`

Expected:

- Control Room passes.
- Bridge automatically runs.
- v27 validation report exists under `latest/1b_validation/`.
- `latest/session_gate_watch_v27/gate_decision.json` exists.
- Legacy failed workflows should no longer block or collide with the canonical path.
