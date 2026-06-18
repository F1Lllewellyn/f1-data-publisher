# Immutable Forecast Ledger Foundation

PR-only foundation for Enhancement 01. This documents the audit spine for forecast, fantasy, report, override, and later scoring decisions.

Rules:
- append-only; revisions are new entries
- each entry has SHA-256 content hash
- stable and experimental context are recorded separately
- source readiness is recorded before serious outputs
- no DRS assumptions for 2026 forecasts
- production writes, canonical workbook writes, notifications, model promotion, and stable-engine changes remain OFF unless separately approved

Minimum future entry fields:
schema_version, ledger_type, entry_id, generated_utc, event_scope, source_readiness, stable_context, experimental_context, forecast_payload, human_override, governance_flags, previous_entry_hash, entry_hash.

Hash rule:
entry_hash = SHA-256(canonical JSON without entry_hash), with sorted object keys and preserved array order.

Future integration:
source readiness -> sandbox pull -> quality review -> processor -> workbook reflection -> sandbox bundle snapshot -> race/fantasy readiness -> operator decision -> immutable ledger entry -> post-event scoring.

Non-goal:
This PR does not add live storage, does not write the canonical workbook, does not activate automation, does not change Engine_2026-06-07_STABLE, and does not merge automatically.
