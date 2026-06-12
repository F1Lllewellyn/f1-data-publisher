@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0Install-F1-1A-Cumulative-Validation-Hotfix.ps1"
endlocal
