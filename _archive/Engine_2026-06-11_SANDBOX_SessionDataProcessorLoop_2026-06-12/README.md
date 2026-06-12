# Engine_2026-06-11_SANDBOX_SessionDataProcessorLoop

Sandbox-only Session Data Processor Loop for the F1 Prediction Engine.

## Purpose

This package closes the production-readiness gap where race-weekend watcher automations were running but the actual workbook/KPI/source package was not refreshed with live/session data.

The target operating loop is:

```text
Session ends
-> watcher detects timing/source-readiness gate
-> processor pulls OpenF1 / FastF1 / FIA / public session data
-> validates IDs, timestamps, lap counts, columns, duplicates, and anomalies
-> classifies each source as clean / partial / late / conflicting / needs_manual_review
-> writes refreshed dated session source artifacts
-> writes updated readiness manifests
-> creates workbook/KPI update artifacts or sandbox workbook update plan
-> saves Forecast Bundle Ledger snapshot
-> refreshes Race Predictions and Fantasy readiness state
-> notifies only if readiness materially improves or forecast state changes
```

## Sandbox governance

- Does not overwrite the canonical workbook.
- Does not modify `Engine_2026-06-07_STABLE`.
- Does not promote any model layer.
- Does not delete historical/source files.
- Writes dated outputs, manifests, checksums, and validation notes only.

## No-code workflows included

After installation, GitHub Actions will show:

- `F1 Session Data Processor - Safe Test Button`
- `F1 Session Data Processor - Run Now Button`
- `F1 Session Data Processor Loop v1` scheduled processor

The Safe Test Button checks installation only. The Run Now Button attempts a real processor pass and writes outputs only when data validation succeeds.

## Install

Run:

```text
installer/RUN_F1_SESSION_DATA_PROCESSOR_LOOP_WINDOWS.bat
```

Press Enter when asked for the repo path. It defaults to:

```text
C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher
```

Then commit and push using GitHub Desktop.

## Key files

- `scripts/session_data_processor/session_data_processor_loop_v1.py`
- `scripts/session_data_processor/health_check_session_processor_package_v1.py`
- `configs/session_data_processor/session_data_processor_policy_v1.json`
- `schemas/session_readiness_manifest_v1.schema.json`
- `docs/SESSION_DATA_PROCESSOR_LOOP_DESIGN.md`
- `docs/SOURCE_READINESS_TO_INGEST_FLOW.md`
- `docs/VALIDATION_REPORT_SESSION_DATA_PROCESSOR_LOOP_2026-06-12.md`
