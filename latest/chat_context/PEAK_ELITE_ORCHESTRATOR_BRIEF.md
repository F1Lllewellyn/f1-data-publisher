# F1 Peak-Elite Orchestrator Report

Created UTC: `2026-11-22T14:55:26.622354Z`
Operation: `full_run_chain`
Status: **hold_downstream_not_verified**

## Latest source state
- Race/event: `United States - Las Vegas - Las Vegas`
- Session: `Race`
- Source status: `needs_manual_review`
- Workbook source status: `needs_manual_review`
- Workbook commit allowed: `True`

## Steps
- `workflow_commit_block_check`: PASS (`0`)
- `workflow_static_validation`: PASS (`0`)
- `workflow_meta_health_v1`: PASS (`0`)
- `repo_canonicalization_report_only`: PASS (`0`)
- `source_readiness_classifier_v2_self_test`: PASS (`0`)
- `session_data_processor_run_now`: PASS (`0`)
- `workbook_kpi_refresh_apply`: PASS (`0`)
- `dashboard_readiness_publish`: PASS (`0`)
- `peak_elite_health_after_run`: PASS (`0`)
- `cleanup_inventory_report_only`: PASS (`0`)

## Governance
- Stable engine modified: `false`
- Canonical workbook overwritten: `false`
- Model promotion: `false`
- 2026 no-DRS rule: active by project governance; this layer does not create DRS assumptions

## Interpretation
The capture-to-dashboard chain did not complete and verify the current source session. Do not treat earlier green readiness as current.
