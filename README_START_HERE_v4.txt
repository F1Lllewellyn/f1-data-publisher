F1 Peak-Elite System Installer v4 CMD-safe

Double-click only:
  1_DOUBLE_CLICK_ME_INSTALL_F1_PEAK_ELITE_SYSTEM_v4_CMD_SAFE.cmd

This version fixes the two Windows installer failures seen in v2/v3. It does not use a huge encoded-command and does not depend on a sibling .ps1 file.

It uses Windows built-ins only: cmd.exe, certutil, powershell.exe, and git/gh only if already installed. No local Python required.

Target repo:
  C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher

It does not intentionally modify Engine_2026-06-07_STABLE, canonical workbooks, prediction model logic, or promotion state.
