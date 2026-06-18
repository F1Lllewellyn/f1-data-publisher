# v33C Controlled Sandbox-Live Source Pull

v33C is Roadmap Step 3 of 10: the first controlled sandbox-live source pull for the Session Data Processor Loop.

## Scope

- Builds an OpenF1 request manifest after a session-end gate.
- Supports `dry_run`, `fixture`, and explicit `sandbox_live` modes.
- Performs network fetches only when all of these are true:
  - `--mode sandbox_live`
  - `--allow-live true`
  - `--operator-approval APPROVE_V33C_CONTROLLED_SANDBOX_LIVE_SOURCE_PULL`
  - policy allows sandbox-live fetch.
- Writes sandbox/health source evidence only.
- Produces enough source evidence metadata for v33D sandbox-live source quality review.

## Required OpenF1 sources

- `sessions`
- `drivers`
- `laps`
- `stints`

## Optional OpenF1 sources

- `position`
- `intervals`
- `race_control`
- `weather`

Optional-source failures degrade the source evidence instead of blocking it. Required-source failures block v33C.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook writes remain disabled.
- Forecast Bundle Ledger production writes remain disabled.
- Race Predictions refresh remains disabled.
- Fantasy refresh remains disabled.
- Notification sending remains disabled.

## Output

v33C writes a health status JSON. When source evidence is available in fixture or approved sandbox-live mode, it also writes a sandbox source evidence artifact under `sandbox/session_sources/v33c/`.

## Next step

If v33C produces `SANDBOX_SOURCE_EVIDENCE_READY` or `SANDBOX_SOURCE_EVIDENCE_DEGRADED`, the next roadmap step is v33D: sandbox-live source quality review.
