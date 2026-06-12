@echo off
setlocal enabledelayedexpansion

echo.
echo F1 Workbook/KPI Refresh Applier Installer
echo ---------------------------------------
echo This installs sandbox-only workflow/script files.
echo It does NOT overwrite the canonical workbook.
echo It does NOT alter Engine_2026-06-07_STABLE.
echo It does NOT delete old files.
echo.

set "DEFAULT_REPO=C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
set /p REPO_PATH=Repo path [press Enter for "%DEFAULT_REPO%"]:
if "%REPO_PATH%"=="" set "REPO_PATH=%DEFAULT_REPO%"

if not exist "%REPO_PATH%" (
  echo ERROR: Repo path not found: "%REPO_PATH%"
  exit /b 1
)

set "SRC=%~dp0.."
echo Installing into "%REPO_PATH%"

if not exist "%REPO_PATH%\scripts\workbook_kpi_refresh" mkdir "%REPO_PATH%\scripts\workbook_kpi_refresh"
if not exist "%REPO_PATH%\.github\workflows" mkdir "%REPO_PATH%\.github\workflows"
if not exist "%REPO_PATH%\configs\workbook_kpi_refresh" mkdir "%REPO_PATH%\configs\workbook_kpi_refresh"
if not exist "%REPO_PATH%\schemas\workbook_kpi_refresh" mkdir "%REPO_PATH%\schemas\workbook_kpi_refresh"
if not exist "%REPO_PATH%\docs\workbook_kpi_refresh" mkdir "%REPO_PATH%\docs\workbook_kpi_refresh"

copy /Y "%SRC%\scripts\apply_workbook_kpi_refresh_v1.py" "%REPO_PATH%\scripts\workbook_kpi_refresh\apply_workbook_kpi_refresh_v1.py" >nul
copy /Y "%SRC%\scripts\health_check_workbook_kpi_refresh_applier.py" "%REPO_PATH%\scripts\workbook_kpi_refresh\health_check_workbook_kpi_refresh_applier.py" >nul

copy /Y "%SRC%\.github\workflows\f1-workbook-kpi-refresh-safe-test-button.yml" "%REPO_PATH%\.github\workflows\f1-workbook-kpi-refresh-safe-test-button.yml" >nul
copy /Y "%SRC%\.github\workflows\f1-workbook-kpi-refresh-run-now-button.yml" "%REPO_PATH%\.github\workflows\f1-workbook-kpi-refresh-run-now-button.yml" >nul
copy /Y "%SRC%\.github\workflows\f1-workbook-kpi-refresh-scheduled.yml" "%REPO_PATH%\.github\workflows\f1-workbook-kpi-refresh-scheduled.yml" >nul

copy /Y "%SRC%\configs\workbook_kpi_refresh_policy_v1.json" "%REPO_PATH%\configs\workbook_kpi_refresh\workbook_kpi_refresh_policy_v1.json" >nul
copy /Y "%SRC%\schemas\sandbox_workbook_update_plan_schema_v1.json" "%REPO_PATH%\schemas\workbook_kpi_refresh\sandbox_workbook_update_plan_schema_v1.json" >nul
copy /Y "%SRC%\schemas\workbook_kpi_refresh_manifest_schema_v1.json" "%REPO_PATH%\schemas\workbook_kpi_refresh\workbook_kpi_refresh_manifest_schema_v1.json" >nul

copy /Y "%SRC%\README.md" "%REPO_PATH%\docs\workbook_kpi_refresh\README_Workbook_KPI_Refresh_Applier.md" >nul
copy /Y "%SRC%\WORKBOOK_KPI_REFRESH_APPLIER_DESIGN.md" "%REPO_PATH%\docs\workbook_kpi_refresh\WORKBOOK_KPI_REFRESH_APPLIER_DESIGN.md" >nul
copy /Y "%SRC%\SOURCE_TO_WORKBOOK_KPI_FLOW.md" "%REPO_PATH%\docs\workbook_kpi_refresh\SOURCE_TO_WORKBOOK_KPI_FLOW.md" >nul

echo.
echo Installed sandbox-only Workbook/KPI Refresh Applier files.
echo Next: open GitHub Desktop, review, commit, and push.
echo Then run "F1 Workbook KPI Refresh - Safe Test Button".
echo.
pause
