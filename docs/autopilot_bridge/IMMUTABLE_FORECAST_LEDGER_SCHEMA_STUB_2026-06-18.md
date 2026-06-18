# Immutable Forecast Ledger Schema Stub — Enhancement 01B

Purpose: define the minimum schema contract for future immutable forecast ledger entries.

Required fields:
- schema_version
- ledger_type
- entry_id
- generated_utc
- event_scope
- source_readiness
- stable_context
- experimental_context
- forecast_payload
- human_override
- governance_flags
- previous_entry_hash
- entry_hash

Guardrails:
- append-only; revisions are new entries
- hash must be SHA-256 of canonical JSON without entry_hash
- stable and experimental context must remain separate
- production writes, canonical workbook writes, notifications, model promotion, and stable-engine changes remain OFF unless separately approved

Status: schema stub only. No writer, no live storage, no production activation.
