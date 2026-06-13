# F1 1B Output Contract v16

Purpose: create the first combined Forecast Bundle Ledger + last-good-state + material-change + readiness-handoff layer for the 1B autonomous processor lane.

This is additive and controlled. It does not modify stable engine logic, canonical workbooks, forecast gate activation, or model promotion.

## Included pieces

1. Forecast Bundle Ledger snapshot writer
2. Last-good-state pointer
3. Material-change detector
4. Race/Fantasy/Race Reports handoff manifests
5. Acceptance-test harness

## Operational rule

Run after the Peak Elite Control Room full-run chain has produced fresh session processor and workbook/KPI outputs. Forecast gate remains off.

## Expected outputs

- `latest/forecast_bundle_ledger/latest_bundle_snapshot.json`
- `history/forecast_bundle_ledger/<event>/<run_id>/bundle_snapshot.json`
- `latest/last_good_state.json`
- `latest/material_change/material_change_report.json`
- `latest/readiness_handoff/combined_readiness_handoff.json`
- `latest/readiness_handoff/race_predictions_readiness.json`
- `latest/readiness_handoff/fantasy_predictions_readiness.json`
- `latest/readiness_handoff/race_reports_readiness.json`
- `latest/1b_output_contract/output_contract_report.json`

## Activation boundary

This patch adds a manual GitHub Actions workflow only. It does not activate scheduled production automation and does not enable forecast promotion.
