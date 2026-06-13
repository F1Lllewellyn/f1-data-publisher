# F1 Peak-Elite Orchestrator Report

Created UTC: `2026-06-13T03:35:38.847046Z`
Operation: `full_run_chain`
Status: **fail**

## Latest source state
- Race/event: `Spain - Barcelona - Catalunya`
- Session: `Practice 2`
- Source status: `clean`
- Workbook source status: `clean`
- Workbook commit allowed: `True`

## Steps
- `workflow_commit_block_repair`: PASS (`0`)
- `workflow_static_validation`: FAIL (`1`)
- `workflow_meta_health_v1`: FAIL (`1`)
- `repo_canonicalization_safe_apply`: PASS (`0`)
- `source_readiness_classifier_v2_self_test`: PASS (`0`)
- `session_data_processor_run_now`: PASS (`0`)
- `workbook_kpi_refresh_apply`: PASS (`0`)
- `dashboard_readiness_publish`: PASS (`0`)
- `peak_elite_health_after_run`: PASS (`1`)
- `cleanup_inventory_report_only`: PASS (`0`)

## Governance
- Stable engine modified: `false`
- Canonical workbook overwritten: `false`
- Model promotion: `false`
- 2026 no-DRS rule: active by project governance; this layer does not create DRS assumptions

## Interpretation
The orchestration layer failed before reaching production-ready state. Review the failed step tails in the runtime artifact.
