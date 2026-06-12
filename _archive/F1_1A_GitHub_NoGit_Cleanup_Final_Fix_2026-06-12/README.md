# F1 1A GitHub No-Git Cleanup Final Fix — 2026-06-12

## Verdict
Pass as corrected installer package.

## Why this package exists
The previous cleanup installer failed because Git is not available in the shell PATH on the user's Windows environment. The failure happened while the script attempted to call `git` to untrack generated backup folders.

## What this version changes
This installer does not call `git` at all. It performs only filesystem cleanup and `.gitignore` maintenance. The user can then commit and push using GitHub Desktop.

## Cleanup targets
- `.f1_patch_backups/`
- `.f1_patch_external_backups/`
- `latest/forecast_bundles/2026_next_event/`
- `history/forecast_bundles/2026_next_event/`

## Safety
It does not touch stable engine logic, workbook files, prediction outputs, or promotion status.

## Installer
`installer/RUN_F1_1A_GITHUB_NOGIT_CLEANUP_FINAL_FIX_WINDOWS.bat`

## After install
Review GitHub Desktop diff, commit, and push.
Suggested commit message:

`chore: remove placeholder forecast bundles and ignore installer backups`
