# Immutable Forecast Ledger Sandbox Write Rehearsal

Checkpoint for Enhancement 01F.

Goal: rehearse how a ledger entry would be appended in sandbox only. This does not activate production or write a canonical ledger.

Rehearsal rules:
- input is a validated sandbox forecast entry
- output is a new sandbox-only append record
- prior entries are not mutated
- governance flags must stay conservative
- replay/scoring consumes the sandbox record later

Status: rehearsal spec only. No live storage, no canonical write, no activation, no prediction output.
