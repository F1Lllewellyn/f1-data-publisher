# F1 Season Archive Publisher Runbook

## After installing this patch

1. Commit and push.
2. Run `F1 Create Automation Baseline Tag`.
3. Run `F1 Season Archive Publisher`.

Do not rerun OpenF1 extraction workflows.

## What the archive publisher does

It downloads the latest compact artifacts:

- Elite Weekend Engine v2
- Workbook Control Room Bridge
- Dry Forecast Cycle
- Automation Baseline Snapshot

Then it packages them into:

`F1_2026_Season_Archive_COMPACT_<date>_run<run>.zip`

and publishes that as a GitHub Release asset.

## Why releases

GitHub Actions artifacts are temporary. GitHub Releases are tag-based long-term archive objects and are better suited for season records.

## Schedule

The workflow also has a monthly schedule. Manual runs are available for milestone snapshots.
