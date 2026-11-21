# F1 Peak-Elite Orchestrator Report

Created UTC: `2026-11-21T00:50:17.427917Z`
Operation: `full_run_chain`
Status: **fail**

## Latest source state
- Race/event: `United States - Las Vegas - Las Vegas`
- Session: `Practice 2`
- Source status: `clean`
- Workbook source status: `clean`
- Workbook commit allowed: `True`

## Steps
- `workflow_commit_block_check`: PASS (`0`)
- `workflow_static_validation`: FAIL (`1`)
- `workflow_meta_health_v1`: FAIL (`1`)
- `repo_canonicalization_report_only`: PASS (`0`)
- `source_readiness_classifier_v2_self_test`: PASS (`0`)
- `session_data_processor_run_now`: FAIL (`2`)
- `workbook_kpi_refresh_apply`: PASS (`0`)
- `dashboard_readiness_publish`: PASS (`0`)
- `peak_elite_health_after_run`: FAIL (`1`)
- `cleanup_inventory_report_only`: PASS (`0`)

## Governance
- Stable engine modified: `false`
- Canonical workbook overwritten: `false`
- Model promotion: `false`
- 2026 no-DRS rule: active by project governance; this layer does not create DRS assumptions

## Interpretation
The orchestration layer failed before reaching production-ready state. Review the failed step tails in the runtime artifact.
