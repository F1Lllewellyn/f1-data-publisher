# F1 1A No-Code Automation Dependency + Guard Fix — 2026-06-12

## Verdict
Pass with warnings.

## Why this patch exists
The latest logs showed two different outcomes:

- **Safe Test Button:** passed. It completed the dry run and uploaded the safe-test report.
- **Run Now / automated orchestrator:** correctly detected a real pre-weekend gate for Spain - Barcelona - Catalunya and successfully produced, validated, and locked three pre-weekend lane bundles inside the runner, but the overall workflow failed because the source-refresh step needed the Excel writer package `openpyxl` and the workflow had only installed `pandas` and `requests`.

## Plain-English issue
The automation tried to refresh OpenF1 source data, but GitHub did not have one required Excel helper installed. That caused the source-refresh step to fail.

## What this patch changes
1. Adds `openpyxl` to the GitHub dependency install step in:
   - `F1 Automated Forecast Gate Orchestrator v1`
   - `F1 Forecast Automation - Safe Test Button`
   - `F1 Forecast Automation - Run Now Button`
2. Adds a simple dependency preflight message before the workflows proceed.
3. Hardens the orchestrator so that if required source refresh fails during a real run, it stops before creating or locking bundles from stale data.
4. Keeps the no-code buttons unchanged from the user's point of view.

## What this does not change
- Does not modify the stable engine.
- Does not modify the canonical workbook.
- Does not allow promotion.
- Does not allow structural placeholder bundles.
- Does not require the user to type code terms.

## Expected result after installation
- Safe Test Button should still pass quickly.
- Run Now Button should no longer fail on missing `openpyxl`.
- If a real gate is active, source refresh should run first; if it succeeds, the chain proceeds to forecast production, validation, and bundle locking.
- If source refresh fails for any future reason, the chain will stop safely and not lock stale-source bundles.
