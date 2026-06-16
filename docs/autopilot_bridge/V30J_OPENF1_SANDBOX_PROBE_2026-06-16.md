# V30J OpenF1 Sandbox Probe

This PR adds an explicit OpenF1 sandbox probe for the Session Data Processor Loop.

## Scope

- Consumes the V30H OpenF1 request manifest.
- Supports three modes:
  - `dry_run`: validates the request manifest without network access.
  - `fixture`: validates fixture fetch results for repeatable tests.
  - `sandbox_live`: performs OpenF1 requests only when `--allow-live true` is also provided.
- Keeps downstream consumers blocked unless required OpenF1 rows are validated.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook mutation remains disabled.
- Notification sending remains disabled.

## V30I Repair

This PR also repairs a latent V30I live-validation typo in the required-request loop.

The typo did not affect dry-run validation, but would have affected future live-fetch validation. Fixing it before Control Room wiring is required.
