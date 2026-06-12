# F1 Workbook/KPI Refresh Applier - Source Discovery + Commit Guard Fix

## Purpose

This is a sandbox-only hardening patch for the Workbook/KPI Refresh Applier.

It fixes the validation issue where the applier looked at `latest/session_data_processor/` itself instead of the concrete session folder below it, such as:

`latest/session_data_processor/2026_1287_spain_barcelona_catalunya/practice_2_11301/`

## What changed

- Recursively discovers the newest concrete Session Data Processor output folder.
- Requires real source artifacts before creating or committing workbook/KPI refresh outputs.
- Blocks commits when source artifacts are missing or incomplete.
- Writes a runtime status file used by the workflow commit guard.
- Preserves canonical workbook protection, stable-engine protection, and promotion blocking.

## Install

Run:

`installer/RUN_F1_WORKBOOK_KPI_REFRESH_APPLIER_WINDOWS.bat`

Press Enter for the default repo path.

Then commit and push in GitHub Desktop.

## Validate

Run:

`F1 Workbook KPI Refresh - Run Now Button`

Expected result if FP2 session processor artifacts are still present:

- `status: refresh_applied`
- `commit_allowed: true`
- `source_status: needs_manual_review` or better
- sandbox workbook name should include the actual event/session, not `unknown_event_session`

Expected result if no session processor artifacts are available:

- `status: no_action`
- `commit_allowed: false`
- no new workbook/KPI refresh commit

## Governance

- Canonical workbook: untouched
- `Engine_2026-06-07_STABLE`: untouched
- Stable P1-P20: untouched
- Promotion: blocked
- Delete authority: not granted
