# V32F Controlled Sandbox Workbook Reflection Execution

This patch adds controlled sandbox workbook reflection execution for the Session Data Processor Loop.

## Purpose

V32F is allowed to write a sandbox-only workbook reflection artifact after V32E passes. It does not write to the canonical workbook.

## What It Can Do

- Read the V32E sandbox workbook reflection preflight.
- Read the V31D sandbox KPI reflection contract.
- Run only with `--mode sandbox_reflection --execute true --operator-approval true --allow-sandbox-workbook-write true`.
- Write a sandbox-only reflection artifact.

## What It Cannot Do

- Cannot write to the canonical workbook.
- Cannot write a Forecast Bundle Ledger snapshot.
- Cannot refresh Race Predictions.
- Cannot refresh Fantasy outputs.
- Cannot send notifications.
- Cannot activate production automation.
- Cannot activate the forecast gate.
- Cannot promote model logic.

## Next Step

After V32F is merged and sandbox reflection evidence is available, the next layer is V32G: sandbox workbook reflection evidence review.
