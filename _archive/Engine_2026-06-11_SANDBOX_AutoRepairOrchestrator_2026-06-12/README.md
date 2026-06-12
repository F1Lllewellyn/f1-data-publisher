# Engine_2026-06-11_SANDBOX_AutoRepairOrchestrator

Sandbox-only Auto-Repair Orchestrator for the F1 Prediction Engine.

## Purpose

This package turns the current safe-stop behavior into a governed recovery loop for the exact failure we just found:

```text
Workbook/KPI refresh cannot find valid session source
-> run Session Data Processor
-> rerun Workbook/KPI Refresh Applier
-> commit only if source-backed
-> write plain-English repair report
```

## No-code buttons added

- `F1 Auto-Repair - Safe Test Button`
- `F1 Auto-Repair - Run Now Button`
- `F1 Auto-Repair - Scheduled Session Workbook Recovery`

## Governance

This layer may only create sandbox/output artifacts. It may not:

- overwrite the canonical workbook;
- modify `Engine_2026-06-07_STABLE`;
- promote any model layer;
- delete source files;
- force-push;
- silently rewrite stable exact P1-P20.

## Recommended validation

1. Install with `installer/RUN_F1_AUTOREPAIR_ORCHESTRATOR_WINDOWS.bat`.
2. Commit/push in GitHub Desktop.
3. Run `F1 Auto-Repair - Safe Test Button`.
4. If that passes, run `F1 Auto-Repair - Run Now Button`.
5. Send the log.

## Promotion decision

`NOT PROMOTED`. This is operational infrastructure, not model promotion.
