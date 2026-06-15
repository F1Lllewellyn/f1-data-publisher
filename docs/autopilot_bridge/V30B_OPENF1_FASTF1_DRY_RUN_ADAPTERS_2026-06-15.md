# V30B OpenF1/FastF1 Dry-Run Adapters - 2026-06-15

## Purpose

Add the first source adapter layer for the Session Data Processor Loop while staying PR-only and dry-run only.

## Scope

Added files:

- scripts/autopilot/source_readiness_manifest_v30b.json
- scripts/autopilot/openf1_source_adapter_v30b.mjs
- scripts/autopilot/fastf1_source_adapter_v30b.mjs
- scripts/autopilot/session_source_readiness_processor_v30b.mjs

## Behavior

The v30B processor runs both adapters in dry-run mode and writes readiness status artifacts.

Command:

    node scripts/autopilot/session_source_readiness_processor_v30b.mjs --mode dry_run

Expected outputs:

- health/session_source_readiness_v30b_last_status.json
- logs/session_source_readiness/openf1_adapter_v30b.json
- logs/session_source_readiness/fastf1_adapter_v30b.json
- logs/session_source_readiness/v30b_run_*.json

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine remains protected.
- Canonical workbook remains protected.
- No workbook mutation is introduced.
- No prediction accuracy claim is made.

## Follow-up

- v30C: bounded live source validation.
- v30D: sandbox workbook/KPI readiness update path.
- v30E: material-change notification logic.
