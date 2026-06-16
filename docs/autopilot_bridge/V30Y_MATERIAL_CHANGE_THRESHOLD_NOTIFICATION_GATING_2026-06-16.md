# V30Y Material-Change Threshold and Notification Gating

This patch adds a dry-run material-change threshold gate for the Session Data Processor Loop.

## Purpose

V30Y compares current session-loop readiness evidence with a previous snapshot and determines whether the difference is material enough to create a notification preview.

## What It Does

- Classifies readiness status transitions.
- Detects blocking-source count changes.
- Detects failed-case count changes.
- Detects source row-count deltas above configured thresholds.
- Detects data-ready case changes.
- Treats any live-fetch evidence as manual-review material.
- Writes a machine-readable threshold-gate status.

## What It Does Not Do

- Does not send notifications.
- Does not activate production automation.
- Does not activate the forecast gate.
- Does not promote model logic.
- Does not write to the canonical workbook.
- Does not refresh Race Predictions or Fantasy outputs.

## Next Step

After V30Y is merged, the next safe layer is V30Z: Control Room operator dashboard packet.
