# Forecast Bundle Ledger Integration

The Session Data Processor writes a ledger snapshot for each session processor run.

## Purpose

The ledger snapshot tells the forecast-bundle system whether the source-readiness state materially changed after a session.

## Snapshot output

```text
latest/forecast_bundle_ledger/session_data_processor/<event_id>/<session_slug>/ledger_snapshot.json
history/forecast_bundle_ledger/session_data_processor/<event_id>/<run_id>/<session_slug>/ledger_snapshot.json
```

## Rules

- If source readiness improves materially, mark `forecast_state_changed: true`.
- If source readiness remains stale/late, mark `forecast_state_changed: false`.
- If source conflict exists, mark `needs_manual_review: true` and block forecast-state upgrades.
- Do not overwrite stable prediction order.
- Do not create forecast bundles directly from incomplete session data unless the forecast-bundle system explicitly validates them.
