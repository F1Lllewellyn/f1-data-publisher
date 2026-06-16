# V31 Bridge Hygiene - Runtime Status Ledger

This PR changes the bridge status ledger writer so generated status artifacts are runtime-only by default.

## Problem

`health/autopilot_last_status.json` and `logs/autopilot_bridge/dispatch_*.json` change on every bridge run. When those generated files are committed into normal feature PRs, independent bridge patches can conflict even when their actual code changes do not overlap.

## Change

- `scripts/autopilot/write_status_ledger.mjs` now writes `_runtime/autopilot_bridge/status_ledger.json` by default.
- Tracked status files are only written when explicitly requested with `--write-tracked-status true` or `F1_BRIDGE_WRITE_TRACKED_STATUS=true`.
- Legacy positional invocation remains supported for the catchall receiver.
- CLI flag invocation remains supported for the patch receiver.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.

## Expected Result

Future feature PRs should stop carrying generated health/log status changes unless a command explicitly requests tracked status output.
