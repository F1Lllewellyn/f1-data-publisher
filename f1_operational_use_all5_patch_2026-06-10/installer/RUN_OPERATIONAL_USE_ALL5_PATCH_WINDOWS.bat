@echo off
echo F1 Operational Use All-5 Patch Installer
echo This adds baseline snapshot, workbook bridge, forecast-consumption policy, dry forecast cycle, and next-weekend runbook.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_operational_use_all5_patch.ps1" -Repo "%REPO%" -Apply
echo.
pause
