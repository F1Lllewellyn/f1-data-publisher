# Validation Report

Local validation completed against a sample source-backed Spain / Barcelona-Catalunya Practice 2 artifact set.

## Local test results

- Health check: Pass
- Safe test mode: Pass
- Run now mode with source-backed artifacts: Pass
- Missing source behavior: Pass in design; commit blocked
- Material change detection: Pass
- Race Predictions brief creation: Pass
- Fantasy brief creation: Pass
- Governance flags: Pass

## Live validation still required

After installation, run:

1. F1 Forecast/Fantasy Readiness Dashboard - Safe Test Button
2. F1 Forecast/Fantasy Readiness Dashboard - Run Now Button

The expected Run Now result is either:

- dashboard_refreshed with source_status needs_manual_review/clean/partial/late/conflicting, or
- no_action with commit_allowed false if source is missing/stale.
