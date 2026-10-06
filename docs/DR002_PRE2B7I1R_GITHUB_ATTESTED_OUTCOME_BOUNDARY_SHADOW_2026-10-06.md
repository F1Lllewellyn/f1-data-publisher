# DR-002 pre-2B-7I1R — Corrected GitHub-attested synthetic outcome-boundary shadow capability

Work order: [F1-WO-DR002-PRE2B7I1R-001 / Issue #182](https://github.com/F1Lllewellyn/f1-data-publisher/issues/182)  
Recorded: 2026-10-06  
Result: corrected capability installed for review; no workflow run was dispatched.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Corrected composed identity

This capability was rebuilt against the accepted H3 lock-wrapper repair. Closed PR #178 is rejected evidence and is not part of the accepted lineage.

The new manual-only outcome workflow passes its actual GitHub identity to the corrected lock wrapper:

- `workflow_ref = ${{ github.workflow_ref }}`;
- `workflow = ${{ github.workflow }}`;
- `git_ref = ${{ github.ref }}`; and
- the current repository, head, run, and attempt values.

It never substitutes the direct lock workflow's identity. Before constructing any outcome receipt, the outcome wrapper independently fails closed unless the same-run lock manifest records exactly:

- `.github/workflows/dr002-outcome-boundary-shadow-pilot.yml` as `workflow_path`;
- the current repository plus that path and `@refs/heads/main` as `workflow_ref`;
- the current outcome workflow display name; and
- the outer repository, ref, head, run, attempt, and run ID.

Focused negative tests cover the rejected old lock-workflow identity and every outer identity mismatch.

## Installed capability

The workflow is `workflow_dispatch` only, restricted to `refs/heads/main`, and uses a GitHub-hosted runner with exactly `contents: read`, `id-token: write`, and `attestations: write`. A separately authorized future run will execute once and in order:

1. the accepted frozen-producer shadow;
2. the corrected forecast-lock shadow with the actual outcome-workflow identity;
3. the new synthetic outcome-boundary wrapper;
4. the accepted immutable `actions/attest` release against the exact successful outcome-boundary manifest;
5. exact action-bundle and factual-metadata preservation; and
6. runtime-only evidence upload.

There is no repository write, push, commit, production dispatch, live F1/OpenF1 request by project code, stable-engine execution, Pipedream, Gmail, `latest/**`, `history/**`, workbook, ledger, or production output path.

## Synthetic outcome and boundary

The wrapper preserves one fixed synthetic outcome payload for the same synthetic event, meeting, and session as the forecast context. Its source ID is `synthetic:dr002:outcome_result`, its URI is `synthetic://dr002/outcome-result/v1`, and it is distinct from every forecast input source.

A canonical parentless Gate 2B-1 `source_capture` receipt binds the exact payload bytes and SHA-256. The unchanged Gate 2B-4 `build_outcome_boundary` is called exactly once with policy `synthetic:dr002:outcome-boundary-policy-v1`. The boundary receipt's only parent is the synthetic outcome capture, and its boundary equals only that capture's `first_observed_utc`.

Event and publisher times are not substituted. Internal first-observed, capture-receipt creation, and boundary-receipt creation times remain separate and unauthenticated. A future transparency-log time cannot authenticate them.

No revision receipt, engine receipt, or `verified_receipt_bindings` value is created.

## Runtime and attestation package

A future authorized run will preserve under `_runtime/dr002_pre2b7i_outcome_boundary_shadow/gha-<run_id>-<attempt>/`:

- `outcome_boundary_execution_manifest.json`;
- `synthetic_outcome_payload.json`;
- `outcome_source_capture_receipt.json`;
- `outcome_boundary_receipt.json`;
- `outcome_boundary_report.md`;
- `github_attestation.bundle.json`; and
- `github_attestation_metadata.json`.

The manifest binds the exact pre-attestation evidence, same-run producer and lock manifests, truthful outer execution identity, outcome payload and receipt hashes, internal times, boundary, and policy. The action-produced bundle is preserved byte-for-byte. Local DSSE subject inspection is consistency checking only; independent GitHub/Sigstore verification requires a later separately authorized I2 run.

## Claim ceiling

This Work Result proves only that a corrected isolated capability exists to compose producer → lock → synthetic outcome boundary with truthful workflow provenance and package an exact manifest for future attestation.

It does not prove a live run, authenticated outcome time, real race result, publisher truth, observation or revision completeness, full Gate 2B-1 verification, production enforcement, blind eligibility, predictive accuracy, activation, or promotion.

## Checkpoint

```text
outcome_boundary_shadow_capability_installed: true
truthful_composed_lock_workflow_identity: true
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
