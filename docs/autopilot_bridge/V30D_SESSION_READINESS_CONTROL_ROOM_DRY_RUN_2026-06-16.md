# V30D Session Readiness Control Room Dry-Run

This PR adds a dry-run Control Room summary layer for the Session Data Processor Loop.

## Scope

- Adds a v30D policy file for readiness aggregation.
- Adds a v30D Control Room summary script.
- Consolidates optional v30A/v30B/v30C health manifests when present.
- Writes only health/log style artifacts when executed.

## Command

Run in dry-run mode:

    node scripts/autopilot/session_readiness_control_room_v30d.mjs --mode dry_run

Expected outputs:

- health/session_readiness_control_room_v30d_status.json
- logs/session_readiness_control_room/v30d_run_*.json

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook mutation remains disabled.
- Forecast Bundle Ledger write remains disabled until a later reviewed patch.

## Follow-up

The next decision point is either:

- v30E: material-change notification logic, still dry-run/sandbox only.
- v31: bridge hygiene to prevent generated status files from creating merge conflicts.
