# F1 Forecast Chain Event Context Fix - 2026-06-12

Verdict: Pass with warnings.

This patch fixes the manual validation confusion where the forecast workflows used different hidden/default event labels.

Plain-English rule:
- The event_id is just the folder label used by the forecast chain.
- This patch defaults the source writer, readiness validator, and bundle locker to the same label: manual_forecast_producer_validation.
- It also adds a one-click validation workflow so the user does not need to manage event_id manually.

Installed workflows:
- F1 Forecast Gate Source Writer v1
- F1 Forecast Chain Readiness Validator v1
- F1 Forecast Bundle Locker v1
- F1 Forecast Chain One-Click Validation v1

Stable engine logic, canonical workbook files, prediction outputs, and promotion status are not changed.
