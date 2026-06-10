@echo off
echo F1 Elite v2 Artifact Wiring + Node24 Installer
echo This wires Elite Weekend Engine Run to latest OpenF1 artifacts and opts workflows into Node.js 24.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_elite_v2_artifact_wiring_node24.ps1" -Repo "%REPO%" -Apply
echo.
pause
