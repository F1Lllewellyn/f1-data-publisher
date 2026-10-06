# DR-002 pre-2B-7I2 — Live GitHub-attested synthetic outcome-boundary shadow

Work order: [F1-WO-DR002-PRE2B7I2-001 / Issue #185](https://github.com/F1Lllewellyn/f1-data-publisher/issues/185)  
Recorded: 2026-10-06  
Result: COMPLETED — one live synthetic outcome-boundary shadow and independent saved-bundle verification PASS.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Observed GitHub run

The user manually dispatched the first and only qualifying run after the accepted I1R merge and I2 authorization. Coder did not dispatch, rerun, retry failed jobs, or trigger a second attempt.

| Run fact | Value |
|---|---|
| Run | [37457499638](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37457499638) |
| Run number / attempt | `1` / `1` |
| Event | `workflow_dispatch` |
| Workflow | `DR-002 synthetic outcome boundary shadow pilot` |
| Workflow path | `.github/workflows/dr002-outcome-boundary-shadow-pilot.yml` |
| Branch / ref | `main` / `refs/heads/main` |
| Head | `55d0cf2de4c8738ee4debfe70d34030b6a9c9ad7` |
| Actor / triggering actor | `F1Lllewellyn` / `F1Lllewellyn` |
| Created / started | `2026-10-06T11:36:13Z` / `2026-10-06T11:36:13Z` |
| Terminal updated timestamp | `2026-10-06T11:39:38Z` |
| Status / conclusion | `completed` / `success` |
| Job ID / name | `112248592157` / `shadow` |
| Job conclusion | `success` |
| Runner | GitHub-hosted; runner version `2.337.0`; Hosted Compute Agent in Azure `westus3` |
| Runner image | Ubuntu 24.04.5 LTS; `ubuntu-24.04` image version `20260927.320.1` |
| Job-log observation window | `2026-10-06T11:36:18.6629551Z` through `2026-10-06T11:39:35.4506497Z` |

The run API exposes `updated_at`, not a separate run-completion field. The job log provides the observed runner execution window.

| Step | Conclusion |
|---|---|
| Set up job | success |
| Run `actions/checkout@v4` | success |
| Run `actions/setup-python@v5` | success |
| One accepted synthetic frozen producer shadow | success |
| One accepted synthetic forecast lock shadow | success |
| One Gate 2B-4 synthetic outcome boundary shadow | success |
| Attest exact successful outcome boundary manifest | success |
| Preserve attestation bundle and factual metadata | success |
| Run `actions/upload-artifact@v4` | success |
| Post `actions/setup-python@v5` | success |
| Post `actions/checkout@v4` | success |
| Complete job | success |

The job log reports `Attestations: write`, `Contents: read`, and `Metadata: read`. The committed workflow also declares `id-token: write`; checkout used `persist-credentials: false` at the exact run head.

## Artifact identity and exact-byte verification

| Artifact fact | Value |
|---|---|
| ID | `11410291039` |
| Name | `dr002-outcome-boundary-shadow-37457499638-1` |
| Size | 32,650 bytes |
| GitHub-reported digest | `sha256:2d4ad9230f1f13ceefe36d857027f43ecbdd0607a63638e6008fb10268618aea` |
| Independently recomputed ZIP SHA-256 | `2d4ad9230f1f13ceefe36d857027f43ecbdd0607a63638e6008fb10268618aea` |
| Created / updated | `2026-10-06T11:39:34Z` / `2026-10-06T11:39:34Z` |
| Expires | `2027-01-04T11:36:14Z` |
| Expired at inspection | false |

The downloaded archive contains exactly 23 files across the same-run producer, lock, and outcome packages. The upload action removes only their common `_runtime/` ancestor.

Key exact-byte SHA-256 values independently recomputed from the archive:

| File | SHA-256 |
|---|---|
| Producer `execution_manifest.json` | `64ed24c0f99d8c54e51fb744ce7a0ba01db9a41cbc1f538f2dcf47794c90a11c` |
| Producer `evidence/forecast_rows.csv` | `41f50182b5a9396f47116655fd4b00c9b93bdea5cb6aaa59a564a1b1025c9a68` |
| Lock `forecast_payload.csv` | `41f50182b5a9396f47116655fd4b00c9b93bdea5cb6aaa59a564a1b1025c9a68` |
| `producer_execution_receipt.json` | `058de40f1b6d4af369d08f9429a7d44615e35e46f3a0dac6096170d80a1a6a22` |
| `forecast_lock_receipt.json` | `d9862719a1e432772743ac04684263256f97a7555151f5ac42d334b98652c58c` |
| `lock_execution_manifest.json` | `a095443f4217672711755e2e4474976ed943121e9f730dfec7c19e31e3ebf7d1` |
| `synthetic_outcome_payload.json` | `2e3e0544c8f9f86b737877c4cd48146f2b4e82cc33c77867f9f6b06faae81052` |
| `outcome_source_capture_receipt.json` | `237c8ae217043b886904835a38aec96619e7e6bd96b0163ffec61e6b4b9695ac` |
| `outcome_boundary_receipt.json` | `6a86bb9a7084a3e339729938924a02d315c589110c0f1dc4f05ad7583df79743` |
| `outcome_boundary_report.md` | `eb1f3a9e5cec74bb4e6dac10aae2d70aa12c2cb04adc747b62854f96032a2632` |
| `outcome_boundary_execution_manifest.json` | `5bb7bb11c8554c530dd36b87c0d981097a94883bb27ffbc785a40b60bf77ae12` |
| `github_attestation.bundle.json` | `dd6d5d685c2506fab5ac8b171dbf287119c595f7a050c57a6105f431d5c9c5ed` |
| `github_attestation_metadata.json` | `62cf54e10e98e545b9718427fe34746e4cecbd27d5c4d68b34bb373b414df246` |

### Truthful same-run composition

The producer `forecast_rows.csv` bytes equal the lock `forecast_payload.csv` bytes exactly. Their SHA-256 matches the producer manifest, synthetic producer receipt, forecast-lock receipt, stored-payload declaration, and lock execution manifest.

The lock manifest records the actual outer outcome workflow identity:

- repository `F1Lllewellyn/f1-data-publisher`;
- workflow path `.github/workflows/dr002-outcome-boundary-shadow-pilot.yml`;
- workflow ref `F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-outcome-boundary-shadow-pilot.yml@refs/heads/main`;
- ref `refs/heads/main`;
- head `55d0cf2de4c8738ee4debfe70d34030b6a9c9ad7`;
- run `37457499638`; and
- attempt `1`.

The same-run producer and lock manifests recompute to the hashes declared by the outcome manifest. All producer and lock evidence hashes and canonical receipt hashes independently agree. The canonical producer-receipt digest is `daf5230e297d9d15b030aae97d7974e89c7f6adcb0faf17ec1ecbabd956a4cb1`; the canonical forecast-lock-receipt digest is `92740c1bf2150435d976a4832cc9dec5ba890dc4886d66d99c1ef16f477ca44b`.

### Exact synthetic outcome boundary

The archived `synthetic_outcome_payload.json` bytes equal the fixed canonical bytes declared by the accepted wrapper. The source-capture receipt hashes those exact bytes, and its source ID `synthetic:dr002:outcome_result` is distinct from all three forecast input source IDs.

The outcome-boundary receipt's only parent is `source_capture:3379f72caf035b6fcb0c179f90992fb92cbdee3a0df1d106ef55b56276ee1ceb`. Its boundary equals only the source capture's `first_observed_utc`, and its policy is exactly `synthetic:dr002:outcome-boundary-policy-v1`.

| Structural value | Value |
|---|---|
| Outcome first observed | `2026-10-06T11:39:31Z` |
| Outcome capture receipt created | `2026-10-06T11:39:31Z` |
| Outcome-boundary receipt created | `2026-10-06T11:39:31Z` |
| Outcome availability boundary | `2026-10-06T11:39:31Z` |
| Canonical capture-receipt SHA-256 | `cbf3906afceda8711b9b3e953f100e5fafd15ba968ff7673cb04df92799f36be` |
| Canonical boundary-receipt SHA-256 | `e05e4a8743c7ddb536f6514317ea85d28874c2c2e6b6b22e26a7f05570643d58` |

Timestamp equality in this one execution is structurally permitted. These workflow-authored times are unauthenticated; only the outcome capture's `first_observed_utc` supplies the boundary value.

No `revision` receipt exists. No `engine_execution` receipt exists. No `verified_receipt_bindings` value exists. All 16 required trust-ceiling fields in both the outcome manifest and factual attestation metadata remain false.

## Independent GitHub/Sigstore verification

Attestation: [53155711](https://github.com/F1Lllewellyn/f1-data-publisher/attestations/53155711).  
Subject path: `_runtime/dr002_pre2b7i_outcome_boundary_shadow/gha-37457499638-1/outcome_boundary_execution_manifest.json`.  
Exact subject SHA-256: `5bb7bb11c8554c530dd36b87c0d981097a94883bb27ffbc785a40b60bf77ae12`.

Independent `sigstore` 4.5.0 saved-bundle verification with the default Public Good Sigstore trust roots succeeded offline with exit 0. The exact certificate identity and OIDC issuer were required:

```sh
sigstore verify identity --offline \
  --bundle github_attestation.bundle.json \
  --cert-identity 'https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-outcome-boundary-shadow-pilot.yml@refs/heads/main' \
  --cert-oidc-issuer 'https://token.actions.githubusercontent.com' \
  outcome_boundary_execution_manifest.json
```

The verified statement and Fulcio certificate were then checked fail-closed for repository, workflow, ref, exact source and signer digests, GitHub-hosted runner, trigger, and run/attempt invocation. No verification constraint was removed or weakened.

| Field | Verified value |
|---|---|
| Statement type | `https://in-toto.io/Statement/v1` |
| Predicate type | `https://slsa.dev/provenance/v1` |
| Build type | `https://actions.github.io/buildtypes/workflow/v1` |
| Subject | `outcome_boundary_execution_manifest.json` / `5bb7bb11c8554c530dd36b87c0d981097a94883bb27ffbc785a40b60bf77ae12` |
| Certificate issuer | `CN=sigstore-intermediate,O=sigstore.dev` |
| OIDC issuer | `https://token.actions.githubusercontent.com` |
| Certificate SAN / signer workflow | `https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-outcome-boundary-shadow-pilot.yml@refs/heads/main` |
| Repository | `F1Lllewellyn/f1-data-publisher` |
| Workflow / ref | `.github/workflows/dr002-outcome-boundary-shadow-pilot.yml` / `refs/heads/main` |
| Source digest | `55d0cf2de4c8738ee4debfe70d34030b6a9c9ad7` |
| Signer/build-config digest | `55d0cf2de4c8738ee4debfe70d34030b6a9c9ad7` |
| Runner environment | `github-hosted` |
| Workflow trigger | `workflow_dispatch` |
| Invocation | `https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37457499638/attempts/1` |

The verified bundle records Rekor integrated time `1791286773`, exactly `2026-10-06T11:39:33Z`, with an inclusion promise, inclusion proof, and checkpoint. Therefore the exact attested manifest bytes existed no later than `2026-10-06T11:39:33Z`.

That transparency-log fact does not authenticate any internal outcome first-observed or receipt time, real publisher/source truth, earliest or historical availability, observation completeness, revision completeness, or durable storage.

## Run-head dependency reconciliation

Fresh `main` and the run head were both `55d0cf2de4c8738ee4debfe70d34030b6a9c9ad7` at inspection. Every declared relevant dependency matched its accepted Git blob at that exact head:

| Path | Git blob | Result |
|---|---|---|
| `.github/workflows/dr002-outcome-boundary-shadow-pilot.yml` | `5ebe0dcaed10583bacd56687bd92d971f561f680` | PASS |
| `scripts/forecast_bundles/dr002_outcome_boundary_shadow_pilot_v1.py` | `5f16658827d9896e8634a32b92fd0934555e4eac` | PASS |
| `tests/test_dr002_outcome_boundary_shadow_pilot_v1.py` | `a6c3f67cf9176406ee18036bdf2aa3c99cd169a5` | PASS |
| `docs/DR002_PRE2B7I1R_GITHUB_ATTESTED_OUTCOME_BOUNDARY_SHADOW_2026-10-06.md` | `9802cad7b3f0c3126b17abecb7b6f499488655bb` | PASS |
| `scripts/forecast_bundles/dr002_forecast_lock_shadow_pilot_v1.py` | `1ef04022041c7dcf625ae10c051c23b35ed72a9d` | PASS |
| `scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py` | `1d3bfaf713807e799a6323875de670dc8d4e1a85` | PASS |
| `scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py` | `064d93ee5ae30354590a3fb95be598c5fe8b3b9a` | PASS |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` | PASS |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` | PASS |

The authorized checkpoint path did not exist before this Work Result.

## Prohibited actions and claim ceiling

The committed workflow, job log, and artifact show no repository write/push/commit, production locker or orchestrator invocation, live F1/OpenF1 request, stable-engine execution, canonical workbook mutation, production output write, or second dispatch. The runtime evidence is synthetic and isolated; the producer sandbox was disposed.

This run proves only that one live GitHub Actions synthetic outcome-boundary shadow executed; truthful same-run producer → lock → synthetic outcome-boundary composition occurred; exact synthetic outcome bytes were bound into a source-capture receipt and the unchanged Gate 2B-4 outcome-boundary receipt; exact outcome-boundary execution-manifest bytes were cryptographically tied to the expected GitHub workflow, run, attempt, ref, and head; and those exact manifest bytes existed no later than the verified transparency-log timestamp.

It does not prove real race-result capture, authenticated outcome observation time, publisher/source authenticity, observation completeness, revision completeness, production outcome-boundary enforcement, a full Gate 2B-1 verified receipt chain, production forecast locking, protected stable-engine execution, blind eligibility, predictive accuracy, or DR-002 production enforcement.

No implementation file changed, no test suite was rerun, and no workflow was dispatched, retried, or rerun by Coder. This Work Result adds one Markdown checkpoint only and remains unmerged for independent Science / Architecture Adviser review.

## Checkpoint

```text
live_outcome_boundary_shadow_run_executed: true
run_attempt_one_only: true
truthful_composed_lock_workflow_identity: true
exact_synthetic_outcome_payload_bound: true
gate2b4_outcome_boundary_constructor_exercised_live: true
github_attestation_cryptographically_verified: true
attested_manifest_existed_by_tlog: true
outcome_capture_externally_bound: false
outcome_boundary_receipt_externally_bound: false
outcome_clock_authenticated: false
outcome_source_publisher_authenticated: false
observation_completeness_proven: false
revision_proof_completed: false
durable_storage_proven: false
full_gate2b1_chain_verified: false
production_outcome_boundary_proven: false
stable_engine_execution_proven: false
blind_validation_eligible: false
dr002_activated: false
promotion_allowed: false
```
