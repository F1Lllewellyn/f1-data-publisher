# Workbook/KPI Refresh Applier Design

## Problem

The Session Data Processor Loop now ingests session data and writes sandbox update plans, but the canonical workbook must not be modified directly. The missing downstream piece is a governed applier that converts those plans into a dated workbook/KPI readiness artifact.

## Design

The applier is a bridge layer:

```text
Session Processor Artifacts
  -> Governance Preflight
  -> Sandbox Workbook/KPI Artifact Builder
  -> Manifest + Checksum Writer
  -> Forecast Bundle Ledger Snapshot Link
  -> Latest + History Publication
```

## Inputs

- latest/session_data_processor/sandbox_workbook_update_plan.json
- latest/session_data_processor/workbook_kpi_readiness.json
- latest/session_data_processor/workbook_kpi_readiness.csv
- latest/session_data_processor/forecast_bundle_ledger_snapshot.json
- latest/latest_manifest.json
- latest/data_readiness.json
- latest/combined_source_manifest.json

## Outputs

- latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json
- latest/workbook_kpi_refresh_applier/refreshed_workbook_kpi_readiness.csv
- latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_Refresh_*.xlsx
- latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_report.md
- history/workbook_kpi_refresh_applier/<run_id>/*

## Workbook Strategy

The applier can either:

1. Copy a source workbook and append sandbox audit/readiness sheets, or
2. Create a lightweight sandbox workbook artifact if no source workbook is available.

It never overwrites the canonical workbook.

## Gates

- Data-First Gate: require Session Processor artifacts or mark missing/needs review.
- Stable Separation Gate: block stable output changes.
- Canonical Workbook Gate: block canonical overwrite.
- Forecast Bundle Discipline Gate: link to Forecast Bundle Ledger snapshot.
- Promotion Gate: blocked.
