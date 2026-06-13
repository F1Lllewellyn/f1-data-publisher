# F1 1B Output Contract v19 Wiring Fix

Created UTC: 2026-06-13

This narrow patch fixes the v16 output-contract wiring issue. It keeps the existing workflow name/file for continuity but updates the implementation to v19 behavior.

## Fixes

- Prefers the newest clean / source-backed readiness dashboard state over stale blocked manifests.
- Scores candidate source and workbook manifests by readiness quality rather than filesystem modification time alone.
- Writes `latest/1b_output_contract/input_selection_report.json` so every run proves which inputs it consumed.
- Makes the GitHub Actions commit step tolerate optional missing files such as `latest/last_good_state.json`.
- Keeps forecast gate off and promotion disallowed.

## Safety

No stable engine changes. No canonical workbook overwrites. No model promotion. No .git writes. No cleanup or delete scan.
