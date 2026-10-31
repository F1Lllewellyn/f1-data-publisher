# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261031T193300Z`
- Created UTC: `2026-10-31T19:33:00.391641+00:00`
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

- `history/workbook_kpi_refresh_applier/20261031T193300Z/sandbox_workbook_update_plan_applied.json` (e76d7293a563...)
- `history/workbook_kpi_refresh_applier/20261031T193300Z/refreshed_workbook_kpi_readiness.csv` (c5f18ae80b1d...)
- `history/workbook_kpi_refresh_applier/20261031T193300Z/F1_Workbook_KPI_SANDBOX_Refresh_Mexico_-_Mexico_City_-_Mexico_City_Practice_3_20261031T193300Z.xlsx` (d5c45a570ec2...)
- `history/workbook_kpi_refresh_applier/20261031T193300Z/upstream_latest_manifest_snapshot.json` (7ac9c37afb93...)
- `history/workbook_kpi_refresh_applier/20261031T193300Z/upstream_data_readiness_snapshot.json` (208088be27f5...)
- `history/workbook_kpi_refresh_applier/20261031T193300Z/upstream_combined_source_manifest_snapshot.json` (c2e339cb8755...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
