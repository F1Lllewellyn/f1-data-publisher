# F1 1B Downstream Consumer Wiring v24

Date: 2026-06-13

## Purpose

v24 connects the operational output-contract layer to explicit downstream consumer inputs for:

- Race Predictions
- Fantasy Predictions
- Race Reports

It does not generate forecasts, fantasy picks, transfers, chips, reports, PDFs, promotions, or model updates. It only publishes machine-readable readiness contracts that the downstream chats/systems can consume.

## Runtime sequence

```text
Control Room succeeds
→ output-contract ledger/handoff runs
→ v24 downstream consumer handoff writer runs
→ consumer input manifests are committed with the existing safe push helper
```

## New outputs

```text
latest/downstream_consumers/combined_downstream_consumer_manifest.json
latest/downstream_consumers/combined_downstream_consumer_manifest.csv
latest/downstream_consumers/downstream_consumer_wiring_report.json
latest/downstream_consumers/race_predictions/consumer_input.json
latest/downstream_consumers/fantasy_predictions/consumer_input.json
latest/downstream_consumers/race_reports/consumer_input.json
history/downstream_consumers/<event_id>/<run_id>/combined_downstream_consumer_manifest.json
```

## Safety gates

```text
forecast_gate_activated = false
promotion_allowed = false
stable_engine_modified = false
canonical_workbook_overwrite = false
```

## Downstream interpretation

Race Predictions may use v24 inputs only as readiness, source-backed context, confidence/risk, and handoff evidence. Stable P1-P20 logic is not overwritten.

Fantasy Predictions may use v24 inputs only as readiness, value/risk, constructor/driver context, and chip/transfer recommendation context. No transfer or chip action is executed.

Race Reports may use v24 inputs for source/readiness context. Full Report PDF generation remains user-requested/report-lane controlled.
