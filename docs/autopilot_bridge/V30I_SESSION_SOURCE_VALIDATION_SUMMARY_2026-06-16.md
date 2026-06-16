# V30I Session Source Validation Summary

This PR adds the source validation summary layer for the Session Data Processor Loop.

## Scope

- Consumes the V30H source-fetch adapter output.
- Validates required request coverage.
- Validates governance flags.
- Validates fetch results if sandbox-live results are present.
- Emits `contract_ready`, `data_ready`, or `blocked`.
- Keeps workbook refresh, forecast refresh, Race Predictions refresh, and Fantasy readiness refresh blocked unless live source artifacts are validated.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook mutation remains disabled.
- Notification sending remains disabled.

## Role In The Loop

V30H produces a source request manifest.

V30I validates whether that manifest or later live source artifacts are safe for downstream consumers.

Dry-run manifest-only output is allowed to become `contract_ready`, but not `data_ready`.
