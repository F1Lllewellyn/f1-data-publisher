# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261122T063746Z`
- Created UTC: `2026-11-22T06:37:46.593892+00:00`
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

- `history/workbook_kpi_refresh_applier/20261122T063746Z/sandbox_workbook_update_plan_applied.json` (a11be42cb998...)
- `history/workbook_kpi_refresh_applier/20261122T063746Z/refreshed_workbook_kpi_readiness.csv` (e8714617e4ef...)
- `history/workbook_kpi_refresh_applier/20261122T063746Z/F1_Workbook_KPI_SANDBOX_Refresh_United_States_-_Las_Vegas_-_Las_Vegas_Race_20261122T063746Z.xlsx` (bdff66a02b17...)
- `history/workbook_kpi_refresh_applier/20261122T063746Z/upstream_latest_manifest_snapshot.json` (894908c56ac9...)
- `history/workbook_kpi_refresh_applier/20261122T063746Z/upstream_data_readiness_snapshot.json` (9dd5a5d6fdc6...)
- `history/workbook_kpi_refresh_applier/20261122T063746Z/upstream_combined_source_manifest_snapshot.json` (8f1c0ce66bbb...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
