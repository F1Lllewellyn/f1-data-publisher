# F1 Live Source Feed Capture Consolidated Installer Fix Install Report

Installed: 2026-06-10 20:36:17
Repo path: C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher
Backup directory: C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher\_archive\live_source_feed_capture_consolidated_installer_fix_20260610_203617

## Result

Installed cumulative consolidated validation patch with corrected installer file references.

## Previous installer issue fixed

The prior consolidated validation installer referenced legacy latest-preserve documentation filenames that were not included in that package. This installer preflights all package files before copying and uses the correct consolidated file list.

## What changed

- Installed stabilized experimental workflow.
- Installed stabilized live-capture script.
- Added consolidated documentation and manifest files.
- Preserved replaced files in the backup directory above.

## Next step

Commit and push the changes, then rerun the workflow manually with:

- capture_mode: manual
- manual_validation_mode: infrastructure_only
- duration_minutes: 2
- session_label: manual_test
- commit_outputs: true
