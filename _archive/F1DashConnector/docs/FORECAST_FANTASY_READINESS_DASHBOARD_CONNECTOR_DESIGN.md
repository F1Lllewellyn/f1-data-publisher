# Forecast/Fantasy Readiness Dashboard Connector Design

## Goal

Make Race Predictions and Fantasy Predictions chats automatically aware of the latest session state by publishing small, source-backed readiness dashboards from the existing Session Data Processor, Workbook/KPI Refresh Applier, and Auto-Repair outputs.

## Flow

```text
Session Data Processor output
-> Workbook/KPI Refresh Applier sandbox workbook
-> Auto-Repair source-backed status
-> Forecast/Fantasy Readiness Dashboard Connector
-> Race Predictions brief + Fantasy brief
-> material-change-only commit
```

## Source discovery

The connector reads the latest available artifacts from:

- latest/workbook_kpi_refresh_applier/
- latest/session_data_processor/**/
- latest/autorepair/session_workbook_recovery/
- latest/latest_manifest.json
- latest/data_readiness.json
- latest/combined_source_manifest.json
- latest/forecast_bundles/ or history/forecast_bundles/

It understands source status aliases used by earlier layers:

- source_status
- overall_status
- overall_classification
- classification
- status

## Commit discipline

Allowed source states:

- clean
- partial
- late
- conflicting
- needs_manual_review

Blocked source states:

- missing
- unknown
- placeholder
- scheduled_not_populated
- empty

Dashboard outputs commit only if the state materially changes.

## Chat behavior

Race Predictions receives:

- latest event/session
- source readiness
- sandbox workbook path
- forecast bundle ledger path
- confidence/risk guidance
- stable overwrite block

Fantasy receives:

- latest event/session
- source readiness
- transfer/chip readiness context
- value/watch/avoid risk context
- stable/promotion block

## Governance

This layer cannot directly alter official predictions. It only publishes readiness context.
