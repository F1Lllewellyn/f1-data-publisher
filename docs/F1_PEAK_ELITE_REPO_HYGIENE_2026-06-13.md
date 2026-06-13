# F1 Peak-Elite Repo Hygiene Patch v5

Created: 2026-06-13

Purpose: remove generated Python cache files from the repository and prevent future Peak-Elite workflow commits from reintroducing them.

Scope:
- Add/confirm `.gitignore` entries for generated Python cache files.
- Remove local `__pycache__` directories and `*.pyc`, `*.pyo`, `*.pyd` files, after backing them up under `_archive`.
- Patch `.github/workflows/f1-peak-elite-control-room-one-click-v1.yml` so GitHub Actions cleans Python cache files before staging and committing outputs.

Protected boundaries:
- Does not modify `Engine_2026-06-07_STABLE`.
- Does not modify canonical workbooks.
- Does not promote experimental logic.
- Does not alter prediction model logic.
- Does not delete source packages or reports.

After installing and committing/pushing, run:

`F1 Peak Elite Control Room - One Click v1`

with:

- `operation=full_safe_chain`
- `commit_outputs=true`
- `run_forecast_gate=false`

Then confirm the next committed output removes any tracked `scripts/ops/__pycache__/*.pyc` files and does not re-add them.
