# 2026 historical recovery evidence

This directory is the isolated, post-event recovery output for the 39 processor snapshots identified as absent by the 17 October audit.

The GitHub review payload is `F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz`. Extract it at the repository root to restore the exact `audit/2026-10-17/recovery/processor_outputs/` tree described below. Its SHA-256 and Git blob are recorded in `F1_2026_HISTORICAL_RECOVERY_VALIDATION.json`.

- `processor_outputs/latest/` contains the final per-session raw rows, validation reports and source-readiness manifests.
- `processor_outputs/history/` preserves the timestamped processor writes, including the pre-repair grid HOLD snapshots and their later bounded grid-source resolutions.
- `processor_outputs/historical_recovery_checkpoint.json` is the terminal checkpoint: 39 attempted, 39 processed, zero failed.
- `processor_outputs/batch_receipts/` and the checkpoint's `batches` array retain request URL, endpoint, session key, HTTP status, response byte count, SHA-256 and observation time.

All provider observations are post-event. Nothing here proves pre-race availability, authorizes a forecast, authenticates an FIA final grid, activates DR-002 or modifies the stable engine. Issue #309 was not changed or dispatched.
