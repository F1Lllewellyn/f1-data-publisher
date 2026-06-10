@echo off
echo F1 GitHub automation CLEAN installer - NO PYTHON VERSION
echo This will archive old F1 automation paths and install the new clean version.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_f1_github_automation_clean.ps1" -Repo "%REPO%" -Apply
echo.
pause
