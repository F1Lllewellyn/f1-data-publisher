@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo F1 Dashboard Connector Missing-Scripts Repair Installer
set "DEFAULT_REPO=C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
set /p "REPO=Repo path [press Enter for %DEFAULT_REPO%]: "
if "%REPO%"=="" set "REPO=%DEFAULT_REPO%"

echo Using repo: "%REPO%"
if not exist "%REPO%" (
  echo ERROR: Repo path does not exist.
  pause
  exit /b 1
)

set "SRC=%~dp0"

for %%D in ("%REPO%\.github\workflows" "%REPO%\scripts\dashboard_connector" "%REPO%\configs\dashboard_connector" "%REPO%\schemas\dashboard_connector" "%REPO%\docs") do (
  if not exist %%~D mkdir %%~D
)

echo Copying dashboard connector workflows and scripts...
copy /Y "%SRC%.github\workflows\f1-forecast-fantasy-readiness-dashboard-safe-test.yml" "%REPO%\.github\workflows\" >nul
copy /Y "%SRC%.github\workflows\f1-forecast-fantasy-readiness-dashboard-run-now.yml" "%REPO%\.github\workflows\" >nul
copy /Y "%SRC%.github\workflows\f1-forecast-fantasy-readiness-dashboard-scheduled.yml" "%REPO%\.github\workflows\" >nul
copy /Y "%SRC%scripts\dashboard_connector\health_check_dashboard_connector_v1.py" "%REPO%\scripts\dashboard_connector\" >nul
copy /Y "%SRC%scripts\dashboard_connector\publish_forecast_fantasy_readiness_dashboards_v1.py" "%REPO%\scripts\dashboard_connector\" >nul
copy /Y "%SRC%configs\dashboard_connector\dashboard_connector_policy_v1.json" "%REPO%\configs\dashboard_connector\" >nul
copy /Y "%SRC%schemas\dashboard_connector\dashboard_state_schema_v1.json" "%REPO%\schemas\dashboard_connector\" >nul
copy /Y "%SRC%docs\FORECAST_FANTASY_READINESS_DASHBOARD_CONNECTOR_DESIGN.md" "%REPO%\docs\" >nul
copy /Y "%SRC%docs\SOURCE_TO_FORECAST_FANTASY_DASHBOARD_FLOW.md" "%REPO%\docs\" >nul
copy /Y "%SRC%README.md" "%REPO%\docs\README_FORECAST_FANTASY_READINESS_DASHBOARD_CONNECTOR.md" >nul

echo.
echo Verifying required files now exist in repo...
set "FAIL=0"
for %%F in (^
"%REPO%\.github\workflows\f1-forecast-fantasy-readiness-dashboard-safe-test.yml" ^
"%REPO%\.github\workflows\f1-forecast-fantasy-readiness-dashboard-run-now.yml" ^
"%REPO%\.github\workflows\f1-forecast-fantasy-readiness-dashboard-scheduled.yml" ^
"%REPO%\scripts\dashboard_connector\health_check_dashboard_connector_v1.py" ^
"%REPO%\scripts\dashboard_connector\publish_forecast_fantasy_readiness_dashboards_v1.py" ^
"%REPO%\configs\dashboard_connector\dashboard_connector_policy_v1.json" ^
"%REPO%\schemas\dashboard_connector\dashboard_state_schema_v1.json"^
) do (
  if not exist %%~F (
    echo MISSING: %%~F
    set "FAIL=1"
  ) else (
    echo OK: %%~nxF
  )
)

echo.
if "%FAIL%"=="1" (
  echo INSTALL CHECK FAILED. Do not commit yet.
  pause
  exit /b 1
)

echo INSTALL CHECK PASSED.
echo Next: open GitHub Desktop, make sure the scripts/dashboard_connector files are included, then commit and push.
echo Then run: F1 Forecast/Fantasy Readiness Dashboard - Safe Test Button
pause
endlocal
