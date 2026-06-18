# Immutable Forecast Ledger Integration Checkpoint

Checkpoint for Enhancement 01E.

Target flow:
source readiness -> sandbox source pull -> quality review -> processor -> workbook reflection -> sandbox bundle snapshot -> race/fantasy readiness -> operator decision -> immutable ledger entry -> post-event scoring.

Integration rules:
- ledger entry must not precede source readiness or forecast gates
- stable and experimental context must be recorded separately
- overrides must be explicit and auditable
- scoring consumes ledger entries later; scoring does not mutate prior entries

Status: map only. No live writer, no activation, no prediction output.
