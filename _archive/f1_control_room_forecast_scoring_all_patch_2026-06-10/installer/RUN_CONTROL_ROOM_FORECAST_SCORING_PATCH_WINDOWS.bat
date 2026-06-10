@echo off
echo F1 Control Room + Forecast Review + Post-Race Scoring Installer
echo This adds the no-v18 operational workbook, forecast review, operating rhythm, and post-race scoring loop.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_control_room_forecast_scoring_patch.ps1" -Repo "%REPO%" -Apply
echo.
pause
