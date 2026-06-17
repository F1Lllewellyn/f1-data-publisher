# V33B-R3 End-to-End Dry-Run Rehearsal

PR-only recovery from v33B-R2. R2 failed at the GitHub receiver's requested-tests stage because the payload used a raw shell command in `tests[]`. 1B's repeated successful v32 process used `tests: []`; validation belonged in the bridge/receiver, the merge gate, and the script's own dry-run safety logic.

R3 therefore preserves the v33B R2 write-guard fix, uses `tests: []`, keeps files under the successful merge-gate prefixes `scripts/autopilot/` and `docs/autopilot_bridge/`, and moves the policy file to `scripts/autopilot/` to match the v32/v33A pattern.

## What It Does

- Verifies v32N and v33A evidence-chain readiness in repo mode.
- Supports fixture mode for local validation only.
- Confirms all safety flags remain false.
- Plans the Session Data Processor Loop stages without live data fetches or production writes.
- Blocks unsafe output paths before writing any rehearsal artifact.

## What It Does Not Do

- Does not activate production automation.
- Does not fetch live data.
- Does not write or overwrite the canonical workbook.
- Does not write the production Forecast Bundle Ledger.
- Does not refresh Race Predictions or Fantasy outputs.
- Does not send notifications.
- Does not promote model logic.

## Required Process

Submit through the existing Gmail -> Pipedream -> GitHub PR-only bridge with `tests: []`. Review the PR, then use a separate approved merge-gate command only after bridge/GitHub evidence is clean.
