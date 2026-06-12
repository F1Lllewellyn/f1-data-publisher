@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Install-F1-NoCode-Automation-Dependency-Guard-Fix.ps1"
echo.
echo Installer finished. You can close this window after reviewing any messages above.
pause
