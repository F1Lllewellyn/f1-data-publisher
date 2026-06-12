# F1 1A GitHub Cleanup + Maintenance Patch — 2026-06-12

## Verdict

Pass with warnings.

## Purpose

This patch removes the already-committed `2026_next_event` placeholder forecast bundles from the working tree, updates common GitHub Actions versions to reduce Node.js runtime warnings, and installs a forecast-chain readiness validator.

## What it removes

The installer runs a cleanup script that targets:

```text
latest/forecast_bundles/2026_next_event/
history/forecast_bundles/2026_next_event/
```

Before removal, the script copies any existing targets to:

```text
.f1_patch_backups/cleanup_maintenance_<timestamp>/
```

The backup is intentionally local and not committed.

## Node.js maintenance

The patch updates the common Actions used by our workflows:

```text
actions/checkout@v6
actions/setup-python@v6
actions/upload-artifact@v6
```

This does not change the Python versions used by individual workflows.
For example, workflows that require Python 3.9 for FastF1 live timing compatibility remain pinned to Python 3.9.

## Forecast-chain validation

Installs workflow:

```text
F1 Forecast Chain Readiness Validator v1
```

Script:

```text
scripts/forecast_bundles/validate_forecast_chain_readiness_v1.py
```

It validates actual forecast rows only. If actual rows are missing, it reports `pending_actual_forecast_rows` and does not fabricate saved bundles.

## Guardrails

- Stable engine logic unchanged.
- Canonical workbook unchanged.
- No promotion.
- No stable exact P1-P20 overwrite.
- Forecast Bundle Locker remains guarded against no-source placeholder commits.


## Installer fix included

The installer now uses a robust Backup-PathSafe helper. Directory backup is performed through Robocopy, which creates nested destination folders reliably before the cleanup script removes placeholder bundle trees. This fixes the prior Copy-Item DirectoryNotFoundException during backup.
