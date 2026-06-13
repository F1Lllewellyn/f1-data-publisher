# F1 Workflow Meta-AutoRepair One-Click Fix — 2026-06-12

## Purpose
Fixes the scheduled Workbook/KPI workflow failure introduced by workflow-stability hardening and adds a repo-native workflow meta-health check so similar workflow syntax/commit-fragility failures can be detected before the next scheduled run.

## Critical fix
The failed scheduled-refresh job had a malformed shell block: an `if ... else` commit block was missing its final `fi`, causing `syntax error: unexpected end of file` after a valid source-backed refresh.

This package replaces `f1-workbook-kpi-refresh-scheduled.yml` with a validated version that:
- preserves source-backed commit gating;
- uses write serialization;
- uses the safe push/rebase/retry helper;
- closes all shell `if/fi` blocks;
- does not touch stable engine logic or the canonical workbook.

## Also added
`F1 Workflow Meta-Health - Safe Test Button`, which scans workflow run blocks for basic shell `if/fi` imbalance and raw `git push` patterns.

## Install
Run `install.bat`, press Enter for the default repo path, commit/push in GitHub Desktop.

## Validate
1. Run `F1 Workflow Meta-Health - Safe Test Button`.
2. Re-run `F1 Workbook KPI Refresh - Scheduled Processor` or wait for the next scheduled run.
3. Send logs.
