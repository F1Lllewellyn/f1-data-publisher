@echo off
echo F1 OpenF1 Lightweight Source Closure + Zero-Lane Diagnostics Patch
echo This installs a GitHub-side lightweight source capture workflow and diagnostic publisher.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_openf1_lightweight_source_closure.ps1" -Repo "%REPO%" -Apply
echo.
pause
