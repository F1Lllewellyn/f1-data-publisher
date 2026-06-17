# V32C Controlled Sandbox Processor Execution

This patch adds a controlled sandbox execution runner for the Session Data Processor Loop.

## Purpose

V32C is the first execution-capable layer after the v32B preflight, but it is limited to sandbox health/log artifacts only.

## What It Can Do

- Read the v32B execution preflight.
- Read the v31J activation review packet.
- Optionally read source evidence and source review artifacts.
- Run only when `--mode sandbox_execution --execute true --operator-approval true` is provided.
- Emit a sandbox health/log status artifact.

## What It Cannot Do

- It cannot activate production automation.
- It cannot perform live fetch.
- It cannot write to the canonical workbook.
- It cannot write a Forecast Bundle Ledger snapshot.
- It cannot refresh Race Predictions.
- It cannot refresh Fantasy outputs.
- It cannot send notifications.
- It cannot promote model logic.

## Next Step

After V32C is merged and the sandbox execution status is reviewed, the next layer is V32D: sandbox execution evidence review gate.
