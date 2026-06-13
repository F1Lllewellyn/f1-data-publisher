@echo off
setlocal
cd /d "%~dp0"
echo F1 Peak-Elite System Installer v1
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\Install-F1-Peak-Elite-System.ps1"
echo.
echo Installer finished. You may close this window after reviewing any messages above.
pause
