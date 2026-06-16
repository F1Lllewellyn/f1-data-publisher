# V30G Session Source Fetch Contract Dry-Run

This PR adds the dry-run source-fetch contract for the Session Data Processor Loop.

## Scope

- Reads a session-end gate event.
- Emits the source plan required before a forecast/readiness refresh.
- Defines OpenF1, FastF1, FIA public document, and Formula 1 public-context source roles.
- Records minimum fields, validation checks, blocking status, and intended output artifacts.
- Performs no live source fetch by default.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook mutation remains disabled.
- Notification sending remains disabled.

## Role In The Loop

V30F connected the dry-run loop:

`session-end gate -> readiness processor -> material-change decision -> notification candidate`

V30G defines the next layer:

`session-end gate -> source-fetch plan -> source validation contract -> readiness refresh prerequisites`

Future work can add sandbox live-fetch adapters only after this contract is reviewed.
