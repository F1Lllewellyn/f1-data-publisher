@echo off
set /p REPOPATH=Paste your local f1-data-publisher repo path: 
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-F1-Forecast-Bundle-Locker-Scheduler-Guard-Hotfix.ps1" -RepoPath "%REPOPATH%"
pause
