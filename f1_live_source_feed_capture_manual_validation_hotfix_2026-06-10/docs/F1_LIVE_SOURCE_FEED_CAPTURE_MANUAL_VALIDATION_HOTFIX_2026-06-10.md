# F1 Live Source Feed Capture — Manual Validation / Source-Feed Handshake Hotfix (2026-06-10)

## Purpose

This hotfix fixes the validation behaviour discovered after the FastF1 Python 3.9 compatibility patch.

The previous run showed that FastF1 imported successfully, but the live source-feed connection immediately raised a `JSONDecodeError`. That is most likely a live source-feed handshake / no-active-stream condition during a manual test outside an active F1 timing window.

## What changed

1. Adds a `manual_validation_mode` workflow input:
   - `infrastructure_only` — validates GitHub workflow plumbing without attempting live source-feed capture.
   - `force_source_feed` — attempts FastF1 SignalR capture and records whether packets are actually written.
2. Classifies `JSONDecodeError` during source-feed start as `source_feed_handshake_unavailable` with a clear diagnostic hint.
3. Treats manual outside-session validation as `Pass with warnings`, not a false live-capture failure.
4. Keeps active scheduled capture strict: if a real capture window is active and the feed handshake fails, it is still a failure.

## What this does not do

- Does not touch the canonical workbook.
- Does not change the stable engine.
- Does not promote live snapshot signals.
- Does not replace OpenF1 source closure.

## Recommended manual test

After install, run the workflow manually with:

- `capture_mode`: manual
- `manual_validation_mode`: infrastructure_only
- `duration_minutes`: 2
- `session_label`: manual_test
- `commit_outputs`: true

Expected result: Pass with warnings, with manifests/artifacts committed.

During an actual live session window, use:

- `manual_validation_mode`: force_source_feed

Expected result: Pass if raw bytes and packet lines are greater than zero.
