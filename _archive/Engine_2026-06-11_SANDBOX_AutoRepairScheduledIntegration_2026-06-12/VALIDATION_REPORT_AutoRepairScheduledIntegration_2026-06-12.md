# Validation Report

## Local package validation

Status: Pass with warnings.

Validated locally:

- required workflow files exist;
- required scripts are included;
- Auto-Repair source-status alias fix is included;
- Session Data Processor script is included;
- Workbook/KPI Refresh Applier script is included;
- installer is ASCII-safe and uses the known local repo path by default;
- canonical workbook overwrite remains blocked;
- stable engine modification remains blocked;
- promotion remains blocked.

## Warning

This package validates integration scaffolding locally. The real proof is a GitHub Actions run of:

```text
F1 Session Auto-Repair Integrated - Run Now Button
```

A successful live validation should show:

```text
commit_allowed: true
final_workbook_status: refresh_applied
final_workbook_source_status: needs_manual_review or better
```

or, if no source exists:

```text
commit_allowed: false
no bad workbook commit
```
