@echo off
echo F1 GitHub automation CLEAN installer
echo This will archive old F1 automation paths and install the new clean version.
set /p REPO="Repo folder path: "
python "%~dp0install_f1_github_automation_clean.py" --repo "%REPO%" --apply
pause
