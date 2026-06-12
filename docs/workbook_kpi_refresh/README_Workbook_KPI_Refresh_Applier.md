# Engine_2026-06-11_SANDBOX_WorkbookKPIRefreshApplier

## Purpose

This sandbox layer converts Session Data Processor outputs into dated workbook/KPI refresh artifacts without touching the canonical workbook or the stable engine.

It is the governed downstream step after:

```text
session ingest -> validation -> readiness artifacts -> workbook/KPI update plan
```

It produces:

```text
sandbox workbook refresh artifact
workbook_kpi_refresh_manifest.json
refreshed_workbook_kpi_readiness.csv
workbook_kpi_refresh_report.md
history snapshots
latest snapshots
```

## Governance

- Canonical workbook overwrite: blocked
- Engine_2026-06-07_STABLE modification: blocked
- Stable exact P1-P20 overwrite: blocked
- Promotion: blocked
- Delete/cleanup authority: blocked
- Output mode: dated sandbox artifacts only

## No-code workflows

After install and push, GitHub Actions will show:

1. `F1 Workbook KPI Refresh - Safe Test Button`
2. `F1 Workbook KPI Refresh - Run Now Button`
3. `F1 Workbook KPI Refresh - Scheduled Processor`

Run the Safe Test Button first.

## Expected flow

```text
Session Data Processor Run Now
-> sandbox_workbook_update_plan.json
-> workbook_kpi_readiness.json/csv
-> forecast_bundle_ledger_snapshot.json
-> Workbook/KPI Refresh Applier
-> dated sandbox workbook/KPI artifact
-> latest manifest + history snapshot
```

## Promotion status

NOT PROMOTED. This is infrastructure validation only.
