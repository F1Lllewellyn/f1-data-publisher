# v31I Sandbox-Live Rehearsal with Evidence Replay and Operator Review

This patch adds the v31I dry-run sandbox-live rehearsal operator-review layer for the Session Data Processor Loop.

## Purpose

v31I consumes source evidence, source review, and the end-to-end rehearsal packet, then produces one operator-review status for a controlled sandbox-live rehearsal. It is evidence replay and review only.

## What It Does

- Reads v31A-style source evidence.
- Reads v31B-style source evidence review.
- Reads v31H-style end-to-end rehearsal packet.
- Optionally reads the v31 activation protocol.
- Verifies required inputs are present and ready-like.
- Detects blocked, failed, stale, or governance-violating upstream inputs.
- Writes a machine-readable rehearsal status JSON.
- Writes a Markdown operator review packet.

## What It Does Not Do

- Does not fetch live data.
- Does not write the canonical workbook.
- Does not write a Forecast Bundle Ledger snapshot.
- Does not refresh Race Predictions.
- Does not refresh Fantasy outputs.
- Does not send notifications.
- Does not activate production automation.
- Does not promote model logic.

## Governance

Production automation remains OFF. Forecast gate remains OFF. Model promotion remains false. Stable engine and canonical workbook remain protected. All consumer gates remain disabled.

## Next Step

After v31I is merged and reviewed, the next planned layer is v31J: activation review packet, only if all gates pass.
