# V30Q R2 Live Source Hardening + Failure Taxonomy Hotfix

This hotfix corrects the v30Q taxonomy script syntax defect in the final optional log-write branch.

## Scope

- Replaces `scripts/autopilot/session_live_source_failure_taxonomy_v30q.mjs`.
- Refreshes `scripts/autopilot/session_live_source_hardening_policy_v30q.json` schema metadata.
- Keeps the live-source hardening layer dry-run only.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Live fetch is not performed.

## Validation

The script is expected to pass:

- Node syntax check.
- Empty dry-run contract.
- Blocking source fixture.
- Degraded source with fallback fixture.
