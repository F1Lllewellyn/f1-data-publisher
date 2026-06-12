# F1 1A GitHub Long-Path Cleanup Final Fix — 2026-06-12

## Purpose

This patch fixes the prior cleanup installer failure where the installer attempted to run a helper based on a null `ProcessStartInfo`/`ArgumentList` object.

It also fixes the original commit blocker: `.f1_patch_backups/` had been generated inside the repository and included deeply nested placeholder forecast bundle files. Git on Windows then failed with `Filename too long` while trying to process those generated backup files.

## What this patch does

- Removes `.f1_patch_backups/` from the repository working tree if present.
- Adds `.f1_patch_backups/` and `.f1_patch_external_backups/` to `.gitignore`.
- Removes the previously committed structural placeholder forecast bundles:
  - `latest/forecast_bundles/2026_next_event/`
  - `history/forecast_bundles/2026_next_event/`
- Sets `core.longpaths=true` locally for the repository where possible.
- Uses direct Git calls and `cmd /c rmdir` fallback instead of the broken PowerShell process helper.

## What this patch does not do

- Does not touch stable engine logic.
- Does not touch the canonical workbook.
- Does not change model weights or prediction outputs.
- Does not promote any experimental layer.
- Does not alter forecast bundle guard logic.

## Installer

Run:

```text
installer/RUN_F1_1A_GITHUB_LONGPATH_CLEANUP_FINAL_FIX_WINDOWS.bat
```

Then review Git changes, commit, and push.

Suggested commit message:

```text
chore: remove placeholder forecast bundles and ignore installer backups
```

## Follow-up validation

After pushing, run:

```text
F1 Forecast Chain Readiness Validator v1
```

With:

```text
event_id: manual_cleanup_validation
gate: all
lane: all
strict: false
commit_outputs: true
```

Expected result before actual forecast rows exist: `Pass with warnings / pending_actual_forecast_rows`.
