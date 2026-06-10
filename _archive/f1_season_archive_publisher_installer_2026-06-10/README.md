# F1 Season Archive Publisher Installer

## Use

1. Unzip this package.
2. Open `installer`.
3. Double-click:

`RUN_SEASON_ARCHIVE_PUBLISHER_INSTALLER_WINDOWS.bat`

4. When asked for the repo path, paste only:

`C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher`

5. Commit and push.

## After installing

Run these GitHub workflows:

1. `F1 Create Automation Baseline Tag`
2. `F1 Season Archive Publisher`

Do not rerun OpenF1 extraction workflows.

## Purpose

GitHub Actions artifacts are temporary. This patch publishes compact derived season archives as GitHub Release assets for long-term season/year preservation.
