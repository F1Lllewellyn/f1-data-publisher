# V30C R2 Public Source Crosscheck Dry-Run

This PR refreshes v30C from the updated main branch after v30B was merged.

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

## Why R2

The original v30C PR conflicted after v30B changed the generated bridge status file. R2 uses a fresh branch from current main to avoid that stale generated-file conflict.
