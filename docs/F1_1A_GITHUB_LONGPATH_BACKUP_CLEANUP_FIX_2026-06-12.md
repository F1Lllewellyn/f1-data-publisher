# F1 1A GitHub Long-Path Backup Cleanup Fix — 2026-06-12

## Purpose

This patch fixes the Windows/Git commit failure caused by generated installer backup files under:

```text
.f1_patch_backups/
```

The failure was caused by long nested paths inside the backup copy of the already-committed placeholder forecast bundles, especially paths under:

```text
history/forecast_bundles/2026_next_event/20260612T001324Z/
```

## What it does

- Adds `.f1_patch_backups/` to `.gitignore`.
- Removes `.f1_patch_backups/` from Git tracking if Git saw it.
- Robustly removes the local `.f1_patch_backups/` folder using long-path fallback logic.
- Removes placeholder bundle folders:
  - `latest/forecast_bundles/2026_next_event/`
  - `history/forecast_bundles/2026_next_event/`
- Leaves stable engine logic unchanged.
- Leaves canonical workbook files unchanged.
- Leaves prediction outputs unchanged.
- Performs no promotion.

## Installer

Run:

```text
installer/RUN_F1_1A_GITHUB_LONGPATH_BACKUP_CLEANUP_FIX_WINDOWS.bat
```

Then review the Git diff, commit, and push.

Recommended commit message:

```text
chore: cleanup placeholder bundles and ignore local patch backups
```

## Why this patch exists

The prior cleanup installer created a local backup inside the repo. That was safe in principle, but on Windows it created very long nested paths that Git Desktop could not process during commit. Future installer backups should stay outside the repo or be ignored by Git.
