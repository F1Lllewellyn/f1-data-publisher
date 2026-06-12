@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Install-F1-Actual-Forecast-Producer-Source-Discovery-Installer-Fix.ps1"
echo.
pause
