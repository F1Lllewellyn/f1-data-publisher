@echo off
setlocal
cd /d "%~dp0"
echo F1 Live Source Feed Capture Patch Installer
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0Install-F1-Live-Source-Feed-Capture-Patch.ps1"
echo.
echo Done. You can close this window.
pause
