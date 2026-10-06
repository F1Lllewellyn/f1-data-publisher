# DR-002 pre-2B-7I3 — Outcome-boundary workflow identity composability

Work order: [F1-WO-DR002-PRE2B7I3-001 / Issue #188](https://github.com/F1Lllewellyn/f1-data-publisher/issues/188)  
Recorded: 2026-10-06  
Result: implementation and focused offline verification PASS; no live workflow run.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Provenance-truth repair

The outcome-boundary shadow wrapper now reuses the accepted lock-wrapper `validate_workflow_ref` semantics. It derives the actual caller workflow path from the validated `workflow_ref` rather than requiring or recording the direct outcome workflow path unconditionally.

A caller is accepted only when its workflow ref:

- identifies the explicitly supplied repository;
- uses the explicitly supplied ref;
- has a normalized path directly under `.github/workflows/`;
- has one non-empty workflow filename ending in `.yml` or `.yaml`; and
- contains no traversal, nesting, outside-workflow path, malformed identity, repository mismatch, or ref mismatch.

The outcome execution manifest records that derived path with the exact caller-supplied workflow ref and display name, plus the validated repository, ref, head, run, and attempt. Same-run lock verification requires the lock manifest to contain that same actual caller identity.

Direct execution remains truthful for `.github/workflows/dr002-outcome-boundary-shadow-pilot.yml`. A future composed synthetic call from `.github/workflows/dr002-revision-shadow-pilot.yml` is also representable truthfully. The direct outcome identity cannot be substituted for a revision caller, and the revision identity cannot be substituted for a direct caller.

## Preserved mechanics and trust ceiling

This repair does not change the fixed synthetic outcome bytes, source-capture construction, unchanged Gate 2B-4 outcome-boundary constructor, timing rules, payload or receipt hashing, evidence set, report bytes for equivalent clocks, or false trust flags.

Direct and composed offline fixtures produce byte-identical:

- `synthetic_outcome_payload.json`;
- `outcome_source_capture_receipt.json`;
- `outcome_boundary_receipt.json`; and
- `outcome_boundary_report.md`.

Their outcome manifests differ only in the truthful caller workflow identity and the consequent hash of the identity-bearing same-run lock manifest. No revision receipt, engine receipt, network caller, production dispatch, production locker, repository write, or fabricated verified binding was added.

Historical I2 evidence remains unchanged at its pinned run head and blob. No workflow was dispatched or rerun.

## Focused verification

The focused outcome-boundary suite and cheap Python syntax validation pass. Coverage includes:

- direct outcome workflow identity accepted and recorded;
- future revision-workflow identity accepted and recorded;
- same-run lock identity equality with the actual caller;
- rejection of direct/revision identity substitution;
- rejection of repository mismatch, ref mismatch, malformed refs, traversal, outside-workflow paths, nested paths, empty filenames, and non-YAML filenames;
- unchanged run, head, and attempt validation;
- byte-identical direct/composed outcome evidence and matching receipt/hash semantics;
- unchanged false trust ceiling and absence of revision or engine receipts;
- absence of workflow, network, production, or repository-write capability; and
- unchanged declared dependency blobs.

Verified preserved dependencies:

| Path | Git blob |
|---|---|
| `.github/workflows/dr002-outcome-boundary-shadow-pilot.yml` | `5ebe0dcaed10583bacd56687bd92d971f561f680` |
| `docs/DR002_PRE2B7I2_LIVE_GITHUB_ATTESTED_OUTCOME_BOUNDARY_SHADOW_2026-10-06.md` | `df1b309b185e55300eedad7889971b1f8cc46d4f` |
| `scripts/forecast_bundles/dr002_forecast_lock_shadow_pilot_v1.py` | `1ef04022041c7dcf625ae10c051c23b35ed72a9d` |
| `scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py` | `064d93ee5ae30354590a3fb95be598c5fe8b3b9a` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

## Claim ceiling

This Work Result proves only that the accepted outcome-boundary shadow wrapper can truthfully represent the actual executing workflow identity in direct and future composed synthetic shadow execution while preserving accepted I2 mechanics.

It does not prove a new live run, revision capture, revision completeness, observation completeness, authenticated clocks, production enforcement, blind eligibility, predictive accuracy, DR-002 activation, or promotion.

## Checkpoint

```text
outcome_boundary_workflow_identity_composable: true
direct_outcome_workflow_identity_preserved: true
future_revision_workflow_identity_truthful: true
historical_i2_evidence_rewritten: false
outcome_boundary_mechanics_modified: false
trust_ceiling_modified: false
live_workflow_run_executed: false
revision_proof_completed: false
observation_completeness_proven: false
dr002_activated: false
promotion_allowed: false
```
