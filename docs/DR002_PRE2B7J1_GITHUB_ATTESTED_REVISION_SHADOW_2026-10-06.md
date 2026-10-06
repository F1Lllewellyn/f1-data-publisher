# DR-002 pre-2B-7J1 — GitHub-attested synthetic revision shadow capability

Work order: [F1-WO-DR002-PRE2B7J1-001 / Issue #191](https://github.com/F1Lllewellyn/f1-data-publisher/issues/191)  
Recorded: 2026-10-06  
Result: isolated capability and focused offline verification PASS; no workflow run.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Installed capability

The manual-only revision shadow workflow composes the accepted frozen producer, forecast lock, and outcome-boundary wrappers under the actual revision-workflow identity. It then invokes the new revision wrapper once. Every composed wrapper receives the same repository, workflow name/ref, Git ref, implementation head, run ID, and attempt supplied by GitHub Actions.

The revision wrapper fails closed unless the same-run producer, lock, and outcome packages remain internally exact, name the actual caller, retain their false trust ceilings, and preserve their canonical Gate 2B-4 bindings. It does not treat predecessor attestations as independently verified and does not create an engine receipt or verified receipt binding.

## Synthetic revision mechanics

The wrapper deterministically selects the lexicographically smallest forecast evidence `source_id`. For the accepted fixed fixture this is `synthetic:dr002:drivers`. One fixed payload classified `SYNTHETIC_POST_CUTOFF_REVISION_NOT_REAL_PUBLISHER_REVISION` is captured with the same source ID, URI, event, meeting, and session as that original evidence source.

The revised payload bytes differ from the original source hash. Its parentless source-capture receipt has a distinct receipt ID and a first-observed time strictly after the forecast evidence cutoff. The internal clock and source publisher remain unauthenticated.

The unchanged `dr002_lock_boundary_revision_v1.build_revision` constructor is called exactly once. The unchanged `complete_forecast_record` constructor is called exactly once with the exact returned declaration. The completed record preserves the original forecast manifest and producer input-manifest identity, retains the same forecast lock and outcome boundary, and contains exactly one revision declaration.

## Runtime and future attestation

The runtime-only package contains:

- `revision_execution_manifest.json`;
- `synthetic_revised_source_payload.json`;
- `revised_source_capture_receipt.json`;
- `revision_receipt.json`;
- `completed_forecast_record.json`; and
- `revision_report.md`.

The successful manifest binds the exact persisted bytes for every pre-attestation evidence file and the exact same-run predecessor manifests. A separately authorized future execution may attest that exact successful manifest and preserve the action-produced bundle and factual metadata unchanged. Local DSSE subject inspection remains a consistency check only; independent GitHub/Sigstore verification belongs to a later work order.

## Focused verification

Focused offline tests cover the manual-only/main-only workflow, least permissions, hosted runner, exact wrapper order and caller identity, deterministic source selection, exact changed payload, post-cutoff timing, canonical parentless capture, single calls to both unchanged Gate 2B-4 constructors, exact revision and completed-record bindings, same-run predecessor verification, direct-workflow identity substitution failure, evidence tamper failure, exact future attestation subject handling, false trust ceilings, absence of network/production/repository-write capability, and all pinned dependency blobs.

No workflow was dispatched. No existing file was modified.

## Claim ceiling

This Work Result proves only that an isolated synthetic capability exists to compose the accepted producer → lock → outcome path under one truthful workflow identity, construct one exact synthetic post-cutoff revision to one forecast input source, exercise the unchanged Gate 2B-4 revision constructor, bind that declaration into a completed forecast record, and package an exact manifest for future GitHub attestation.

It does not prove a live revision run, real publisher revision capture, authenticated observation time, publisher authenticity, observation completeness, revision completeness, full Gate 2B-1 verification, production revision tracking or outcome enforcement, stable-engine execution, blind eligibility, predictive accuracy, activation, or promotion.

## Checkpoint

```text
revision_shadow_capability_installed: true
truthful_composed_chain_identity: true
single_synthetic_post_cutoff_revision_constructed: true
gate2b4_revision_constructor_used: true
completed_forecast_record_bound: true
live_revision_run_executed: false
revision_capture_externally_bound: false
revision_receipt_externally_bound: false
revision_clock_authenticated: false
revision_source_publisher_authenticated: false
observation_completeness_proven: false
revision_completeness_proven: false
revision_proof_completed: false
production_revision_tracking_proven: false
dr002_activated: false
promotion_allowed: false
```
