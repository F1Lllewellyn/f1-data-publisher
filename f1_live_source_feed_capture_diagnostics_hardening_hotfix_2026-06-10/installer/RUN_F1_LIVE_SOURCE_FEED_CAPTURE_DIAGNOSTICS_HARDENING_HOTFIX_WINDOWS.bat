@echo off
setlocal
echo F1 Live Source Feed Capture Diagnostics Hardening Hotfix
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0Install-F1-Live-Source-Feed-Capture-Diagnostics-Hardening-Hotfix.ps1"
echo.
pause
