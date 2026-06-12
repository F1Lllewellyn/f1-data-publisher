# Engine_2026-06-11_SANDBOX_WorkbookKPIRefreshApplier_StrictSourceStatus_Fix

## Purpose

This no-code sandbox fix hardens the Workbook/KPI Refresh Applier after the Run Now validation showed a dangerous-but-contained behavior:

- the applier found enough files to build a workbook,
- but the upstream source classification was still `missing`,
- and the workflow committed a sandbox workbook anyway.

This fix makes `source_status=missing` a hard no-commit condition.

## What changed

- Keeps recursive nested Session Data Processor discovery.
- Allows source-backed classifications: `clean`, `partial`, `late`, `conflicting`, `needs_manual_review`.
- Blocks commit for `missing`, `unknown`, `empty`, `placeholder`, `scheduled_not_populated`, or `no_action`.
- Writes `_runtime/workbook_kpi_refresh_status.json` with `commit_allowed=false` when source status is not eligible.
- Keeps canonical workbook overwrite blocked.
- Keeps Engine_2026-06-07_STABLE untouched.
- Keeps model promotion blocked.

## Install

Run:

```text
installer/RUN_F1_WORKBOOK_KPI_REFRESH_APPLIER_WINDOWS.bat
```

Press Enter when asked for the repo path.

Then commit and push through GitHub Desktop.

## Validate

Run:

```text
F1 Workbook KPI Refresh - Run Now Button
```

Expected good result for real FP2 source-backed data:

```json
{
  "status": "refresh_applied",
  "commit_allowed": true,
  "source_status": "needs_manual_review"
}
```

Expected safe stop if the source is still not properly classified:

```json
{
  "status": "no_action",
  "reason": "source_status_not_commit_eligible",
  "commit_allowed": false,
  "source_status": "missing"
}
```
