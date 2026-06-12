@echo off
setlocal enabledelayedexpansion

echo.
echo F1 Auto-Repair Orchestrator Installer
echo ------------------------------------
echo This installs sandbox-only self-recovery workflow/script files.
echo It does NOT overwrite the canonical workbook.
echo It does NOT alter Engine_2026-06-07_STABLE.
echo It does NOT promote any model layer.
echo It does NOT delete old files.
echo.

set "DEFAULT_REPO=C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
set /p REPO_PATH=Repo path [press Enter for "%DEFAULT_REPO%"]: 
if "%REPO_PATH%"=="" set "REPO_PATH=%DEFAULT_REPO%"

if not exist "%REPO_PATH%" (
  echo ERROR: Repo path not found: "%REPO_PATH%"
  exit /b 1
)

set "SRC=%~dp0..\payload"
echo Installing into "%REPO_PATH%"

if not exist "%REPO_PATH%\scripts\autorepair" mkdir "%REPO_PATH%\scripts\autorepair"
if not exist "%REPO_PATH%\configs\autorepair" mkdir "%REPO_PATH%\configs\autorepair"
if not exist "%REPO_PATH%\schemas\autorepair" mkdir "%REPO_PATH%\schemas\autorepair"
if not exist "%REPO_PATH%\.github\workflows" mkdir "%REPO_PATH%\.github\workflows"
if not exist "%REPO_PATH%\docs\autorepair" mkdir "%REPO_PATH%\docs\autorepair"

copy /Y "%SRC%\scripts\autorepair\f1_autorepair_orchestrator_v1.py" "%REPO_PATH%\scripts\autorepair\f1_autorepair_orchestrator_v1.py" >nul
copy /Y "%SRC%\configs\autorepair\repair_catalog_v1.json" "%REPO_PATH%\configs\autorepair\repair_catalog_v1.json" >nul
copy /Y "%SRC%\schemas\autorepair\autorepair_report_v1.schema.json" "%REPO_PATH%\schemas\autorepair\autorepair_report_v1.schema.json" >nul

copy /Y "%SRC%\.github\workflows\f1-autorepair-safe-test-button-v1.yml" "%REPO_PATH%\.github\workflows\f1-autorepair-safe-test-button-v1.yml" >nul
copy /Y "%SRC%\.github\workflows\f1-autorepair-run-now-button-v1.yml" "%REPO_PATH%\.github\workflows\f1-autorepair-run-now-button-v1.yml" >nul
copy /Y "%SRC%\.github\workflows\f1-autorepair-scheduled-session-workbook-recovery-v1.yml" "%REPO_PATH%\.github\workflows\f1-autorepair-scheduled-session-workbook-recovery-v1.yml" >nul

copy /Y "%~dp0..\README.md" "%REPO_PATH%\docs\autorepair\README_AutoRepair_Orchestrator.md" >nul
copy /Y "%~dp0..\AUTO_REPAIR_ORCHESTRATOR_DESIGN.md" "%REPO_PATH%\docs\autorepair\AUTO_REPAIR_ORCHESTRATOR_DESIGN.md" >nul
copy /Y "%~dp0..\SESSION_TO_WORKBOOK_RECOVERY_FLOW.md" "%REPO_PATH%\docs\autorepair\SESSION_TO_WORKBOOK_RECOVERY_FLOW.md" >nul

echo.
echo Installed sandbox-only Auto-Repair Orchestrator files.
echo Next: open GitHub Desktop, review, commit, and push.
echo Then run "F1 Auto-Repair - Safe Test Button".
echo.
pause
