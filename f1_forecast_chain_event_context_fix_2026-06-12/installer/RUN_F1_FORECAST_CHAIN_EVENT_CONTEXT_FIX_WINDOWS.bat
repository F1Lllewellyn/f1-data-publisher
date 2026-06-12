@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-F1-Forecast-Chain-Event-Context-Fix.ps1"
pause
