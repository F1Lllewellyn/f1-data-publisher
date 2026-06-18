# v33D Sandbox-Live Source Quality Review

v33D is Roadmap Step 4 of 10: sandbox-live source quality review.

It consumes v33C sandbox source evidence and classifies whether the pulled evidence is ready, degraded, or blocked before any processor execution.

## Scope

- Reviews existing v33C source evidence only.
- Performs no live fetch.
- Runs no FastF1, FIA, Formula1.com, workbook, prediction, fantasy, notification, or production automation step.
- Writes only health and sandbox quality-review JSON artifacts.

## Review dimensions

v33D checks:

- completeness of required OpenF1 sources;
- optional-source missing/empty/failed classification;
- timestamp presence, parseability, and source-age threshold;
- session-key alignment between gate metadata and manifest URLs;
- source health from `ok`, HTTP status, row counts, and byte counts;
- v33C guardrail flags remain off/protected.

## Decision states

- `SANDBOX_SOURCE_QUALITY_READY`: required sources are present, healthy, nonempty, and aligned with no warnings.
- `SANDBOX_SOURCE_QUALITY_DEGRADED`: required sources pass, but optional sources or non-blocking warnings exist.
- `SANDBOX_SOURCE_QUALITY_BLOCKED`: required source, guardrail, timestamp, or session-alignment blocker exists.

## Next step

If v33D is READY or DEGRADED, the next roadmap step is v33E sandbox-live processor execution.

If v33D is BLOCKED, resolve source quality blockers before v33E.

## Guardrails

The following remain disabled:

- production automation;
- canonical workbook writes;
- production Forecast Bundle Ledger writes;
- Race Predictions refresh;
- Fantasy Predictions refresh;
- notification send;
- model promotion;
- activation.
