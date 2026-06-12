# Engine_2026-06-11_SANDBOX_AutoRepairScheduledIntegration_2026-06-12

## Purpose

This sandbox patch wires the Auto-Repair Orchestrator behind the scheduled Session Data Processor so the engine can attempt the full recovery path automatically:

```text
Session watcher / timing gate
-> Session Data Processor
-> Auto-Repair session-to-workbook recovery
-> Workbook/KPI Refresh Applier
-> commit only if source-backed
```

## Plain-English behavior

If a session exists and can be ingested, the integrated loop refreshes the session artifacts and then immediately verifies that Workbook/KPI refresh is source-backed.

If the workbook refresh cannot see a valid session source, Auto-Repair attempts recovery by running the session processor and workbook refresh chain again. It commits only when the final status is source-backed.

If source data is still missing, the workflow stops safely and uploads diagnostics.

## No-code buttons added

- `F1 Session Auto-Repair Integrated - Safe Test Button`
- `F1 Session Auto-Repair Integrated - Run Now Button`
- `F1 Session Processor + Auto-Repair Integrated Loop v1` scheduled workflow

## Governance

- Sandbox branch only.
- Canonical workbook overwrite is blocked.
- `Engine_2026-06-07_STABLE` is not modified.
- No promotion is allowed.
- No delete/overwrite authority is granted.
- `_runtime` diagnostics are uploaded as artifacts, not committed.

## Install

Run:

```text
installer/RUN_F1_AUTOREPAIR_SCHEDULED_INTEGRATION_WINDOWS.bat
```

Press Enter for the repo path, then commit and push in GitHub Desktop.

## Validate

First run:

```text
F1 Session Auto-Repair Integrated - Safe Test Button
```

Then run:

```text
F1 Session Auto-Repair Integrated - Run Now Button
```
