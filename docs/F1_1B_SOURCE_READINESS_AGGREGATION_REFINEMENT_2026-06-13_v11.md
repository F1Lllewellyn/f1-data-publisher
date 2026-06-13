# F1 1B Source-Readiness Aggregation Refinement v11

Created UTC: 2026-06-13

## Purpose

This is a narrow 1B processor-lane patch. It improves the autonomous Session Data Processor Loop by making source-readiness aggregation session-aware, especially for Practice sessions.

## What changed

- Adds `scripts/session_data_processor/source_readiness_aggregation_v2.py`.
- Adds `configs/session_data_processor/source_readiness_aggregation_policy_v2.json`.
- Adds `scripts/ops/f1_1b_source_readiness_patch_validation_v1.py`.
- Patches `scripts/session_data_processor/session_data_processor_loop_v1.py` only enough to consume the aggregation result and publish `readiness_quality` / `source_needs_manual_review` fields.

## Key behavior

For Practice sessions:

- `starting_grid = 0` is expected-empty and non-blocking.
- `intervals = 0` is optional context and non-blocking.
- Core `laps`, `drivers`, `position`, and `weather` remain critical.
- If `laps = 0`, the session remains late/not ready.

## Governance

This patch does not alter `Engine_2026-06-07_STABLE`, canonical workbooks, stable prediction logic, experimental/sandbox model logic, or forecast promotion gates.

Forecast gate remains off until explicitly activated after clean source-backed validation.
