# Source-Readiness to Workbook/KPI Flow

```text
Session ends
  |
Watcher detects source/timing readiness
  |
Session Data Processor pulls OpenF1/FastF1/FIA/public data
  |
Session validation:
  - session_key
  - round
  - driver IDs
  - timestamps
  - lap counts
  - missing columns
  - duplicates
  - anomalies
  |
Source classified:
  clean / partial / late / conflicting / needs_manual_review
  |
Processor writes:
  - latest_manifest.json
  - data_readiness.json
  - combined_source_manifest.json
  - workbook_kpi_readiness.json/csv
  - sandbox_workbook_update_plan.json
  - forecast_bundle_ledger_snapshot.json
  |
Workbook/KPI Refresh Applier:
  - reads plan
  - creates dated sandbox workbook artifact
  - writes refresh manifest
  - writes latest + history snapshots
  - blocks stable/canonical overwrite
  |
Race Predictions / Fantasy readiness can read refreshed artifacts
```

## Notification discipline

Notify only if readiness materially improves, the active session changes, or forecast/fantasy readiness state changes.
