# Workbook/KPI Update Strategy

The processor must not overwrite the canonical workbook.

## Safe update options

1. Write JSON/CSV readiness artifacts for the workbook/KPI layer.
2. Create a sandbox workbook copy only if explicitly enabled.
3. Add a `SessionData_Readiness` tab to the sandbox copy only.
4. Never alter the canonical workbook path.
5. Never alter `Engine_2026-06-07_STABLE`.

## Output artifacts

- `workbook_kpi_readiness.json`
- `workbook_kpi_readiness.csv`
- `sandbox_workbook_update_plan.json`
- optional: `sandbox/workbooks/<event>_<session>_SESSION_DATA_PROCESSOR_SANDBOX.xlsx`

## Readiness fields

- event_id
- session_key
- session_name
- gate
- openf1_source_status
- fastf1_source_status
- FIA_source_status
- lap_rows
- driver_count
- weather_rows
- race_control_rows
- missing_required_columns
- duplicate_count
- anomaly_count
- forecast_state_changed
- fantasy_readiness_changed
- manual_review_required
