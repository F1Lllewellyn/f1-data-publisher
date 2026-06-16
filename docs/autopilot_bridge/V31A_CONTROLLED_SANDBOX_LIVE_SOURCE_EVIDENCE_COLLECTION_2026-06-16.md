# V31A Controlled Sandbox-Live Source Evidence Collection

This patch adds a controlled source-pull evidence collector for the Session Data Processor Loop.

## Purpose

V31A creates the first narrow source-evidence collection layer after the v31 activation protocol. It is designed to collect sandbox-live evidence only after explicit manual approval and explicit CLI flags.

## Default Behavior

By default, V31A runs in dry-run mode:

- No live fetch.
- No workbook write.
- No Forecast Bundle Ledger write.
- No Race Predictions refresh.
- No Fantasy refresh.
- No notification sending.
- No production automation.
- No model promotion.

## Controlled Sandbox-Live Behavior

The script only attempts live source evidence collection when both conditions are true:

- `--mode sandbox_live`
- `--allow-live true`

The policy also keeps `live_fetch_allowed` false by default. A future explicit approval can change policy or invoke a separate approved sandbox-live command.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine remains untouched.
- Canonical workbook remains untouched.
- All downstream consumer gates remain closed.

## Next Step

After V31A is merged and reviewed, the next safe step is an approved sandbox-live evidence run against one current event/session, followed by operator review before any downstream consumer wiring.
