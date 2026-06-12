@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Install-F1-Session-Data-Processor-Loop.ps1"
if errorlevel 1 (
  echo.
  echo Install failed. Copy the error above and send it back.
  pause
  exit /b 1
)
echo.
echo Install finished. Open GitHub Desktop, commit, and push.
pause
