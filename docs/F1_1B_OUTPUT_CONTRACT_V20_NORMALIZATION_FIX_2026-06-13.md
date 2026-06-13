# F1 1B Output Contract v20 Normalization Fix

Created UTC: 2026-06-13

This narrow patch fixes the remaining v19 inconsistency where the output-contract report could show `readiness_quality=usable_with_optional_context_gaps` while still carrying stale `source_status=needs_manual_review` and `workbook_source_status=needs_manual_review`.

## Fixes

- Normalizes final source status to `clean` when readiness quality and source-backed evidence show the processor state is usable and no critical source gap remains.
- Normalizes final workbook handoff status to `clean` when a sandbox workbook/artifact is available and the source state is usable.
- Preserves blocking behavior for true critical source gaps such as missing laps, position, weather, race-control, session result, drivers, or sessions.
- Keeps forecast gate off and promotion disallowed.

## Safety

No stable engine changes. No canonical workbook overwrite. No model promotion. No `.git` access. No cleanup/delete scanning.
