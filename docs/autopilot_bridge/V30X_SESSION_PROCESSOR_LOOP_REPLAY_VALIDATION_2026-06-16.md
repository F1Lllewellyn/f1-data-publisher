# V30X Session Processor Loop Replay Validation Runner

This patch adds a fixture-driven replay validation runner for the Session Data Processor Loop.

## Purpose

V30X validates the dry-run loop paths using deterministic fixtures before any sandbox-live activation or downstream consumer wiring is considered.

## Validated Paths

- No session gate: clean no-op.
- Session-end contract-ready path: processor chain is structurally ready but no source data is consumed.
- Session-end data-ready fixture path: source-data-ready sandbox evidence is recognized.
- Session-end blocking-failure path: downstream consumers remain blocked.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine remains untouched.
- Canonical workbook remains untouched.
- Race Predictions refresh remains disabled.
- Fantasy refresh remains disabled.
- Notification sending remains disabled.
