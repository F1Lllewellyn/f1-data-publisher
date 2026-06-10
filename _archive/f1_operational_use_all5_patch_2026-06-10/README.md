# F1 Operational Use All-5 Patch

## Use

1. Unzip this package.
2. Open `installer`.
3. Double-click:

`RUN_OPERATIONAL_USE_ALL5_PATCH_WINDOWS.bat`

4. When asked for the repo path, paste only:

`C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher`

5. Commit and push.

## After installing

Run only the small downstream workflows:

1. `F1 Automation Baseline Snapshot`
2. `F1 Workbook Control Room Bridge`
3. `F1 Dry Forecast Cycle`

Do **not** rerun the big OpenF1 extraction workflows.

## Optional release tag

After commit/push, you can create the local release tag using:

`scripts/admin/create_baseline_tag.ps1`

Tag:

`F1_Automation_Baseline_2026-06-10_READY`
