# V31F Race/Fantasy Readiness Metadata Contracts

This patch adds dry-run readiness metadata contracts for Race Predictions and Fantasy surfaces.

## Purpose

V31F defines the metadata required before Race Predictions or Fantasy readiness surfaces can be refreshed by a future activation patch.

## Non-Scope

- Does not generate race predictions.
- Does not generate fantasy picks.
- Does not refresh Race Predictions output.
- Does not refresh Fantasy output.
- Does not write to the canonical workbook.
- Does not activate production automation.
- Does not send notifications.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not modified.
- Canonical workbook is not overwritten.

## Next Step

If this contract is ready, the next layer is v31G: material notification preview gate.
