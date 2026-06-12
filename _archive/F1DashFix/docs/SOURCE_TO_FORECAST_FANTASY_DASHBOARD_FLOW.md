# Source to Forecast/Fantasy Dashboard Flow

```text
1. Integrated session loop runs
2. Session data processor writes latest/session_data_processor/<event>/<session>/...
3. Workbook/KPI Refresh Applier writes latest/workbook_kpi_refresh_applier/...
4. Auto-Repair confirms source-backed status
5. Dashboard connector discovers latest source-backed state
6. Connector writes Race Predictions and Fantasy readiness state files
7. Connector commits only if material state changed
8. Chats consume latest/chat_context/*.md and latest/readiness_dashboards/*.json
```

## Material change examples

- new session key
- session status changes from missing to needs_manual_review/clean
- new sandbox workbook path
- data_readiness.json hash changes
- forecast bundle ledger snapshot changes

## Notification rule

Notify/commit only on material state change. Otherwise no action.
