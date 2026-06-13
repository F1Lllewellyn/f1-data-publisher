# F1 Peak-Elite Orchestrator Report

Created UTC: `2026-06-13T01:31:20.069924Z`
Operation: `full_run_chain`
Status: **pass_with_warnings**

## Latest source state
- Race/event: `Spain - Barcelona - Catalunya`
- Session: `Practice 2`
- Source status: `partial`
- Workbook source status: `partial`
- Workbook commit allowed: `True`

## Steps
- `workflow_commit_block_repair`: PASS (`0`)
- `workflow_static_validation`: PASS (`0`)
- `workflow_meta_health_v1`: PASS (`0`)
- `repo_canonicalization_safe_apply`: PASS (`0`)
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
The processor produced source-backed artifacts, but readiness is not clean. Use as confidence/risk context, not automatic stable-prediction promotion.
