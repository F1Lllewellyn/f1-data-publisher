# F1 Actual Forecast Producer Source Discovery Hotfix - 2026-06-12

## Executive summary

Verdict: Pass with warnings.

This hotfix updates the Actual Forecast Producer so it recognizes the current OpenF1 Lightweight Source Closure output layout. The source-closure publisher writes OpenF1 lane CSVs under `latest/openf1_lightweight_source_closure/data/`, while the original forecast producer checked the root source-closure folder first.

## What changed

- Adds `latest/openf1_lightweight_source_closure/data/` as the primary source folder.
- Adds equivalent `/data` variants for related source-closure locations.
- Adds recursive fallback search under known `latest/` and `history/` source-closure roots.
- Preserves no-source guardrails.
- Does not fabricate forecast rows if no usable driver or starting-grid source rows exist.
- Does not touch stable engine logic, workbook files, prediction outputs, or promotion status.

## Expected validation

After install, run `F1 Actual Forecast Producer v1` with:

```text
event_id: manual_forecast_producer_validation
race_name: Manual Forecast Producer Validation
gate: all
lane: all
strict_source: false
commit_outputs: true
```

Expected result if OpenF1 source closure data files exist:

```text
forecast_rows_created: greater than 0
gate_lane_files_created: 15
```

If source closure data files do not exist yet, the workflow should still exit safely with no forecast rows created.
