# V31 Session Processor Activation Protocol Design

This patch adds a dry-run activation protocol design for the Session Data Processor Loop.

## Purpose

V31 defines the evidence and manual approval gates required before any sandbox-live source pull, workbook reflection, Forecast Bundle Ledger snapshot, Race Predictions readiness refresh, Fantasy readiness refresh, or material notification preview can be considered.

## What It Does

- Reads optional evidence snapshots from the v30 dashboard, replay, source, and threshold layers.
- Validates required evidence presence.
- Blocks activation if any supplied evidence is blocking, failed, or governance-invalid.
- Records the manual approval scopes that would be required for future controlled activation.
- Emits a machine-readable protocol status.

## What It Does Not Do

- Does not activate production automation.
- Does not fetch live data.
- Does not write to the canonical workbook.
- Does not activate the forecast gate.
- Does not promote model logic.
- Does not refresh Race Predictions or Fantasy outputs.
- Does not send notifications.

## Required Manual Approval Scopes

- Sandbox live source pull.
- Sandbox workbook reflection.
- Forecast Bundle Ledger snapshot write.
- Race Predictions readiness refresh.
- Fantasy readiness refresh.
- Material notification preview.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine remains untouched.
- Canonical workbook remains untouched.
- Notifications remain disabled.

## Next Step

After V31 is merged and reviewed, the next work should be a controlled sandbox-live activation request that targets only one narrow path at a time, starting with source pull evidence collection.
