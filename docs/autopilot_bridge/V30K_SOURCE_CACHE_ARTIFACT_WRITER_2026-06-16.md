# V30K Source Cache Artifact Writer

This PR adds the sandbox-only source cache artifact writer for the Session Data Processor Loop.

## Scope

- Reads the v30J OpenF1 sandbox probe status.
- Writes a durable cache artifact only when required OpenF1 rows are present and validated.
- Writes a health/log status for manifest-only or data-ready runs.
- Keeps downstream workbook, forecast, race prediction, fantasy, and notification consumers closed.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook writes are not enabled.
- Notification sending is not enabled.

## Follow-up

After review, v30L can wire this cache status into a Control Room summary dry-run. v30L must still avoid workbook mutation and forecast activation until source-cache behavior is proven.
