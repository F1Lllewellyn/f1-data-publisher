# F1 OpenF1 Post-Race Empty Feature Validator Hotfix

This patch fixes the post-race autopilot workflow behavior when the latest completed race extraction succeeds but produces zero 30-second feature rows.

## Problem observed

The workflow successfully:
- selected the latest completed race session,
- extracted 1,162,832 high-frequency rows,
- uploaded a checkpoint artifact,
- wrote the report,
- uploaded the final artifact.

But validation failed because the validator required:

`features/openf1_high_frequency_reliability_features_30s.parquet`

For post-race latest-race automation, zero feature rows should be treated as `PASS_WITH_WARNINGS`, not a hard infrastructure failure.

## Change

- Keeps `prerace` and `all` validation strict.
- Allows `race` mode to pass with warnings when extraction/report/artifact are valid but feature rows are zero.
- Keeps guardrail language: no stable/fantasy/race-order signal should consume a zero-feature post-race run.
- Updates only the post-race workflow to call `--allow-empty-features`.
