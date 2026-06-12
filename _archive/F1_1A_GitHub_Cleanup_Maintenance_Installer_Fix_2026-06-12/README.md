# F1 1A GitHub Cleanup + Maintenance Patch (2026-06-12)

Purpose:

1. Remove the already-committed placeholder forecast bundles created for `2026_next_event` during earlier Forecast Bundle Locker validation.
2. Preserve a local backup before removal.
3. Update common GitHub Actions dependencies away from older Node runtimes where applicable.
4. Install a Forecast Chain Readiness Validator so the source-writer / forecast-producing / bundle-locker chain can be validated once actual forecast rows exist.

This patch does **not** change stable engine logic, canonical workbooks, prediction outputs, or promotion status.

Installer:

```text
installer/RUN_F1_1A_GITHUB_CLEANUP_MAINTENANCE_PATCH_WINDOWS.bat
```

After install, commit and push the resulting repo changes.


## Installer fix note

This refreshed package fixes a Windows PowerShell backup issue where Copy-Item could fail while backing up deeply nested placeholder bundle folders. The installer now uses a Robocopy-backed directory backup helper and only then installs payload files.
