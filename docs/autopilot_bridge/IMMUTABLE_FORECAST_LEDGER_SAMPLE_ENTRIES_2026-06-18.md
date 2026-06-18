# Immutable Forecast Ledger Sample Entries

Checkpoint for Enhancement 01D.

Sample types:

- sandbox_preview: dry-run forecast candidate; no production write
- candidate_forecast: ready for operator review; still not production
- approved_forecast: operator-approved entry; still must obey activation gates
- revision: new entry that references previous_entry_hash

Sample entries must record source_readiness, stable_context, experimental_context, forecast_payload, human_override, governance_flags, and hash chain fields.

Status: sample shape only. No live ledger, no canonical write, no activation.
