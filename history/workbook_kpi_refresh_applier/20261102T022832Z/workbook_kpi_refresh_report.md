# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261102T022832Z`
- Created UTC: `2026-11-02T02:28:32.899020+00:00`
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

- `history/workbook_kpi_refresh_applier/20261102T022832Z/sandbox_workbook_update_plan_applied.json` (a95c71469828...)
- `history/workbook_kpi_refresh_applier/20261102T022832Z/refreshed_workbook_kpi_readiness.csv` (47ae243ce0f7...)
- `history/workbook_kpi_refresh_applier/20261102T022832Z/F1_Workbook_KPI_SANDBOX_Refresh_Mexico_-_Mexico_City_-_Mexico_City_Race_20261102T022832Z.xlsx` (a3c5ac340913...)
- `history/workbook_kpi_refresh_applier/20261102T022832Z/upstream_latest_manifest_snapshot.json` (a6f6099cf625...)
- `history/workbook_kpi_refresh_applier/20261102T022832Z/upstream_data_readiness_snapshot.json` (b509141d3833...)
- `history/workbook_kpi_refresh_applier/20261102T022832Z/upstream_combined_source_manifest_snapshot.json` (1468effc287e...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
