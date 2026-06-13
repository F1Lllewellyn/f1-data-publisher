# F1 Peak-Elite Long-Path Recovery and Hygiene Patch v6

Created: 2026-06-13

Purpose: recover from the v5 hygiene-installer mistake where generated Python bytecode was backed up inside `_archive`, creating excessively long paths that GitHub Desktop/Git could not stat during merge/push.

Scope:
- Deletes only generated Python cache files and the bad hygiene-cache backup directories created by v5.
- Keeps the useful v5 `.gitignore` and workflow hygiene idea.
- Patches the Peak-Elite control-room workflow so GitHub Actions removes `__pycache__` and bytecode before staging/committing outputs.
- Attempts to enable `core.longpaths=true` if Git is available through PATH, GitHub Desktop, or Program Files.

Protected boundaries:
- Does not modify `Engine_2026-06-07_STABLE`.
- Does not modify canonical workbooks.
- Does not promote experimental logic.
- Does not alter prediction model logic.
- Does not delete source packages, reports, workbooks, model artifacts, or forecast bundles.

After installing:
1. Commit and push the changed/deleted files with GitHub Desktop or the GitHub UI.
2. Run `F1 Peak Elite Control Room - One Click v1` with `operation=full_safe_chain`, `commit_outputs=true`, `run_forecast_gate=false`.
