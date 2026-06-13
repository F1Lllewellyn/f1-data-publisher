@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title F1 Peak-Elite Repo Hygiene Installer v5 - CMD Safe
color 0A

set "REPOPATH=C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher"
set "LOG=%TEMP%\F1_PEAK_ELITE_HYGIENE_INSTALLER_V5_BOOTSTRAP.log"

echo ============================================================
echo  F1 PEAK-ELITE REPO HYGIENE INSTALLER v5 - CMD SAFE
echo ============================================================
echo.
echo Purpose:
echo   - remove generated Python cache files from the repo
echo   - patch the Peak-Elite control-room workflow so it will not
echo     re-commit __pycache__ or *.pyc files
echo   - add .gitignore hygiene entries
echo.
echo Target repo:
echo   %REPOPATH%
echo.
echo It will NOT intentionally modify Engine_2026-06-07_STABLE,
echo canonical workbooks, prediction model logic, or promotion state.
echo.
pause

> "%LOG%" echo F1 Peak-Elite Hygiene Installer v5 bootstrap started at %DATE% %TIME%
>> "%LOG%" echo Repo: %REPOPATH%

if not exist "%REPOPATH%\" (
  echo.
  echo ERROR: Repository folder not found:
  echo   %REPOPATH%
  >> "%LOG%" echo ERROR: repo path not found.
  goto :fail
)
if not exist "%REPOPATH%\.github\workflows\" (
  echo.
  echo ERROR: This does not look like the f1-data-publisher repo. Missing .github\workflows:
  echo   %REPOPATH%\.github\workflows
  >> "%LOG%" echo ERROR: workflows folder not found.
  goto :fail
)

set "WORKROOT=%TEMP%\F1_PeakElite_Hygiene_v5_%RANDOM%%RANDOM%"
set "B64=%WORKROOT%\payload.b64"
set "ZIP=%WORKROOT%\payload.zip"
set "EXPANDED=%WORKROOT%\expanded"

echo.
echo Running CMD-safe hygiene installer now...
echo Work folder: %WORKROOT%
echo.
>> "%LOG%" echo WorkRoot: %WORKROOT%

mkdir "%WORKROOT%" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Could not create work folder.
  >> "%LOG%" echo ERROR: could not create work folder.
  goto :fail
)

echo Extracting embedded payload text...
> "%B64%" (
  set "capture="
  for /f "usebackq delims=" %%A in ("%~f0") do (
    set "line=%%A"
    if "!line!"=="__END_F1_PAYLOAD__" set "capture="
    if defined capture echo(!line!
    if "!line!"=="__BEGIN_F1_PAYLOAD__" set "capture=1"
  )
)

for %%I in ("%B64%") do set "B64SIZE=%%~zI"
if "%B64SIZE%"=="0" (
  echo ERROR: Payload extraction failed. Base64 file is empty.
  >> "%LOG%" echo ERROR: empty b64 payload.
  goto :fail
)
>> "%LOG%" echo Payload b64 bytes: %B64SIZE%

echo Decoding embedded payload zip...
certutil -f -decode "%B64%" "%ZIP%" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: Could not decode embedded payload. See:
  echo   %LOG%
  goto :fail
)

echo Expanding payload zip...
mkdir "%EXPANDED%" >nul 2>&1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%EXPANDED%' -Force" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: Could not expand payload zip. See:
  echo   %LOG%
  goto :fail
)

set "PS1FILE="
for /f "delims=" %%P in ('dir /s /b "%EXPANDED%\Install-F1-Peak-Elite-Hygiene-v5.ps1" 2^>nul') do set "PS1FILE=%%P"
if not defined PS1FILE (
  for /f "delims=" %%P in ('dir /s /b "%EXPANDED%\*Install-F1-Peak-Elite-Hygiene-v5.ps1" 2^>nul') do set "PS1FILE=%%P"
)
if not defined PS1FILE (
  echo ERROR: Internal hygiene installer was not found after extraction. See:
  echo   %LOG%
  goto :fail
)

echo Launching internal hygiene installer:
echo   %PS1FILE%
echo.
>> "%LOG%" echo Internal PS1: %PS1FILE%

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS1FILE%" -RepoPath "%REPOPATH%"
set "EXITCODE=%ERRORLEVEL%"
>> "%LOG%" echo Internal installer exit code: %EXITCODE%

echo.
echo ============================================================
echo  Hygiene installer finished with exit code: %EXITCODE%
echo ============================================================
echo.

set "REPORT="
if exist "%TEMP%\F1_PEAK_ELITE_HYGIENE_INSTALL_REPORT_LAST_RUN.txt" set "REPORT=%TEMP%\F1_PEAK_ELITE_HYGIENE_INSTALL_REPORT_LAST_RUN.txt"
if not defined REPORT (
  for /f "delims=" %%R in ('dir /s /b "%WORKROOT%\INSTALL_REPORT_LAST_RUN.txt" "%WORKROOT%\*INSTALL_REPORT_LAST_RUN.txt" 2^>nul') do set "REPORT=%%R"
)
if defined REPORT (
  echo Opening install report...
  copy /y "%REPORT%" "%~dp0INSTALL_REPORT_LAST_RUN.txt" >nul 2>&1
  start "" notepad "%REPORT%"
) else (
  echo No install report was found. Bootstrap log:
  echo   %LOG%
  start "" notepad "%LOG%"
)

echo.
echo Next:
echo   1. Commit and push these local changes with GitHub Desktop or GitHub web.
echo   2. Run: F1 Peak Elite Control Room - One Click v1
echo   3. Use: operation=full_safe_chain, commit_outputs=true, run_forecast_gate=false
echo.
pause
exit /b %EXITCODE%

:fail
echo.
echo ============================================================
echo  HYGIENE INSTALLER STOPPED BEFORE CHANGING THE REPO
echo ============================================================
echo Bootstrap log:
echo   %LOG%
echo.
if exist "%LOG%" start "" notepad "%LOG%"
pause
exit /b 1

__BEGIN_F1_PAYLOAD__
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
jGQsTdJ4Zj9QwKNDb433+LKTcTkWxSzCvAA7Klcar41Qdv6aDczG1or3y/uFCaSykxWBLrStikAg
fd1CJll1Kjr8czjqnS35ov0UW1dFa02/rEjU2uX6/Q3dkvYHGLAhBmzUH9DjwWnvpH6JbxyRu4HM
OroYonYtvFki2dkmweSBx4/hUUYc9kGYBxrIZ7e/JrWy7GBB4ARKWyUCq2RC3iACEYbFvPqcCm42
JvB7WRyr0ON4glWEk9saQuX2UV29ZiZnH2keHqhwsLDnQX5e/lGaHZhWvc8yvLh/wZf9s+NDaex1
nzShHZqkekoVRwGOv4yaNwuDhgPmH1BLAQIUAxQAAAAIAHsHzVyWKc13JgIAAJkDAAA/AAAAAAAA
AAAAAACkgQAAAABGMV9QZWFrX0VsaXRlX0h5Z2llbmVfSW5zdGFsbGVyX3Y1X0lOVEVSTkFML1BB
VENIX01BTklGRVNULmpzb25QSwECFAMUAAAACAB7B81ctXohxoQAAACpAAAAQQAAAAAAAAAAAAAA
pIGDAgAARjFfUGVha19FbGl0ZV9IeWdpZW5lX0luc3RhbGxlcl92NV9JTlRFUk5BTC9SRUFETUVf
U1RBUlRfSEVSRS50eHRQSwECFAMUAAAACAB7B81cvCkzoU4IAABsGgAAZgAAAAAAAAAAAAAApIFm
AwAARjFfUGVha19FbGl0ZV9IeWdpZW5lX0luc3RhbGxlcl92NV9JTlRFUk5BTC9faW50ZXJuYWxf
ZG9fbm90X29wZW4vSW5zdGFsbC1GMS1QZWFrLUVsaXRlLUh5Z2llbmUtdjUucHMxUEsBAhQDFAAA
AAgAewfNXKhJintXAgAAPwQAAGEAAAAAAAAAAAAAAKSBOAwAAEYxX1BlYWtfRWxpdGVfSHlnaWVu
ZV9JbnN0YWxsZXJfdjVfSU5URVJOQUwvcGF5bG9hZC9kb2NzL0YxX1BFQUtfRUxJVEVfUkVQT19I
WUdJRU5FXzIwMjYtMDYtMTMubWRQSwECFAMUAAAACAB7B81cg7fUNr0GAADMEwAAcQAAAAAAAAAA
AAAApIEODwAARjFfUGVha19FbGl0ZV9IeWdpZW5lX0luc3RhbGxlcl92NV9JTlRFUk5BTC9wYXls
b2FkLy5naXRodWIvd29ya2Zsb3dzL2YxLXBlYWstZWxpdGUtY29udHJvbC1yb29tLW9uZS1jbGlj
ay12MS55bWxQSwUGAAAAAAUABQCeAgAAWhYAAAAA
__END_F1_PAYLOAD__
