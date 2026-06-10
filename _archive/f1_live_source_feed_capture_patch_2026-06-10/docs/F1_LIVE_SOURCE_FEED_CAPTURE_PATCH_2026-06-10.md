# F1 Live Source Feed Capture Layer v0 Experimental

## Purpose

This patch adds an experimental GitHub-led live source-feed capture layer for the F1 Prediction Engine.

It is designed to capture the F1 live timing source feed during race-weekend sessions, preserve the raw evidence in GitHub, and support post-session replay/reconciliation inside the Method E proof-loop architecture.

## What it is

A source-feed recorder and archive layer.

It records FastF1 live timing SignalR packets into a raw timing file, creates a lightweight packet index, writes manifests/readiness files, uploads a GitHub Actions artifact, and commits reusable `latest/` and `history/` outputs.

## What it is not

It is not a real-time prediction engine.
It does not update the stable forecast.
It does not touch the canonical workbook.
It does not promote experimental signals.
It does not replace OpenF1 lightweight source closure.

## Installed files

- `.github/workflows/f1-live-source-feed-capture-experimental.yml`
- `scripts/live_capture/run_live_source_feed_capture.py`
- `configs/live_capture/live_source_feed_capture_policy.json`
- `docs/F1_LIVE_SOURCE_FEED_CAPTURE_PATCH_2026-06-10.md`
- `CURRENT_CANONICAL_FILES_LIVE_SOURCE_FEED_CAPTURE_2026-06-10.md`
- `LIVE_SOURCE_FEED_CAPTURE_PATCH_MANIFEST.csv`

## Expected outputs

- `latest/live_source_feed_capture/live_timing_raw.txt`
- `latest/live_source_feed_capture/live_source_feed_packet_index.csv`
- `latest/live_source_feed_capture/live_source_feed_capture_manifest.json`
- `latest/live_source_feed_capture/live_source_feed_capture_readiness.json`
- `latest/live_source_feed_capture/live_source_feed_capture_report.md`
- `history/live_source_feed_capture/<timestamp_session>/...`

## Operating guidance

Start with a short manual test using workflow dispatch and a 2-5 minute duration.

Only after that test passes should scheduled session-window capture be treated as usable.

Use GitHub as orchestrator and archive. Treat source-feed capture as experimental evidence until reconciled against post-session source closure.
