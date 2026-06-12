# Session Data Processor Loop Design

Branch/package: `Engine_2026-06-11_SANDBOX_SessionDataProcessorLoop`

## Diagnosis of the operational gap

The active race-weekend automations were functioning as readiness/watch systems, not as a true processor loop. The logs show source refresh and forecast bundle production for a detected Spain/Barcelona pre-weekend gate, but not a session-level FP1/FP2 data processor.

Observed behavior from the available logs:

1. The watcher/source-readiness automations ran.
2. The full automation detected `2026 Spain / Barcelona-Catalunya` and produced pre-weekend forecast rows/bundles.
3. The pipeline did not run a session-specific processor for FP1/FP2.
4. The logs did not show updates to `latest/latest_manifest.json`, `latest/data_readiness.json`, or `combined_source_manifest` for FP1/FP2 workbook/KPI readiness.
5. The existing forecast automation writes forecast-bundle artifacts; it does not update local workbook/KPI state.

## Required new loop

```text
Session end detector
-> Session data processor
-> Source artifact writer
-> Session validation/classification
-> Workbook/KPI readiness updater/sandbox plan
-> Forecast Bundle Ledger snapshot
-> Race/Fantasy readiness refresh
-> Notification gate
```

## Core processor responsibilities

- Detect most recent completed session or selected session.
- Pull OpenF1 session-scoped data.
- Optionally run FastF1 capture/enrichment where available.
- Accept FIA/public/manual artifacts as side-loaded source files.
- Validate source rows and schema.
- Classify data source readiness.
- Write latest + history artifacts.
- Refresh manifest files consumed by predictions/fantasy chats.
- Never overwrite stable predictions or canonical workbook.

## Source classification

| Class | Meaning | Action |
|---|---|---|
| clean | Complete enough for downstream use | refresh readiness and ledger |
| partial | Some useful data but incomplete | refresh with warning, do not overstate |
| late | Expected endpoint is not populated yet | retry on next cycle |
| conflicting | IDs/timestamps/round/session mismatch | manual review |
| needs_manual_review | anomalies cannot be resolved automatically | block forecast-state upgrade |

## Production-readiness status

This package is a sandbox processor scaffold plus GitHub workflow integration. It should be activated for FP3/qualifying/race only after Safe Test passes and the pending No-Code Commit Ignore Fix is installed in the repo.
