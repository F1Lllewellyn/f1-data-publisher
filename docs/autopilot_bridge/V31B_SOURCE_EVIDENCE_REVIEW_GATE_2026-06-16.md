# V31B Source Evidence Review Gate

This patch adds a dry-run review gate for v31A controlled sandbox-live source evidence.

## Purpose

V31B reviews source-evidence artifacts before downstream consumers are opened. It classifies evidence as ready, degraded, blocked, or contract-ready.

## Scope

- Reads optional v31A source-evidence status.
- Confirms live evidence is sandbox-live only.
- Confirms production automation, forecast gate, model promotion, workbook writes, prediction refresh, fantasy refresh, and notification sending remain disabled.
- Writes a machine-readable review status.

## Non-Scope

- Does not perform live network fetches.
- Does not write to the canonical workbook.
- Does not modify the stable engine.
- Does not write forecast bundles.
- Does not refresh Race Predictions or Fantasy outputs.
- Does not send notifications.

## Next Step

If evidence is review-ready, the next layer is downstream consumer contract wiring in dry-run mode only.
