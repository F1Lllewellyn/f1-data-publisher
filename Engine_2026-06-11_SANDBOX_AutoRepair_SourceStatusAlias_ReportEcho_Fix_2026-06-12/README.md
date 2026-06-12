# Engine_2026-06-11_SANDBOX_AutoRepair_SourceStatusAlias_ReportEcho_Fix_2026-06-12

## Purpose

This is a sandbox-only hardening fix for the Auto-Repair Orchestrator and Workbook/KPI Refresh Applier.

It addresses the latest Auto-Repair Run Now log, where Auto-Repair attempted recovery but did not allow commit:

```text
repair_attempted: true
repair_succeeded: false
commit_allowed: false
```

## Root cause fixed

The Session Data Processor writes its upstream readiness classification as:

```text
overall_status
```

The Workbook/KPI Refresh Applier was checking:

```text
classification / overall_classification / status
```

but not `overall_status`.

That meant source-backed FP2-style session data could still be interpreted as `missing`.

## What this fix changes

1. Workbook/KPI Refresh Applier now accepts these aliases:
   - `classification`
   - `overall_status`
   - `overall_classification`
   - `source_status`
   - `status`

2. Auto-Repair Run Now now prints a plain-English report directly into the GitHub log.

3. The commit guard remains strict:
   - commits allowed only for `clean`, `partial`, `late`, `conflicting`, or `needs_manual_review`
   - commits blocked for `missing`, `unknown`, `placeholder`, and scheduled-but-not-populated

## Governance

- Canonical workbook overwrite: blocked
- Engine_2026-06-07_STABLE modification: blocked
- Stable P1-P20 overwrite: blocked
- Promotion: blocked
- Deletion/cleanup authority: not granted

## Install

Run:

```text
installer/RUN_F1_AUTOREPAIR_SOURCE_STATUS_ALIAS_REPORT_ECHO_FIX_WINDOWS.bat
```

Press Enter for the repo path.
