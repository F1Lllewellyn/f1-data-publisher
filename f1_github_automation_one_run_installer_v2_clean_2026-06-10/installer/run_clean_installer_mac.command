#!/bin/bash
echo "F1 GitHub automation CLEAN installer"
echo "This will archive old F1 automation paths and install the new clean version."
read -p "Repo folder path: " REPO
python3 "$(dirname "$0")/install_f1_github_automation_clean.py" --repo "$REPO" --apply
