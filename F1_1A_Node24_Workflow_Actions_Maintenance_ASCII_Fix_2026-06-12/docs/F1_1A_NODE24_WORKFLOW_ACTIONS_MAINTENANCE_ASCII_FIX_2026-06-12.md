# F1 1A Node 24 Workflow Actions Maintenance ASCII Fix - 2026-06-12

Verdict: Pass with warnings.

This corrected package fixes the prior installer parser failure by using an ASCII-only PowerShell installer and avoiding fragile markdown string construction.

Scope:
- Updates GitHub workflow action references only.
- Does not call command-line git.
- Does not touch stable engine logic.
- Does not touch workbook files.
- Does not touch forecast rows or forecast bundles.
- Does not alter prediction outputs.
- Does not alter promotion status.

Installer:
`installer/RUN_F1_1A_NODE24_WORKFLOW_ACTIONS_MAINTENANCE_ASCII_FIX_WINDOWS.bat`

After install, review the diff in GitHub Desktop, commit, and push.

Suggested commit message:
`chore: update workflow actions for Node 24 maintenance`
