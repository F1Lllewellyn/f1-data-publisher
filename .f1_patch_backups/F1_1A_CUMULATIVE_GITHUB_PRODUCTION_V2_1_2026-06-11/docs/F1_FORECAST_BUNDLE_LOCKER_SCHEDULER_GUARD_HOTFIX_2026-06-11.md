# F1 Forecast Bundle Locker v1 — Scheduler Guard Hotfix

Date: 2026-06-11

## Verdict

Pass with warnings.

This hotfix keeps the forecast-bundle locker available for manual gate locking while making scheduled runs safer.

## What changed

Scheduled runs now require actual forecast source rows before creating or committing any `latest/forecast_bundles` or `history/forecast_bundles` outputs.

If no forecast rows are detected, the workflow exits cleanly and writes only a runtime guard report under:

```text
_runtime/forecast_bundle_locker_guard/
```

The commit step will have no `latest/forecast_bundles` or `history/forecast_bundles` changes to commit.

## Scheduled source detection

The guard scans these source roots:

```text
latest/forecasts/<event_id>/<gate>/<lane>/forecast_rows.csv
latest/forecast_outputs/<event_id>/<gate>/<lane>/forecast_rows.csv
latest/method_e_control_room/forecasts/<event_id>/<gate>/<lane>.csv
```

It deliberately excludes existing forecast bundles as scheduled sources:

```text
latest/forecast_bundles/**
```

That prevents old or placeholder bundles from being re-locked repeatedly on a timer.

## Manual behavior

Manual `workflow_dispatch` behavior remains available. Manual runs can still create structural bundles and mark missing sources as `missing_forecast_source`, because manual gate locking is deliberate operator action.

## Guardrails

- Canonical workbook unchanged.
- Stable engine unchanged.
- No promotion logic changed.
- Missing forecast sources still block validation.
- Scheduled placeholder churn is blocked.

## Recommended first check

After installation, run one manual workflow with a known event/gate only if you want to verify manual behavior. Scheduled no-source behavior does not need manual testing; it will exit cleanly when no forecast sources exist.
