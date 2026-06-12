# F1 Forecast Gate Source Writer v1 Patch

This patch creates the missing upstream bridge needed by the Forecast Bundle Locker.

It writes normalized forecast rows into `latest/forecasts/<event_id>/<gate>/<lane>/forecast_rows.csv` only when actual forecast source rows already exist in approved source locations.

It will not fabricate blind-valid history and will not silently overwrite stable exact P1-P20 outputs.

After running this workflow, run `F1 Forecast Bundle Locker v1` to create immutable gate-locked bundles.
