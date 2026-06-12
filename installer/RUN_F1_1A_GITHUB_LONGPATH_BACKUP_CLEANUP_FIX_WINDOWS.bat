@echo off
setlocal
echo F1 1A GitHub Long-Path Backup Cleanup Fix
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-F1-1A-GitHub-LongPath-Backup-Cleanup-Fix.ps1"
echo.
pause
