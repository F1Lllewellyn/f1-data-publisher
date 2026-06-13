# F1 1B Race Predictions Context v25

## Confirmed Data
- Event: Spain - Barcelona - Catalunya
- Session: Qualifying / key 11303
- Run ID: 20260613T165712Z
- Consumer readiness: ready
- Source status: clean
- Workbook source status: clean
- Readiness quality: usable_with_optional_context_gaps
- Material change detected: True
- Notification recommended: True
- Forecast gate: off
- Promotion allowed: false
- Stable engine modified: false
- Canonical workbook overwrite: false

## How This Context May Be Used
- Exact P1-P20 prediction context, confidence/risk flags, source-readiness proof.
- Trigger action: notify_and_update_context
- Trigger reason: material readiness or forecast-relevant state changed

## Boundaries
- Do not promote experimental logic from this context alone.
- Do not overwrite Engine_2026-06-07_STABLE.
- Do not overwrite the canonical workbook.
- Do not activate forecast gate from this package.

## Open Questions
- Are newer session gates available after this run?
- Are there critical source conflicts not represented in the current handoff?
- Does the downstream lane need a human-readable prediction/report output now, or should it stay quiet?

## Source Files
- downstream: `latest/downstream_consumers/combined_downstream_consumer_manifest.json`
- race_predictions: `latest/downstream_consumers/race_predictions/consumer_input.json`
- bundle: `latest/forecast_bundle_ledger/latest_bundle_snapshot.json`
- last_good: `latest/last_good_state.json`
- material_change: `latest/material_change/material_change_report.json`
- handoff: `latest/readiness_handoff/combined_readiness_handoff.json`
- output_contract: `latest/1b_output_contract/output_contract_report.json`
