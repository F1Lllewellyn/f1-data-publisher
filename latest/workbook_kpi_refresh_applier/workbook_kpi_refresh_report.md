# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261029T212521Z`
- Created UTC: `2026-10-29T21:25:21.545005+00:00`
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

- `history/workbook_kpi_refresh_applier/20261029T212521Z/sandbox_workbook_update_plan_applied.json` (e7da26426714...)
- `history/workbook_kpi_refresh_applier/20261029T212521Z/refreshed_workbook_kpi_readiness.csv` (0cec7d64ff1f...)
- `history/workbook_kpi_refresh_applier/20261029T212521Z/F1_Workbook_KPI_SANDBOX_Refresh_United_States_-_Austin_-_Austin_Race_20261029T212521Z.xlsx` (2643c6dfc9fa...)
- `history/workbook_kpi_refresh_applier/20261029T212521Z/upstream_latest_manifest_snapshot.json` (d6e46e8a298c...)
- `history/workbook_kpi_refresh_applier/20261029T212521Z/upstream_data_readiness_snapshot.json` (37454f258ba3...)
- `history/workbook_kpi_refresh_applier/20261029T212521Z/upstream_combined_source_manifest_snapshot.json` (343884c77486...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
