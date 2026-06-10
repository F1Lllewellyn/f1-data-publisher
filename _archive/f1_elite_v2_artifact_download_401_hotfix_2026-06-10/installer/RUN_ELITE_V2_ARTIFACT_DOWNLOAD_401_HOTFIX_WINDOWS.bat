@echo off
echo F1 Elite v2 Artifact Download 401 Hotfix
echo This fixes the Elite workflow artifact download authentication redirect failure.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_elite_v2_artifact_download_401_hotfix.ps1" -Repo "%REPO%" -Apply
echo.
pause
