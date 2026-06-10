@echo off
echo F1 GitHub automation CLEAN installer - FIXED v3
echo This will archive old F1 automation paths and install the clean version.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_f1_github_automation_clean_FIXED_v3.ps1" -Repo "%REPO%" -Apply
echo.
pause
