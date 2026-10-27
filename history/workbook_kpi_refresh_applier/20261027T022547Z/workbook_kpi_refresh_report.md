# F1 Workbook/KPI Refresh Applier Report

## Verdict

Pass with warnings

## Run

- Run ID: `20261027T022547Z`
- Created UTC: `2026-10-27T02:25:47.746619+00:00`
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

- `history/workbook_kpi_refresh_applier/20261027T022547Z/sandbox_workbook_update_plan_applied.json` (fb12182c54da...)
- `history/workbook_kpi_refresh_applier/20261027T022547Z/refreshed_workbook_kpi_readiness.csv` (0cec7d64ff1f...)
- `history/workbook_kpi_refresh_applier/20261027T022547Z/F1_Workbook_KPI_SANDBOX_Refresh_United_States_-_Austin_-_Austin_Race_20261027T022547Z.xlsx` (1e8d90f08c9b...)
- `history/workbook_kpi_refresh_applier/20261027T022547Z/upstream_latest_manifest_snapshot.json` (2438cfd55c30...)
- `history/workbook_kpi_refresh_applier/20261027T022547Z/upstream_data_readiness_snapshot.json` (033a9f3b1269...)
- `history/workbook_kpi_refresh_applier/20261027T022547Z/upstream_combined_source_manifest_snapshot.json` (b196897a32d3...)

## Governance

- Canonical workbook overwrite: **blocked**
- Stable engine modification: **blocked**
- Model promotion: **blocked**
- Delete/cleanup authority: **blocked**

## Classification

This is a sandbox workbook/KPI refresh artifact. It may support readiness, forecast bundle discipline, and fantasy/race prediction state refresh, but it does not promote model logic.
