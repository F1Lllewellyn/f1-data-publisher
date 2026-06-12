# F1 Forecast Bundle Locker No-Source Commit Guard Hotfix — 2026-06-11

## Verdict

Pass with warnings.

This hotfix tightens the Forecast Bundle Locker after validation showed that a manual run with `commit_outputs: true` could commit structural placeholder bundles even when `source_found: 0`.

## What it fixes

- Removes automatic manual placeholder-bundle creation unless explicitly requested.
- Adds workflow input `allow_structural_placeholders`, default `false`.
- If no actual forecast source rows exist, the workflow exits cleanly and uploads a runtime guard artifact, but does not create `latest/forecast_bundles` or `history/forecast_bundles` output bundles.
- Commit step now only stages `latest/forecast_bundles` and `history/forecast_bundles`; it does not commit `_runtime` guard-only artifacts.
- Scheduled guard behaviour remains intact.

## Important note

This does not delete placeholder bundles already committed by a previous validation run. Those should only be removed after explicit approval.

## Stable protection

Stable engine logic, canonical workbook, prediction outputs, and promotion status are unchanged.
