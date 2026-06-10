# F1 Season Archive Retention Policy

## Problem

GitHub Actions artifacts are useful for workflow handoff and recent debugging, but they are not the long-term source of truth. Artifact retention is capped by repository/organization/enterprise settings.

## Policy

Long-term season data should be preserved as compact GitHub Release assets.

## What to archive long-term

- Elite Weekend Engine v2 outputs
- Workbook/control-room bridge outputs
- Dry forecast cycle outputs
- Locked forecast ledgers
- Source readiness history
- Reliability warning history
- DNF_ALL precursor history
- Fantasy risk history
- Validation summaries
- Manifests

## What not to archive by default

- Raw high-frequency OpenF1 `car_data`
- Raw high-frequency OpenF1 `location`
- Full raw historical parquet payloads

Raw snapshots should only be archived for:
- season-opening baseline
- major schema change
- end-of-season full historical extract
- forensic race-weekend deep dive

## Guardrails

- Public/proxy data only.
- No private/internal team sensor assumptions.
- No automatic stable rank changes.
- 2026 no-DRS rule preserved.
