# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261102T170110Z`
- Created UTC: `2026-11-02T17:01:10.223637+00:00`
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

- `history/workbook_kpi_refresh_applier/20261102T170110Z/sandbox_workbook_update_plan_applied.json` (4aac464a7236...)
- `history/workbook_kpi_refresh_applier/20261102T170110Z/refreshed_workbook_kpi_readiness.csv` (47ae243ce0f7...)
- `history/workbook_kpi_refresh_applier/20261102T170110Z/F1_Workbook_KPI_SANDBOX_Refresh_Mexico_-_Mexico_City_-_Mexico_City_Race_20261102T170110Z.xlsx` (caca999b7de8...)
- `history/workbook_kpi_refresh_applier/20261102T170110Z/upstream_latest_manifest_snapshot.json` (42c585282d07...)
- `history/workbook_kpi_refresh_applier/20261102T170110Z/upstream_data_readiness_snapshot.json` (1b1e0a1a7aed...)
- `history/workbook_kpi_refresh_applier/20261102T170110Z/upstream_combined_source_manifest_snapshot.json` (d8fe18596571...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
