# V30F Session Processor Loop Dry-Run

This PR adds a dry-run orchestrator for the Session Data Processor Loop.

## Scope

- Reads a session gate event.
- Detects whether a session-end signal is present.
- Runs or reads the v30D readiness Control Room summary.
- Runs or reads the v30E material-change notifier.
- Emits a final loop summary and effective notification candidate.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook mutation remains disabled.
- Notification sending remains disabled.

## Role In The Loop

This is the first dry-run integration layer:

`session end gate -> readiness processor -> material-change decision -> notification candidate`

Future follow-up can add the live source-fetch contract after this integration layer is reviewed.
