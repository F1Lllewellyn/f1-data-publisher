# V30U R2 Executable Format Hardening

This patch hardens the v30Q-v30U dry-run executable chain against bridge or email clients that collapse source-file line breaks.

## Scope

- Rewrites the executable scripts without shebang headers or leading block comments.
- Preserves the existing v30Q, v30R, v30S, v30T, and v30U dry-run behavior.
- Keeps the chain semicolon-safe if rendered as a single logical line.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Live fetch is not performed.
- Race Predictions refresh remains disabled.
- Fantasy refresh remains disabled.
- Notifications remain disabled.

## Validation

- Node syntax checks passed for all five hardened scripts.
- v30U orchestrator dry-run returned `ready_dry_run_no_execution` with fixture source-summary input.
