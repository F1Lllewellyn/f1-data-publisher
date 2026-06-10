@echo off
echo F1 OpenF1 Post-Race Empty Feature Validator Hotfix
echo This lets post-race runs pass with warnings if extraction succeeds but feature rows are zero.
echo.
set /p REPO="Paste ONLY the repo folder path here, then press Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_postrace_empty_feature_hotfix.ps1" -Repo "%REPO%" -Apply
echo.
pause
