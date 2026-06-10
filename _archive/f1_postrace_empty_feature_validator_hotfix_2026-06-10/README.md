# Post-Race Empty Feature Validator Hotfix

## Use

1. Unzip this package.
2. Open `installer`.
3. Double-click:

`RUN_POSTRACE_EMPTY_FEATURE_HOTFIX_WINDOWS.bat`

4. When asked for the repo path, paste only:

`C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher`

5. Commit and push in GitHub Desktop.

## After installing

Run only:

`OpenF1 Post-Race Auto Reliability`

Expected result if the latest race still has zero feature rows:

`Validation PASS_WITH_WARNINGS`

The run should be green, but it should not be used as a reliability signal until feature rows are available.
