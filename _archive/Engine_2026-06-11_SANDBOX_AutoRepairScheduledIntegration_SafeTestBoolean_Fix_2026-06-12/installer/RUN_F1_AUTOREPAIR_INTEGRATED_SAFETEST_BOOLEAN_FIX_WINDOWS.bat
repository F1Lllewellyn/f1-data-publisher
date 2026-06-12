@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo F1 Session Auto-Repair Integrated Safe-Test Boolean Fix
echo.
set "DEFAULT_REPO=C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
set /p "REPO=Repo path [press Enter for %DEFAULT_REPO%]: "
if "%REPO%"=="" set "REPO=%DEFAULT_REPO%"

echo.
echo Installing into: "%REPO%"
if not exist "%REPO%" (
  echo ERROR: Repo path does not exist.
  exit /b 1
)

set "PAYLOAD=%~dp0..\payload"
if not exist "%PAYLOAD%" (
  echo ERROR: Payload folder not found next to installer.
  exit /b 1
)

xcopy "%PAYLOAD%\*" "%REPO%\" /E /I /Y >nul
if errorlevel 1 (
  echo ERROR: Copy failed.
  exit /b 1
)

echo.
echo Installed:
echo - scripts\session_data_processor\session_data_processor_loop_v1.py
echo.
echo Fix: Safe Test now treats promotion_allowed=false as the correct protected state.
echo.
echo Next: open GitHub Desktop, review changes, commit, and push.
echo Then run: F1 Session Auto-Repair Integrated - Safe Test Button
pause
endlocal
