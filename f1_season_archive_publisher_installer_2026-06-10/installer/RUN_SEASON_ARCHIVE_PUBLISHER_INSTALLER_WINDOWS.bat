@echo off
echo F1 Season Archive Publisher Installer
echo This adds the baseline tag workflow and long-term compact season archive publisher.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_season_archive_publisher.ps1" -Repo "%REPO%" -Apply
echo.
pause
