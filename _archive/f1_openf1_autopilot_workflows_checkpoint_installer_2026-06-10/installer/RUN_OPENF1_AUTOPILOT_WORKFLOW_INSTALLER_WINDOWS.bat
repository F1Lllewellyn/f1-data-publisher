@echo off
echo F1 OpenF1 Autopilot Workflow Installer
echo This adds no-input automated workflows and checkpoint/split-job protection.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_openf1_autopilot_workflows.ps1" -Repo "%REPO%" -Apply
echo.
pause
