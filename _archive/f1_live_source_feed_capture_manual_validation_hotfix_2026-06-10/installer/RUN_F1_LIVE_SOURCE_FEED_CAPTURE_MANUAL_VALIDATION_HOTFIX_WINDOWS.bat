@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0Install-F1-Live-Source-Feed-Capture-Manual-Validation-Hotfix.ps1"
pause
