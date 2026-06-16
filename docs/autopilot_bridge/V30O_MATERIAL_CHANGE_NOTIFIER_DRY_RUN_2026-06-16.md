# V30O Material Change Notifier Dry-Run

This PR adds a dry-run material-change notifier for the Session Data Processor Loop.

## Scope

- Reads the v30M Control Room snapshot diff.
- Reads the v30N sandbox workbook readiness reflection.
- Decides whether a material readiness notification would be warranted.
- Writes a notification preview artifact when a material change is detected.
- Does not send any production notification.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook writes are not enabled.
- Notification sending is not enabled.
- Race prediction and fantasy readiness consumers remain closed.

## Follow-up

After review, v30P can add an end-to-end Control Room orchestrator dry-run that chains source fetch, validation, cache, snapshot diff, sandbox readiness, and notification preview generation without activating production consumers.
