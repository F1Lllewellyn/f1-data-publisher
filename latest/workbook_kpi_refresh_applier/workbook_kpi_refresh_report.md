# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261102T003818Z`
- Created UTC: `2026-11-02T00:38:18.250793+00:00`
- Source status: `needs_manual_review`
- Readiness quality: `blocked_manual_review_required_source`
- Material change: `True`
- Diagnostic publish allowed: `True`
- Downstream eligible: `False`

## Warnings

- diagnostic_only_source_status=needs_manual_review
- readiness_requires_manual_review
- readiness_blocking_issues
- required_source_evidence_unverified
- required_source_status_needs_manual_review
- readiness_quality_blocked_manual_review_required_source

## Outputs

- `history/workbook_kpi_refresh_applier/20261102T003818Z/sandbox_workbook_update_plan_applied.json` (93f6d3f0ca37...)
- `history/workbook_kpi_refresh_applier/20261102T003818Z/refreshed_workbook_kpi_readiness.csv` (47ae243ce0f7...)
- `history/workbook_kpi_refresh_applier/20261102T003818Z/F1_Workbook_KPI_SANDBOX_Refresh_Mexico_-_Mexico_City_-_Mexico_City_Race_20261102T003818Z.xlsx` (f5de233385b1...)
- `history/workbook_kpi_refresh_applier/20261102T003818Z/upstream_latest_manifest_snapshot.json` (2071e2ecd580...)
- `history/workbook_kpi_refresh_applier/20261102T003818Z/upstream_data_readiness_snapshot.json` (2ccf27f1cb48...)
- `history/workbook_kpi_refresh_applier/20261102T003818Z/upstream_combined_source_manifest_snapshot.json` (59c0277c20c4...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
