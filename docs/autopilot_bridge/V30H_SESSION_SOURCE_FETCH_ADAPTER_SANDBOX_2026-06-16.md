# V30H Session Source Fetch Adapter Sandbox

This PR adds the sandbox source-fetch adapter for the Session Data Processor Loop.

## Scope

- Consumes the V30G source-fetch contract.
- Emits a concrete request manifest for OpenF1 session data.
- Emits placeholder/cross-check manifests for FastF1 cache, FIA public documents, and Formula 1 public event context.
- Keeps network fetching disabled by default.
- Supports a future explicit sandbox-live mode, but the default policy leaves sandbox live fetch disabled.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook mutation remains disabled.
- Notification sending remains disabled.

## Role In The Loop

V30G defined what sources are required.

V30H converts that source contract into executable fetch requests and cache metadata without fetching by default.

Next follow-up should validate returned source artifacts before any forecast or workbook refresh logic is wired.
