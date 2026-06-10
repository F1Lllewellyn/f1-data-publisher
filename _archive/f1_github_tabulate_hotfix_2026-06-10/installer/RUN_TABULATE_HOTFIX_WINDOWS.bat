@echo off
echo F1 GitHub OpenF1 tabulate hotfix
echo This fixes the workflow failure: "Import tabulate failed".
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_tabulate_hotfix.ps1" -Repo "%REPO%" -Apply
echo.
pause
