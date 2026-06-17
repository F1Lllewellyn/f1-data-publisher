# v32M Material-Change Notification Preflight

This patch adds a dry-run preflight gate for material-change notification readiness after the Fantasy Predictions readiness preflight.

## Purpose

v32M determines whether the completed readiness chain is material enough to prepare an operator notification preview. It does not send notifications.

## What It Does

- Reads v32L Fantasy Predictions readiness refresh preflight status.
- Requires `fantasy_predictions_readiness_refresh_preflight_ready`.
- Requires `race_predictions_preflight_verified_no_fantasy_refresh_performed`.
- Marks the completed preflight chain as material-change-ready for preview.
- Keeps notification sending disabled.
- Rejects production ledger writes, canonical workbook writes, live fetches, activation, notifications, Race Predictions refresh, Fantasy refresh, and open consumer gates.
- Writes a machine-readable material-change notification preflight status.

## What It Does Not Do

- Does not send notifications.
- Does not refresh Fantasy outputs.
- Does not refresh Race Predictions.
- Does not write the Forecast Bundle Ledger.
- Does not write or overwrite the canonical workbook.
- Does not activate production automation.
- Does not promote model logic.

## Governance

Production automation remains OFF. Forecast gate remains OFF. Model promotion remains false. Stable engine and canonical workbook remain protected.

## Next Step

After v32M is merged and clean, the next planned layer is v32N: operator handoff and readiness packet finalizer.
