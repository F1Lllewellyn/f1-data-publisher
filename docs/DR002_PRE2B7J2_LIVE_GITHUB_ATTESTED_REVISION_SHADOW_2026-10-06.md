# DR-002 pre-2B-7J2 — Live GitHub-attested synthetic post-cutoff revision shadow

Work order: [F1-WO-DR002-PRE2B7J2-001 / Issue #194](https://github.com/F1Lllewellyn/f1-data-publisher/issues/194)  
Recorded: 2026-10-06  
Result: COMPLETED — one live synthetic post-cutoff revision shadow and independent saved-bundle verification PASS.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Observed GitHub run

The user manually dispatched the first and only qualifying run after the accepted J1 merge and J2 authorization. Coder did not dispatch, rerun, retry failed jobs, or trigger a second attempt.

| Run fact | Value |
|---|---|
| Run | [37606489538](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37606489538) |
| Run number / attempt | `1` / `1` |
| Event | `workflow_dispatch` |
| Workflow | `DR-002 synthetic post-cutoff revision shadow pilot` |
| Workflow path | `.github/workflows/dr002-revision-shadow-pilot.yml` |
| Branch / ref | `main` / `refs/heads/main` |
| Head | `34640d94df841d7fdd67fc12c3ab1e685a5bcc67` |
| Actor / triggering actor | `F1Lllewellyn` / `F1Lllewellyn` |
| Created / started | `2026-10-07T10:18:13Z` / `2026-10-07T10:18:13Z` |
| Terminal updated timestamp | `2026-10-07T10:22:39Z` |
| Status / conclusion | `completed` / `success` |
| Job ID / name | `112743130746` / `shadow` |
| Job conclusion | `success` |
| Runner | GitHub-hosted; runner version `2.337.0`; Hosted Compute Agent |
| Runner image | Ubuntu 24.04.5 LTS; `ubuntu-24.04` image version `20260927.320.1` |
| Job-log observation window | `2026-10-07T10:18:19.4282312Z` through `2026-10-07T10:22:35.3572923Z` |

The run API exposes `updated_at`, not a separate run-completion field. The job log provides the observed runner execution window.

| Step | Conclusion |
|---|---|
| Set up job | success |
| Run `actions/checkout@v4` | success |
| Run `actions/setup-python@v5` | success |
| One accepted synthetic frozen producer shadow | success |
| One accepted synthetic forecast lock shadow | success |
| One accepted synthetic outcome-boundary shadow | success |
| One Gate 2B-4 synthetic post-cutoff revision shadow | success |
| Attest exact successful revision execution manifest | success |
| Preserve attestation bundle and factual metadata | success |
| Run `actions/upload-artifact@v4` | success |
| Post `actions/setup-python@v5` | success |
| Post `actions/checkout@v4` | success |
| Complete job | success |

The job log reports `Attestations: write`, `Contents: read`, and `Metadata: read`. The committed workflow also declares `id-token: write`; checkout used `persist-credentials: false` at the exact run head.

## Artifact identity and exact-byte verification

| Artifact fact | Value |
|---|---|
| ID | `11474583887` |
| Name | `dr002-revision-shadow-37606489538-1` |
| Size | 38,217 bytes |
| GitHub-reported digest | `sha256:fa5c8c6fad142424aba1b15973874efcb8e78daa9a09e792a2398a3dbecb15b9` |
| Independently recomputed ZIP SHA-256 | `fa5c8c6fad142424aba1b15973874efcb8e78daa9a09e792a2398a3dbecb15b9` |
| Created | `2026-10-07T10:22:34Z` |
| Expires | `2027-01-05T10:18:15Z` |
| Expired at inspection | false |

The downloaded archive contains exactly 29 regular files across the same-run producer, lock, outcome, and revision packages. It has no duplicate, absolute, parent-traversal, or symbolic-link entries. The upload action removes only their common `_runtime/` ancestor.

Key exact-byte SHA-256 values independently recomputed from the archive:

| File | SHA-256 |
|---|---|
| Producer `execution_manifest.json` | `2a3d629578dc37080124d58a23c41ac8558d9b2d68f4e6f43ae27ec192ae88bb` |
| Producer `evidence/forecast_rows.csv` | `c119ab7107a85a4b29a186d1d250b704cb53421b4052db76be868bcba077599d` |
| Lock `forecast_payload.csv` | `c119ab7107a85a4b29a186d1d250b704cb53421b4052db76be868bcba077599d` |
| `producer_execution_receipt.json` | `3731e4580616c3dde6d30a9d75bd2585ffae1ca8bb5fcadd70857ddf08c280bf` |
| `forecast_lock_receipt.json` | `89c0e6c94aad69c3b5b6ed3fdc8693023b87792cffcb536aba589c2a2aa6460c` |
| `lock_execution_manifest.json` | `917c899a5cdfb4631aabfbdfc11f3fa124e6b2e22e004b117bbf56ea896517b3` |
| `synthetic_outcome_payload.json` | `2e3e0544c8f9f86b737877c4cd48146f2b4e82cc33c77867f9f6b06faae81052` |
| `outcome_source_capture_receipt.json` | `a565c181ce4699a5dfe85f8e1b1ea2e51620176609234ae19049cb30ca5167b9` |
| `outcome_boundary_receipt.json` | `a3c8cba84456a247a3f85427872a9abf8e6f31cd1b40d9443c1b1346b41cd513` |
| `outcome_boundary_execution_manifest.json` | `7e8ae5e6dd3ba313efdb4d043f3e3f7696a9e41ed8ae7c167f0f9d474911b1f2` |
| `synthetic_revised_source_payload.json` | `c9718b5e5ef18e52f41e65ad291bd0eaf3d8f3cf5c0ff8141c91ace3415eb074` |
| `revised_source_capture_receipt.json` | `566a2c0ce49bbd1ba7fce5e09b3bf15fcad92bb1a54c0abd11a4ec908f14c0a6` |
| `revision_receipt.json` | `d3900d0ce5c9c56a1da24c39db5408aedd42810d72c39289603eb30894648555` |
| `completed_forecast_record.json` | `575b08bade9737af4cc89aae049ccf7a73c2ed7f25bf47d96eacc279e6a1dea4` |
| `revision_report.md` | `528f8d117f8268f1c7556cb4de60fb634bcf85ea6fd444b34eacac59b07444ff` |
| `revision_execution_manifest.json` | `7b293f93d66b5e4c2723f8d2d42a2229547e08f17e1f6343663ca5ba160dd40f` |
| `github_attestation.bundle.json` | `6d757e2a766ba63cb463aa180cebce55267f8a9fd98f0f426306b26fc47572e9` |
| `github_attestation_metadata.json` | `b428030ea5340602743b6cbaa4178031c6743c3ad33d731a4310bddfeb83e359` |

### Truthful same-run composition

The producer `forecast_rows.csv` bytes equal the lock `forecast_payload.csv` bytes exactly. Their SHA-256 matches the producer manifest, synthetic producer receipt, forecast-lock receipt, stored-payload declaration, and lock execution manifest.

The lock, outcome, and revision manifests record the actual outer revision workflow identity:

- repository `F1Lllewellyn/f1-data-publisher`;
- workflow path `.github/workflows/dr002-revision-shadow-pilot.yml`;
- workflow ref `F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-revision-shadow-pilot.yml@refs/heads/main`;
- ref `refs/heads/main`;
- head `34640d94df841d7fdd67fc12c3ab1e685a5bcc67`;
- run `37606489538`; and
- attempt `1`.

The same-run producer, lock, and outcome manifests recompute to the hashes declared by the revision manifest. All evidence maps and canonical receipt hashes independently agree:

| Receipt | Canonical SHA-256 |
|---|---|
| Producer execution | `5e81a49b37b7ca1657f04ae11bee8e1452a553775cd440fdc0e73ef3ca44b6e6` |
| Forecast lock | `106005b1c826ab99b7d783b50585b707af43d15b9b7000d893df26514d30efd6` |
| Outcome source capture | `bc9d14b2d021679c95bd671f1058a90a0aa4710ae8cd538742764e4c5448b725` |
| Outcome boundary | `211f638d9fb12d884ed2dbc71b37e62188c72ae59f1ced1f1a7b2fefbb511043` |
| Revised source capture | `3b01ddb430f6550fa5c366b688e589d16577a86cd846a74cd86f3257490fed33` |
| Revision | `599d099c7ee8857e8ab1ddb9af1732100d7635bb2c4a3af66c39c08b4eb32ca1` |

The archived synthetic outcome bytes are canonical. Its capture is parentless, hashes the exact payload, and the unchanged Gate 2B-4 constructor reproduces the archived outcome-boundary receipt exactly.

### Exact synthetic post-cutoff revision

The deterministic minimum source ID selects `synthetic:dr002:drivers`. Its source URI is `runtime-artifact:evidence/drivers.csv`, its scope is the same synthetic event, meeting, and session as the original forecast evidence, and its original exact-byte SHA-256 is `a5225adcc4ab55f9ea33c11de7cef4fc06a30171c56a7d681fd4c4987b335ba0`.

The archived `synthetic_revised_source_payload.json` bytes equal the fixed canonical bytes declared by the accepted wrapper. Their SHA-256 is `c9718b5e5ef18e52f41e65ad291bd0eaf3d8f3cf5c0ff8141c91ace3415eb074`, which differs from the original source hash.

The revised source-capture receipt is parentless and hashes those exact bytes. Its source ID, URI, event, meeting, and session match the selected original source. Its first-observed time is strictly after the forecast evidence cutoff:

| Structural value | Value |
|---|---|
| Forecast evidence cutoff | `2026-10-07T10:22:28Z` |
| Revised first observed | `2026-10-07T10:22:29Z` |
| Revised capture receipt created | `2026-10-07T10:22:29Z` |
| Revision receipt created | `2026-10-07T10:22:29Z` |
| Revised capture receipt ID | `source_capture:09021e2280d4668623411d1212fa86023820a2748f18e68acba5ced131c102ac` |
| Revision ID | `revision:05c91a0d9d8d3183d9a61324caa9eaf3642d29403173d9693f49935d9c189e32` |
| Revision receipt ID | `revision:c6873d3c6732fae0dd266db74203090cac5d0da804c9b1e2442e49b08aa37598` |

The revision receipt's only parent is the exact revised source capture. Its source ID, source hash, and first-observed time equal the capture values. Independent reconstruction with the unchanged Gate 2B-4 `build_revision` constructor reproduces the archived revision receipt and returned declaration exactly.

Independent reconstruction with the unchanged `complete_forecast_record` constructor reproduces the archived completed record exactly. The record preserves every original forecast manifest value and the producer input-manifest identity, retains the same lock and outcome-boundary receipt references, and contains exactly one declaration equal to the Gate 2B-4 returned declaration.

No second revision receipt or declaration exists. No `engine_execution` receipt exists. No `verified_receipt_bindings` value exists. All 18 required trust-ceiling fields in both the revision manifest and factual attestation metadata remain false.

## Independent GitHub/Sigstore verification

Attestation: [53524663](https://github.com/F1Lllewellyn/f1-data-publisher/attestations/53524663).  
Subject path: `_runtime/dr002_pre2b7j_revision_shadow/gha-37606489538-1/revision_execution_manifest.json`.  
Exact subject SHA-256: `7b293f93d66b5e4c2723f8d2d42a2229547e08f17e1f6343663ca5ba160dd40f`.

Independent `sigstore` 4.5.0 saved-bundle verification with the default Public Good Sigstore trust roots succeeded offline with exit 0. The exact certificate identity and OIDC issuer were required:

```sh
sigstore verify identity --offline \
  --bundle github_attestation.bundle.json \
  --cert-identity 'https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-revision-shadow-pilot.yml@refs/heads/main' \
  --cert-oidc-issuer 'https://token.actions.githubusercontent.com' \
  revision_execution_manifest.json
```

The verified statement and Fulcio certificate were then checked fail-closed for repository, workflow, ref, exact source and signer digests, GitHub-hosted runner, trigger, and run/attempt invocation. No verification constraint was removed or weakened.

| Field | Verified value |
|---|---|
| Statement type | `https://in-toto.io/Statement/v1` |
| Predicate type | `https://slsa.dev/provenance/v1` |
| Build type | `https://actions.github.io/buildtypes/workflow/v1` |
| Subject | `revision_execution_manifest.json` / `7b293f93d66b5e4c2723f8d2d42a2229547e08f17e1f6343663ca5ba160dd40f` |
| Certificate issuer | `CN=sigstore-intermediate,O=sigstore.dev` |
| OIDC issuer | `https://token.actions.githubusercontent.com` |
| Certificate SAN / signer workflow | `https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-revision-shadow-pilot.yml@refs/heads/main` |
| Repository | `F1Lllewellyn/f1-data-publisher` |
| Workflow / ref | `.github/workflows/dr002-revision-shadow-pilot.yml` / `refs/heads/main` |
| Source digest | `34640d94df841d7fdd67fc12c3ab1e685a5bcc67` |
| Signer/build-config digest | `34640d94df841d7fdd67fc12c3ab1e685a5bcc67` |
| Runner environment | `github-hosted` |
| Workflow trigger | `workflow_dispatch` |
| Invocation | `https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37606489538/attempts/1` |

The verified bundle records Rekor integrated time `1791368550`, exactly `2026-10-07T10:22:30Z`, with an inclusion promise, inclusion proof, and checkpoint. Therefore the exact attested manifest bytes existed no later than `2026-10-07T10:22:30Z`.

That transparency-log fact does not authenticate the internal revision first-observed or receipt times, a real publisher/source revision, earliest or historical availability, observation or revision completeness, or durable storage.

## Resume checkpoint and dependency state

The Adviser resume checkpoint pinned this exact run and recorded all named accepted dependency blobs as unchanged. No named dependency changed after that checkpoint. Fresh `main` at publication inspection was `34640d94df841d7fdd67fc12c3ab1e685a5bcc67`, exactly the run head. Per the resume instruction, broad run discovery, J1 implementation review, overlap search, and dependency-fingerprint reconciliation were not repeated. The authorized checkpoint path did not exist on `main` before this Work Result.

## Prohibited actions and claim ceiling

The committed workflow, exact job log, and artifact show no repository write/push/commit, production locker or orchestrator invocation, live F1/OpenF1 request, stable-engine execution, canonical workbook mutation, production output write, or second dispatch. The runtime evidence is synthetic and isolated; the producer sandbox was disposed.

This run proves only that one live GitHub Actions synthetic post-cutoff revision shadow executed; truthful same-run producer → lock → synthetic outcome-boundary → one synthetic revision composition occurred; exact revised bytes were bound into a source-capture receipt and the unchanged Gate 2B-4 revision receipt and completed record; exact revision execution-manifest bytes were cryptographically tied to the expected GitHub workflow, run, attempt, ref, and head; and those exact manifest bytes existed no later than the verified transparency-log timestamp.

It does not prove a real publisher revision, authenticated revision observation time, publisher/source authenticity, observation completeness, revision completeness, production revision tracking, a full Gate 2B-1 verified receipt chain, production forecast locking, production outcome-boundary enforcement, protected stable-engine execution, blind eligibility, predictive accuracy, or DR-002 production enforcement.

No implementation file changed, no test suite was rerun, and no workflow was dispatched, retried, or rerun by Coder. This Work Result adds one Markdown checkpoint only and remains unmerged for independent Science / Architecture Adviser review.

## Checkpoint

```text
live_post_cutoff_revision_shadow_run_executed: true
run_attempt_one_only: true
truthful_composed_revision_workflow_identity: true
exact_synthetic_revised_source_payload_bound: true
gate2b4_revision_constructor_exercised_live: true
completed_forecast_record_bound: true
single_synthetic_revision_constructed: true
revision_after_forecast_cutoff: true
github_attestation_cryptographically_verified: true
attested_manifest_existed_by_tlog: true
revision_capture_externally_bound: false
revision_receipt_externally_bound: false
revision_clock_authenticated: false
revision_source_publisher_authenticated: false
observation_completeness_proven: false
revision_completeness_proven: false
revision_proof_completed: false
durable_storage_proven: false
full_gate2b1_chain_verified: false
production_revision_tracking_proven: false
stable_engine_execution_proven: false
blind_validation_eligible: false
dr002_activated: false
promotion_allowed: false
```
