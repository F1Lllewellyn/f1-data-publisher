# Auto-Repair Orchestrator Design

## Problem

The system had become safe-failing but not self-repairing. The Workbook/KPI Refresh Applier correctly refused to commit when source status was `missing`, but it did not automatically run the upstream Session Data Processor and try again.

## Repair loop

```text
Detect Workbook/KPI no-action or missing source
-> run Session Data Processor Loop
-> rerun Workbook/KPI Refresh Applier
-> verify final source_status is eligible
-> verify protected assets were not touched
-> commit only source-backed outputs
-> write repair report
```

## Known repair recipes v1

1. Workbook/KPI source missing: run the session processor, then rerun workbook refresh.
2. Runtime diagnostics commit issue: upload `_runtime` as artifact only, never commit it.

## Commit-allowed rule

Commit only when:

- final workbook refresh says `commit_allowed: true`;
- final `source_status` is one of `clean`, `partial`, `late`, `conflicting`, or `needs_manual_review`;
- protected assets are untouched.

## Blocked operations

- Stable engine modification.
- Canonical workbook overwrite.
- Deletion or cleanup of source artifacts.
- Model promotion.
- GitHub secrets or permissions change.
- Force-push.
