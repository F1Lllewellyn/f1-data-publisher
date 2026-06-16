# V31C Downstream Consumer Contract Wiring

This patch adds dry-run downstream consumer contract wiring for the Session Data Processor Loop.

## Purpose

V31C maps source-evidence review status into downstream consumer eligibility without activating any consumer.

## Consumers Represented

- Sandbox workbook KPI/readiness reflection.
- Forecast Bundle Ledger snapshot writer.
- Race Predictions readiness refresh metadata.
- Fantasy readiness refresh metadata.
- Material notification preview artifact.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not modified.
- Canonical workbook is not overwritten.
- Live fetch is not performed.
- Workbook writes, forecast writes, prediction refresh, fantasy refresh, and notification sending remain disabled.

## Next Step

If the contract is review-ready, the next safe layer is sandbox workbook KPI reflection contract in dry-run mode.
