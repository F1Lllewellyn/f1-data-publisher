# F1 Operational Use Runbook

## After installing this patch

Run only small downstream workflows:

1. `F1 Automation Baseline Snapshot`
2. `F1 Workbook Control Room Bridge`
3. `F1 Dry Forecast Cycle`

Do not rerun large OpenF1 extraction workflows.

## Normal future cycle

1. OpenF1 Pre-Race Auto Ingest runs automatically.
2. Elite Weekend Engine Run consumes validated artifacts.
3. Workbook Control Room Bridge builds workbook-ready package.
4. Dry Forecast Cycle creates advisory forecast-consumption package.
5. Human review decides whether any prediction/fantasy guidance should change.

## Release tag

After committing and pushing this patch, use the included local helper:

`scripts/admin/create_baseline_tag.ps1`

Tag name:

`F1_Automation_Baseline_2026-06-10_READY`
