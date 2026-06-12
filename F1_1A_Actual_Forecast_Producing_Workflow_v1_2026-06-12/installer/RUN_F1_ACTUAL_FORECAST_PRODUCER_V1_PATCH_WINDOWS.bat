@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-F1-Actual-Forecast-Producer-v1-Patch.ps1"
echo.
echo Press Enter to close...
pause >nul
