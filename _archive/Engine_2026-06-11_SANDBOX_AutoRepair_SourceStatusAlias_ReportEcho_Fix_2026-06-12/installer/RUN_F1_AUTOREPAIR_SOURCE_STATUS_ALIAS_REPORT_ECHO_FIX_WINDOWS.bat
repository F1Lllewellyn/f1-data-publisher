@echo off
setlocal enabledelayedexpansion
echo F1 Auto-Repair Source Status Alias + Report Echo Fix
echo.
set "DEFAULT_REPO=C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
set /p "REPO=Repo path [press Enter for %DEFAULT_REPO%]: "
if "%REPO%"=="" set "REPO=%DEFAULT_REPO%"

if not exist "%REPO%" (
  echo ERROR: Repo path not found: "%REPO%"
  exit /b 1
)

set "SCRIPT_DIR=%~dp0"
set "PKG_ROOT=%SCRIPT_DIR%.."
set "PAYLOAD=%PKG_ROOT%\payload"

echo Copying payload into:
echo "%REPO%"
echo.

xcopy "%PAYLOAD%\*" "%REPO%\" /E /I /Y >nul
if errorlevel 1 (
  echo ERROR: Copy failed.
  exit /b 1
)

echo.
echo Installed Auto-Repair source-status alias and report-echo fix.
echo.
echo Next:
echo 1. Open GitHub Desktop.
echo 2. Review changed files.
echo 3. Commit and push.
echo 4. Run: F1 Auto-Repair - Run Now Button
echo.
pause
endlocal
