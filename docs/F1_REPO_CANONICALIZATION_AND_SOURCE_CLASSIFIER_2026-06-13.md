# F1 Repo Canonicalization + Source-Readiness Classifier Upgrade v8

Created: 2026-06-13

## Scope

This patch combines two controlled improvements:

1. Repository canonicalization v1.
2. Source-readiness classifier v2.

## Repository canonicalization boundary

This is not a purge. The automation deletes only generated Python bytecode/cache files:

- `__pycache__/`
- `*.pyc`
- `*.pyo`
- `*.pyd`

Everything else is inventoried and classified. Legacy installers, patch payloads, reports, archives, workbooks, forecast bundles, source artifacts, and model files are kept. The canonicalization output creates a Phase 2 review plan before any deeper archive move.

## Source-readiness classifier upgrade

The session processor now applies session-aware source classification:

- Practice sessions do not require `starting_grid`.
- Practice `intervals`, `pit`, `stints`, and uneventful `race_control` can be optional-empty rather than manual-review blockers.
- Qualifying does not require `starting_grid` as a strict source.
- Race/Sprint sessions keep stricter treatment for `starting_grid` and `intervals`.
- Classifier output remains compatible with the existing v1 statuses: `clean`, `partial`, `late`, `conflicting`, `needs_manual_review`.

## Protected boundaries

This patch does not intentionally touch:

- `Engine_2026-06-07_STABLE`
- canonical workbook files
- stable prediction logic
- experimental promotion state
- model-ranking logic
- forecast gate promotion rules

Forecast gate remains off until source/workbook states are clean and explicitly approved.
