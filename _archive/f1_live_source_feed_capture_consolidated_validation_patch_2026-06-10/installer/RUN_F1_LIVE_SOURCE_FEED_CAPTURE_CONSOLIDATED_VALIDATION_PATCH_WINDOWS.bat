@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0Install-F1-Live-Source-Feed-Capture-Consolidated-Validation-Patch.ps1"
pause
