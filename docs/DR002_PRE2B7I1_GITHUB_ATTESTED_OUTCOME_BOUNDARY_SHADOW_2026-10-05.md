# DR-002 pre-2B-7I1 — GitHub-attested synthetic outcome-boundary shadow capability

Work order: [F1-WO-DR002-PRE2B7I1-001 / Issue #177](https://github.com/F1Lllewellyn/f1-data-publisher/issues/177)  
Recorded: 2026-10-06  
Result: capability installed for review; no workflow run was dispatched.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Installed capability

The new manual-only workflow is restricted to `refs/heads/main` and uses a GitHub-hosted runner with exactly `contents: read`, `id-token: write`, and `attestations: write`. A separately authorized future run will execute, once and in order:

1. the accepted frozen-producer shadow;
2. the accepted forecast-lock shadow for the same run and head;
3. the new synthetic outcome-boundary wrapper;
4. `actions/attest` v4.2.2 at the accepted immutable pin against the exact successful outcome-boundary manifest;
5. exact action-bundle and factual-metadata preservation; and
6. runtime-only artifact upload.

The workflow contains no repository write, commit, push, production dispatch, F1/OpenF1 request by project code, stable-engine execution, Pipedream, or Gmail path. It publishes no `latest/**`, `history/**`, workbook, ledger, production forecast bundle, or production output.

## Synthetic outcome and boundary semantics

The wrapper consumes and revalidates the same-run accepted producer and lock packages. It preserves one fixed synthetic outcome payload with:

- source ID `synthetic:dr002:outcome_result`, distinct from every forecast input source;
- URI `synthetic://dr002/outcome-result/v1`;
- the same synthetic event, meeting, and session as the accepted lock shadow; and
- exact raw payload bytes and SHA-256.

It constructs a canonical, parentless `source_capture` receipt for those exact bytes under the unchanged Gate 2B-1 envelope and temporal rules. It then calls the unchanged Gate 2B-4 `build_outcome_boundary` exactly once with policy reference `synthetic:dr002:outcome-boundary-policy-v1`. The outcome-boundary receipt's only parent is that separate synthetic capture, and its boundary equals only the capture's `first_observed_utc`.

Event time and publisher time are null. The internal outcome observation, capture-receipt creation, and boundary-receipt creation times are recorded separately. A future GitHub/Sigstore transparency-log time is also separate and cannot authenticate any internal outcome clock.

No revision receipt, engine receipt, or `verified_receipt_bindings` value is created.

## Runtime evidence package

A future authorized run will preserve under `_runtime/dr002_pre2b7i_outcome_boundary_shadow/gha-<run_id>-<attempt>/`:

- `outcome_boundary_execution_manifest.json`;
- `synthetic_outcome_payload.json`;
- `outcome_source_capture_receipt.json`;
- `outcome_boundary_receipt.json`;
- `outcome_boundary_report.md`;
- `github_attestation.bundle.json`; and
- `github_attestation_metadata.json`.

The manifest binds the exact pre-attestation evidence bytes, same-run producer and lock manifests, GitHub repository/workflow/ref/head/run/attempt identity, internal times, exact boundary, and exact policy reference. The action-produced attestation bundle is preserved unchanged. Local DSSE subject inspection is consistency checking only; independent GitHub/Sigstore verification belongs to a later separately authorized live-run work order.

## Validation

Focused offline tests cover the authorized workflow restrictions and ordering, exact permissions and immutable attestation subject, exact synthetic bytes and receipt hashing, distinct outcome source identity, unchanged constructor invocation, exact parent and boundary semantics, absence of revision/engine/fabricated bindings, full false trust ceiling, bundle preservation, fail-closed tamper handling, and every named dependency Git blob. Cheap Python syntax validation also passes.

## Claim ceiling

This Work Result proves only that isolated capability exists to consume a same-run synthetic producer and lock shadow, construct a separate synthetic outcome capture, exercise the unchanged Gate 2B-4 outcome-boundary constructor, and package an exact manifest for a future GitHub attestation.

It does not prove a live run, authenticated observation time, publisher or source truth, real race-result capture, observation or revision completeness, full Gate 2B-1 verification, production locking or outcome enforcement, protected stable-engine execution, blind eligibility, predictive accuracy, activation, or promotion.

## Checkpoint

```text
outcome_boundary_shadow_capability_installed: true
live_outcome_boundary_run_executed: false
separate_synthetic_outcome_capture_constructed: true
gate2b4_outcome_boundary_constructor_used: true
boundary_equals_outcome_first_observed: true
outcome_capture_externally_bound: false
outcome_boundary_receipt_externally_bound: false
outcome_clock_authenticated: false
outcome_source_publisher_authenticated: false
observation_completeness_proven: false
revision_proof_completed: false
production_outcome_boundary_proven: false
dr002_activated: false
promotion_allowed: false
```
