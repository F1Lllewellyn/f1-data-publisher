# F1 1A Actual Forecast Producer Source Discovery Installer Fix 2026-06-12

Verdict: Pass after install.

This installer replaces the failed backup-copy installer.
It creates backup parent folders before copying existing files.
It does not call command-line Git.
It does not touch stable engine logic, workbook files, prediction outputs, or promotion status.

Default repo path used or offered: C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher
Repo path installed to: C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher
Backup root: C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\.f1_patch_external_backups\actual_forecast_producer_source_discovery_installer_fix_20260611_212623

## Installed files
- docs\F1_ACTUAL_FORECAST_PRODUCER_SOURCE_DISCOVERY_HOTFIX_2026-06-12.md
- manifests\actual_forecast_producer_source_discovery_patch_manifest.csv
- configs\forecasts\actual_forecast_producer_policy_v1.json
- scripts\forecasts\produce_actual_forecast_rows_v1.py
- .github\workflows\f1-actual-forecast-producer-v1.yml

## Next validation
Run workflow: F1 Actual Forecast Producer v1
Inputs: event_id=manual_forecast_producer_validation, race_name=Manual Forecast Producer Validation, gate=all, lane=all, strict_source=false, commit_outputs=true
