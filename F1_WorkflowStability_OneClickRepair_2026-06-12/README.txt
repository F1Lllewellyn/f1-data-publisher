# F1 Workflow Stability One-Click Repair — 2026-06-12

## Purpose

This patch fixes two failed workflows in one step:

1. **Workbook/KPI scheduled refresh push rejection**
   - Cause: concurrent GitHub workflows committed to `main` before the scheduled refresh could push.
   - Fix: add a safe push/rebase/retry helper and install a write-serialization guard for commit-producing workflows.

2. **Cross-Car Microdelta failure when no preferred input CSV exists**
   - Cause: the experimental microdelta workflow assumed a preferred driver/session summary CSV would always be present.
   - Fix: source-discovery guard now exits safely with a no-action report instead of failing the workflow. It still runs normally when a valid source CSV exists.

## Governance

- Sandbox / workflow hardening only.
- Does not alter `Engine_2026-06-07_STABLE`.
- Does not overwrite the canonical workbook.
- Does not promote any model layer.
- Does not delete old files.
- Does not require local Python.
- Does not require local Git.

## Install

Run:

```text
install.bat
```

Press Enter for the default repo path:

```text
C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher
```

Then commit/push in GitHub Desktop.

## Validate

After pushing, run these two workflows:

1. `F1 Cross-Car Microdelta Forensics Experimental`
2. The workflow that previously failed as `scheduled-refresh` / `F1 Workbook KPI Refresh - Scheduled`

Expected:
- Microdelta should either run normally or end with `status: no_action` instead of failing.
- Workbook/KPI scheduled refresh should no longer fail on `fetch first`; if another workflow pushes first, it retries safely.
