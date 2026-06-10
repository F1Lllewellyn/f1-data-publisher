@echo off
echo F1 All-5 Operational Baseline Patch Installer
echo This locks the baseline, fixes post-race zero-feature handling, adds workbook bridge exports, improves summaries, and adds the forecast-cycle runbook.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_all5_operational_baseline_patch.ps1" -Repo "%REPO%" -Apply
echo.
pause
