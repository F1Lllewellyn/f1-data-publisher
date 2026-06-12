# F1 No-Code Forecast Automation Buttons - 2026-06-12

## Purpose

This patch adds two no-code GitHub Actions buttons so the operator does not have to understand or type workflow variables such as event_id, gate, dry_run, or force_validation.

## Added workflows

1. F1 Forecast Automation - Safe Test Button
   - Manual button only.
   - No fields to fill in.
   - Does not commit outputs.
   - Checks that the automation chain can start and that required scripts are present.

2. F1 Forecast Automation - Run Now Button
   - Manual button only.
   - No fields to fill in.
   - Runs the real auto-detection path.
   - If a real race gate is active, it can refresh source data, produce forecasts, validate rows, lock bundles, and commit outputs.
   - If no real race gate is active, it exits cleanly.

## Existing scheduled automation

This patch does not replace the scheduled orchestrator. The scheduled workflow remains the primary elite operating model. These buttons are operator-friendly wrappers for testing or manual confirmation.

## Safety

- No stable engine logic changes.
- No canonical workbook changes.
- No model promotion.
- No manual event label entry required.
- No local command-line Git required.
- Structural placeholder bundles remain blocked by the underlying locker guard.
