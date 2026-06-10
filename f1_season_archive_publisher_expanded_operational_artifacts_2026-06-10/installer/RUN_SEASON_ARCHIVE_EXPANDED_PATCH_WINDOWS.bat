@echo off
echo F1 Season Archive Expanded Operational Artifacts Patch
echo This updates the archive publisher to include forecast review, operating rhythm, and post-race scoring artifacts.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_season_archive_expanded_operational_artifacts.ps1" -Repo "%REPO%" -Apply
echo.
pause
