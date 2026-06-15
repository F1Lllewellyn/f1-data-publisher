# V30C Public Source Crosscheck Dry-Run

This PR adds sandbox-only public-source crosscheck scaffolding for the Session Data Processor Loop.

## Scope

- Adds a dry-run FIA/public-document source adapter contract.
- Adds a dry-run source crosscheck validator.
- Adds source validation policy metadata.
- Writes only health/log style artifacts when executed.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- No live network fetch is enabled by default.

## Intended follow-up

V30D can integrate live source validation or Control Room orchestration after this dry-run contract is reviewed.
