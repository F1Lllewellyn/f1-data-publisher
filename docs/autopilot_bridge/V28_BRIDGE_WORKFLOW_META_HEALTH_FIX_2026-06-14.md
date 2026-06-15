# V28A 1C Bridge Workflow Meta-Health Fix

## Purpose

Repair the scheduled Control Room failure caused by 1C Gmail Autopilot Bridge workflow meta-health failures.

The hard blockers were in:

- `.github/workflows/f1_1c_repository_dispatch_catchall.yml`
- `.github/workflows/f1_autopilot_patch_receiver.yml`

The Control Room meta-health check flagged Bash `if` / `fi` imbalance, raw `git push`, and force-push risk inside workflow YAML run blocks. This patch removes complex inline shell from both workflows and routes execution through dedicated Node entrypoints already governed by the bridge validation/apply/status scripts.

## Scope

Changed files:

- `.github/workflows/f1_1c_repository_dispatch_catchall.yml`
- `.github/workflows/f1_autopilot_patch_receiver.yml`
- `docs/autopilot_bridge/V28_BRIDGE_WORKFLOW_META_HEALTH_FIX_2026-06-14.md`

Expected automatic bridge files may also appear when later bridge PRs run:

- `health/autopilot_last_status.json`
- `logs/autopilot_bridge/dispatch_*.json`

## Governance

- Bridge mode remains PR-only.
- Production automation remains OFF.
- Model promotion remains false.
- Stable engine remains protected.
- Canonical workbook remains protected.
- No direct-to-main write path is introduced.

## Follow-up

After merge, run the Control Room full chain with `run_forecast_gate=false`. If meta-health passes, proceed separately to race-result source-readiness normalization.
