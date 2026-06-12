@echo off
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Install-F1-1A-GitHub-Cleanup-Maintenance-Patch.ps1"
pause
