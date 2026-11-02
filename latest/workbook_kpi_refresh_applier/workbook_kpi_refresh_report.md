# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261102T064927Z`
- Created UTC: `2026-11-02T06:49:27.808717+00:00`
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

- `history/workbook_kpi_refresh_applier/20261102T064927Z/sandbox_workbook_update_plan_applied.json` (f19424d7f163...)
- `history/workbook_kpi_refresh_applier/20261102T064927Z/refreshed_workbook_kpi_readiness.csv` (47ae243ce0f7...)
- `history/workbook_kpi_refresh_applier/20261102T064927Z/F1_Workbook_KPI_SANDBOX_Refresh_Mexico_-_Mexico_City_-_Mexico_City_Race_20261102T064927Z.xlsx` (991865355391...)
- `history/workbook_kpi_refresh_applier/20261102T064927Z/upstream_latest_manifest_snapshot.json` (614b69bee0a8...)
- `history/workbook_kpi_refresh_applier/20261102T064927Z/upstream_data_readiness_snapshot.json` (71f8a38bb821...)
- `history/workbook_kpi_refresh_applier/20261102T064927Z/upstream_combined_source_manifest_snapshot.json` (a559963d3d0f...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
