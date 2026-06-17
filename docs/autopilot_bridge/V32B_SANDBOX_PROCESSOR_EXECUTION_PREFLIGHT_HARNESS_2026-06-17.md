# V32B Sandbox Processor Execution Preflight Harness

This patch adds a non-activating pre-execution test harness for the Session Data Processor Loop.

## Purpose

V32B verifies that the v31J activation review packet and v32A authorization preflight are present, ready, and still governance-safe before any controlled sandbox execution patch is prepared.

## What It Does

- Reads the activation authorization preflight.
- Reads the activation review packet.
- Optionally reads upstream readiness artifacts.
- Verifies required evidence is present and ready-like.
- Rejects `--execute true`.
- Rejects `--activate true`.
- Verifies downstream consumer gates remain closed.
- Writes a machine-readable preflight status JSON.

## What It Does Not Do

- Does not execute the processor.
- Does not activate production automation.
- Does not activate the forecast gate.
- Does not promote model logic.
- Does not write to the canonical workbook.
- Does not write a Forecast Bundle Ledger snapshot.
- Does not refresh Race Predictions.
- Does not refresh Fantasy outputs.
- Does not send notifications.

## Next Step

If V32B passes after review, the next layer can be V32C: a separately authorized controlled sandbox processor execution patch.
