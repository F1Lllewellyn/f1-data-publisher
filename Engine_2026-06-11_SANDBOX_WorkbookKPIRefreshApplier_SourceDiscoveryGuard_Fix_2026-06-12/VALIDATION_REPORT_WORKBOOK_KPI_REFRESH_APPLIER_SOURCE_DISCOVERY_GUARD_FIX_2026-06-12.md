# Validation Report - Workbook/KPI Refresh Applier Source Discovery + Commit Guard Fix

## Verdict

Pass with warnings.

## Why this fix was needed

The Safe Test Button passed, but the Run Now Button produced a sandbox workbook with:

- `source_status: missing`
- `material_change: false`
- warning: `workbook_kpi_readiness_csv_missing_or_empty`
- workbook name: `F1_Workbook_KPI_SANDBOX_Refresh_unknown_event_session_...xlsx`

The Session Data Processor had actually committed FP2 source artifacts under a nested concrete folder:

`latest/session_data_processor/2026_1287_spain_barcelona_catalunya/practice_2_11301/`

The applier was only checking the parent folder, so it missed valid source artifacts.

## Local validation performed

### Test 1 - nested valid source

A mock repo was created with a nested session processor output folder containing:

- `sandbox_workbook_update_plan.json`
- `workbook_kpi_readiness.json`
- `workbook_kpi_readiness.csv`
- `forecast_bundle_ledger_snapshot.json`

Result:

- `status: refresh_applied`
- `commit_allowed: true`
- `source_status: needs_manual_review`
- `material_change: true`
- sandbox workbook used the event/session label: `Spain_Practice_2`

### Test 2 - missing source

A mock repo with no session processor artifacts was tested.

Result:

- `status: no_action`
- `commit_allowed: false`
- no workbook/KPI refresh output folder was created

## Governance validation

- Canonical workbook overwrite: blocked
- Stable engine modification: blocked
- Promotion: blocked
- Delete authority: not granted

## Remaining warning

A previously committed `unknown_event_session` sandbox artifact may remain in repository history. This patch does not delete old files. It prevents repeats and overwrites `latest/workbook_kpi_refresh_applier` with source-backed outputs on the next successful run.
