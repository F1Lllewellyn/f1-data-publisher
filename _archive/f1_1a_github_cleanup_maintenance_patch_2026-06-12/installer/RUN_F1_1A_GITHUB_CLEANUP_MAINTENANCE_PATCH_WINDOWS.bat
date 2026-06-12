@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Install-F1-1A-GitHub-Cleanup-Maintenance-Patch.ps1"
pause
