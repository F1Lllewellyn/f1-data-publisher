# v31H End-to-End Rehearsal Packet

This patch adds the dry-run end-to-end rehearsal packet for the Session Data Processor Loop.

## Purpose

v31H composes the current source-evidence, downstream consumer, sandbox KPI reflection, Forecast Bundle Ledger, Race/Fantasy readiness, and notification-preview contracts into one operator-facing rehearsal status.

## What It Does

- Reads upstream contract/review status JSON files.
- Verifies required gates are present and ready-like.
- Detects blocked, failed, stale, or missing required inputs.
- Detects governance violations such as live fetch, production automation, open consumer gates, model promotion, stable-engine modification, canonical-workbook overwrite, or notification sending.
- Writes a machine-readable rehearsal status JSON.
- Writes an optional Markdown operator packet.

## What It Does Not Do

- Does not fetch live data.
- Does not write the canonical workbook.
- Does not write a Forecast Bundle Ledger snapshot.
- Does not refresh Race Predictions.
- Does not refresh Fantasy outputs.
- Does not send notifications.
- Does not activate production automation.
- Does not promote model logic.

## Next Step

After v31H is merged and reviewed, the next planned layer is v31I: sandbox-live rehearsal with evidence replay and operator review.
