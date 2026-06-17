# v32G Sandbox Workbook Reflection Evidence Review Gate

This patch adds the v32G dry-run evidence review gate for the sandbox workbook reflection step in the Session Data Processor Loop.

## Purpose

v32G consumes v32F sandbox workbook reflection evidence and v32E reflection preflight evidence, then produces a machine-readable and operator-readable review status.

## What It Does

- Verifies v32F evidence shows a sandbox-only reflection artifact was produced.
- Verifies v32E preflight remains ready.
- Rejects ready-but-not-written evidence.
- Rejects canonical workbook writes or overwrite signals.
- Rejects production automation, forecast gate, live fetch, model promotion, Race/Fantasy refresh, and notification-send signals.
- Writes a JSON review status and optional Markdown packet.

## What It Does Not Do

- Does not write the canonical workbook.
- Does not write or update a sandbox workbook.
- Does not write a Forecast Bundle Ledger snapshot.
- Does not refresh Race Predictions or Fantasy outputs.
- Does not send notifications.
- Does not activate production automation.
- Does not promote model logic.

## Next Step

After v32G is merged and review evidence is clean, the next planned layer is v32H: Forecast Bundle Ledger write preflight.
