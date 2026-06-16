# V30E Session Material Change Notifier Dry-Run

This PR adds dry-run material-change detection for the Session Data Processor Loop.

## Scope

- Compares the current v30D Control Room readiness snapshot with an optional previous snapshot.
- Detects material changes in readiness state, input presence, input status, and governance issues.
- Emits a notification candidate only.
- Does not send email or chat notifications.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook mutation remains disabled.

## Role In The Loop

This is the notification decision layer:

`session readiness summary -> material-change check -> notification candidate`

Future follow-up can wire the candidate into the approved notification channel after the dry-run contract is reviewed.
