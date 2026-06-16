# V30V Session-End Watcher To Processor Loop Dry-Run

This patch adds a dry-run watcher bridge from session-end events into the v30U Session Processor Loop readiness orchestrator.

## Scope

- Reads a session event payload.
- Detects terminal session signals such as `session_end`, `session_complete`, `chequered_flag`, or final/classified status.
- Calls the v30U processor-loop readiness orchestrator only when a session-end gate is detected.
- Emits one watcher-level status record.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Live fetch is not performed.
- Forecast bundle publishing remains disabled.
- Race Predictions refresh remains disabled.
- Fantasy refresh remains disabled.
- Notifications remain disabled.

## Intended Follow-Up

After review, v30W should add a sandbox-live source pull harness behind explicit dry-run and sandbox-live controls.
