@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-F1-1A-GitHub-LongPath-Cleanup-Final-Fix.ps1"
pause
