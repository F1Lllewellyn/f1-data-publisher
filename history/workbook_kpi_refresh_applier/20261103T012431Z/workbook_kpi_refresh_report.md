# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261103T012431Z`
- Created UTC: `2026-11-03T01:24:31.818508+00:00`
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

- `history/workbook_kpi_refresh_applier/20261103T012431Z/sandbox_workbook_update_plan_applied.json` (7e03b289386a...)
- `history/workbook_kpi_refresh_applier/20261103T012431Z/refreshed_workbook_kpi_readiness.csv` (47ae243ce0f7...)
- `history/workbook_kpi_refresh_applier/20261103T012431Z/F1_Workbook_KPI_SANDBOX_Refresh_Mexico_-_Mexico_City_-_Mexico_City_Race_20261103T012431Z.xlsx` (98cbf88946b8...)
- `history/workbook_kpi_refresh_applier/20261103T012431Z/upstream_latest_manifest_snapshot.json` (dbe7a7ed5c6d...)
- `history/workbook_kpi_refresh_applier/20261103T012431Z/upstream_data_readiness_snapshot.json` (f093849af8ba...)
- `history/workbook_kpi_refresh_applier/20261103T012431Z/upstream_combined_source_manifest_snapshot.json` (acf0e7bd2275...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
