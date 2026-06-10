# F1 Elite Weekend Engine v2 Artifact Wiring + Node 24 Patch

## Purpose

This patch turns `Elite Weekend Engine Run` from a stub wrapper into an artifact-consuming control-room run.

It also opts the workflows into Node.js 24 now, using:

`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"`

This addresses the GitHub warning observed in the logs.

## Elite v2 behavior

The Elite workflow now:

1. Finds the latest OpenF1 Pre-Race Auto artifact.
2. Finds the latest OpenF1 Full Historical Auto artifact.
3. Finds the latest OpenF1 Post-Race Auto artifact.
4. Downloads those artifacts using the GitHub Actions API.
5. Builds real control outputs:
   - source readiness board
   - reliability warning board
   - DNF_ALL precursor board
   - fantasy risk board
   - model disagreement board
   - promotion/demotion gate
   - locked forecast ledger snapshot
6. Uploads a real Elite v2 artifact.

## Guardrails

- Public/proxy OpenF1 data only.
- No automatic stable race P1-P20 rank changes.
- No automatic qualifying P1-P5 rank changes.
- DNF_ALL broad precursor search preserved.
- 2026 no-DRS rule preserved.
- Post-race zero-feature output can be accepted as infrastructure health, but not as a reliability/fantasy/stable-ranking signal.

## Expected Elite v2 status

A healthy current state may be:

`READY_WITH_POSTRACE_SIGNAL_WARNING`

That means:
- pre-race artifact exists and is usable,
- full historical artifact exists and is usable,
- post-race artifact exists but has zero usable feature rows.
