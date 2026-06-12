# F1 1A No-Code Automation Commit Ignore Fix — 2026-06-12

## Verdict
Pass with warnings.

## Reason for patch
The Run Now Button successfully executed the forecast chain but failed during the final commit step because the workflow tried to commit `_runtime/forecast_gate_orchestrator`, which is intentionally ignored by `.gitignore`.

That folder should be uploaded as a GitHub Actions artifact, not committed to the repository.

## What this fixes
- Keeps runtime diagnostics in the downloadable Actions artifact.
- Removes `_runtime/forecast_gate_orchestrator` from commit candidates.
- Adds a guard that skips any path Git marks as ignored.
- Preserves source refresh, forecast production, readiness validation, bundle locking, artifact upload, and no-placeholder protections.
- Does not touch stable engine logic.
- Does not touch the canonical workbook.
- Does not enable promotion.

## Expected result after install
The Run Now Button should be able to complete the same successful chain and then commit/push the valid output folders without failing on ignored runtime diagnostics.

Expected real-run result:
- OpenF1 source closure: pass
- Forecast rows: created
- Readiness: pass
- Bundles: created
- Artifact upload: pass
- Commit/push: pass or no-op if no tracked changes

## No-code usage
After install, use GitHub Desktop to commit and push. Then run **F1 Forecast Automation - Run Now Button**.
