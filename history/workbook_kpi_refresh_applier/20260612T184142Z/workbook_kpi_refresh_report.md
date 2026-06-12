# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20260612T184142Z`
- Created UTC: `2026-06-12T18:41:42.619619+00:00`
- Source status: `missing`
- Material change: `False`

## Warnings

- workbook_kpi_readiness_csv_missing_or_empty

## Outputs

- `history/workbook_kpi_refresh_applier/20260612T184142Z/sandbox_workbook_update_plan_applied.json` (0a6ffcda4f50...)
- `history/workbook_kpi_refresh_applier/20260612T184142Z/refreshed_workbook_kpi_readiness.csv` (b235ce791aa1...)
- `history/workbook_kpi_refresh_applier/20260612T184142Z/F1_Workbook_KPI_SANDBOX_Refresh_unknown_event_session_20260612T184142Z.xlsx` (39863939fbfe...)
- `history/workbook_kpi_refresh_applier/20260612T184142Z/upstream_latest_manifest_snapshot.json` (da04350d69fe...)
- `history/workbook_kpi_refresh_applier/20260612T184142Z/upstream_data_readiness_snapshot.json` (f65108ab9cee...)
- `history/workbook_kpi_refresh_applier/20260612T184142Z/upstream_combined_source_manifest_snapshot.json` (a1d605e7a996...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
