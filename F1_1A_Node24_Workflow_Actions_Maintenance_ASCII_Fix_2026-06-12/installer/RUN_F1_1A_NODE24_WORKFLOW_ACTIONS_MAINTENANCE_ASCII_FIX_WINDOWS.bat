@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-F1-1A-Node24-Workflow-Actions-Maintenance-ASCII-Fix.ps1"
echo.
echo Press any key to close...
pause >nul
