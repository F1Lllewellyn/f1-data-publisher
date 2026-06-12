@echo off
setlocal EnableExtensions
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%install.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo INSTALL CHECK PASSED. Open GitHub Desktop, commit, and push.
) else (
  echo INSTALL CHECK FAILED. Do not commit yet.
)
echo.
pause
exit /b %RC%
