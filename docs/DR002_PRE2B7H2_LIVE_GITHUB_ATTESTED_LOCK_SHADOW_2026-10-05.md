# DR-002 pre-2B-7H2 — Live GitHub-attested forecast-lock shadow

Work order: [F1-WO-DR002-PRE2B7H2-001 / Issue #174](https://github.com/F1Lllewellyn/f1-data-publisher/issues/174)  
Recorded: 2026-10-05  
Result: COMPLETED — one live synthetic lock-shadow run and independent saved-bundle verification PASS.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Observed GitHub run

The user manually dispatched the first and only run of the H1 workflow after H2 authorization. Coder did not dispatch, rerun, or rerun failed jobs.

| Run fact | Value |
|---|---|
| Run | [37377556251](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37377556251) |
| Run number / attempt | 1 / 1 |
| Event | `workflow_dispatch` |
| Workflow | `DR-002 synthetic forecast lock shadow pilot` |
| Workflow path | `.github/workflows/dr002-forecast-lock-shadow-pilot.yml` |
| Branch / ref | `main` / `refs/heads/main` |
| Head | `bd3e5574713405f11cc401f94a6ce7a2b8d3e9a7` |
| Actor / triggering actor | `F1Lllewellyn` / `F1Lllewellyn` |
| Created / started | `2026-10-05T21:41:43Z` / `2026-10-05T21:41:43Z` |
| Terminal updated timestamp | `2026-10-05T21:45:47Z` |
| Status / conclusion | `completed` / `success` |
| Job ID / name | `111990610663` / `shadow` |
| Job created / started / completed | `2026-10-05T21:41:45Z` / `2026-10-05T21:41:48Z` / `2026-10-05T21:45:46Z` |
| Job conclusion | `success` |
| Runner | GitHub-hosted, runner `GitHub Actions 1000009726`, group `GitHub Actions`, label `ubuntu-latest` |
| Runner image | Ubuntu 24.04, image version `20260927.320.1`, runner version `2.337.0` |

The run API exposes `updated_at`, not a separate run-completion field; the job completion time is recorded separately.

| Step | Started UTC | Completed UTC | Conclusion |
|---|---|---|---|
| Set up job | `2026-10-05T21:41:49Z` | `2026-10-05T21:41:50Z` | success |
| Run `actions/checkout@v4` | `2026-10-05T21:41:50Z` | `2026-10-05T21:45:39Z` | success |
| Run `actions/setup-python@v5` | `2026-10-05T21:45:39Z` | `2026-10-05T21:45:39Z` | success |
| One accepted synthetic frozen producer shadow | `2026-10-05T21:45:39Z` | `2026-10-05T21:45:40Z` | success |
| One Gate 2B-4 synthetic forecast lock shadow | `2026-10-05T21:45:40Z` | `2026-10-05T21:45:40Z` | success |
| Attest exact successful lock manifest | `2026-10-05T21:45:40Z` | `2026-10-05T21:45:42Z` | success |
| Preserve attestation bundle and factual metadata | `2026-10-05T21:45:42Z` | `2026-10-05T21:45:43Z` | success |
| Run `actions/upload-artifact@v4` | `2026-10-05T21:45:43Z` | `2026-10-05T21:45:44Z` | success |
| Post `actions/setup-python@v5` | `2026-10-05T21:45:44Z` | `2026-10-05T21:45:44Z` | success |
| Post `actions/checkout@v4` | `2026-10-05T21:45:44Z` | `2026-10-05T21:45:44Z` | success |
| Complete job | `2026-10-05T21:45:44Z` | `2026-10-05T21:45:44Z` | success |

The job log's `GITHUB_TOKEN Permissions` block reports `Attestations: write`, `Contents: read`, and implicit `Metadata: read`. The committed workflow separately declares `id-token: write`; the successful GitHub attestation and its Fulcio certificate demonstrate the OIDC path was exercised. No broader repository permission was observed.

## Artifact verification

| Artifact fact | Value |
|---|---|
| ID | `11371759926` |
| Name | `dr002-forecast-lock-shadow-37377556251-1` |
| Size | 28,515 bytes |
| GitHub-reported digest | `sha256:b15a81d9aa30a6db2581541166bf25500d3f68e683cb0cd7499d5b55afdb1e0d` |
| Independently recomputed ZIP SHA-256 | `b15a81d9aa30a6db2581541166bf25500d3f68e683cb0cd7499d5b55afdb1e0d` |
| Created / updated | `2026-10-05T21:45:43Z` / `2026-10-05T21:45:43Z` |
| Expires | `2027-01-03T21:41:45Z` |
| Expired at inspection | false |

The archive contains exactly 18 files: the expected same-run producer-shadow package and the expected lock-shadow package. The archived roots omit only the upload action's common `_runtime/` ancestor.

Key exact-byte hashes independently recomputed from the downloaded artifact:

| File | SHA-256 |
|---|---|
| Producer `execution_manifest.json` | `0f7c510cd341d4eb1016e85946f52cf4458e7474347a094c113c8aedb6e62937` |
| Producer `evidence/forecast_rows.csv` | `c6a75f1f355c5bdb2a760b969bd442818189349415a9b8695baf8d0e50932714` |
| Lock `forecast_payload.csv` | `c6a75f1f355c5bdb2a760b969bd442818189349415a9b8695baf8d0e50932714` |
| `producer_execution_receipt.json` | `0c8c9905476c88c0310fed501018c817043ab3c575c9d2408f462f67ee756194` |
| `forecast_lock_receipt.json` | `4e0857b96075d1df1f7424b56fb98ee30b6a609338285d25c006985178c6b4ce` |
| `lock_report.md` | `0b3f47e6b44eff3a90d4d3170b74598b5f9d184b7f1ccd5ddf2d90bc19792066` |
| `lock_execution_manifest.json` | `2b1375722b7fea1759ef56e6935277c8c96189db847de5a9972283905712520c` |
| `github_attestation.bundle.json` | `de0ee93319cf427746933b4abba8a0bce1c80266ad72b5ffa18f9932fc39fd1f` |
| `github_attestation_metadata.json` | `deb73c9b30b7efb58550368bf193ab498dc137e719a3cb6351f5b46530ae1570` |

The exact copied `forecast_payload.csv` bytes equal the same-run producer-shadow `forecast_rows.csv` bytes. Their SHA-256 also equals every required declaration:

- producer-shadow `evidence_sha256["forecast_rows.csv"]`;
- synthetic producer receipt `forecast_payload_sha256`;
- lock receipt `forecast_payload_sha256`;
- lock receipt `stored_payload_sha256`; and
- lock execution manifest `forecast_payload_sha256`.

The manifest's exact-byte hashes for all four pre-attestation lock evidence files independently match. Its producer-shadow manifest hash also matches the same-run producer manifest. The canonical producer-receipt digest is `629141be910588edbdfb1a0ea67219074ed56b578e70e63a357f6dd6e8addc78`; the canonical lock-receipt digest is `738f74bf8b6d740e3a363c93283ff83f5a56f657cd82f81f65e4b19f1a728d3c`.

The forecast lock's only parent is synthetic producer receipt `producer_execution:bf8d1a9738e55b3d36f19a08ed11730d791086c2909bb9a8c69d6ce7fbf860d1`. No `engine_execution` receipt exists. No `verified_receipt_bindings` value exists. The producer receipt has no parents and its engine fields are null.

The observed internal order is structurally valid:

```text
forecast_generation_utc:     2026-10-05T21:45:40Z
internal lock_utc:           2026-10-05T21:45:40Z
lock receipt created UTC:    2026-10-05T21:45:40Z
```

Equality is permitted by the unchanged Gate 2B-4 constructor. These workflow-authored timestamps are not clock authentication.

The explicit storage reference is `artifact-relative:_runtime/dr002_pre2b7h_forecast_lock_shadow/gha-37377556251-1/forecast_payload.csv`. Artifact preservation is evidence storage for this synthetic shadow; it does not prove production-grade immutability, retention, or durability.

All 12 trust-ceiling fields in both the lock execution manifest and the attestation metadata remain false: producer/lock external binding, lock-clock authentication, durable-storage proof, full Gate 2B-1 verification, production authentication, historical availability, stable-engine execution, blind eligibility, production forecast locking, DR-002 activation, and promotion.

## Independent GitHub/Sigstore verification

Attestation metadata ID: [52968369](https://github.com/F1Lllewellyn/f1-data-publisher/attestations/52968369).  
Subject path: `_runtime/dr002_pre2b7h_forecast_lock_shadow/gha-37377556251-1/lock_execution_manifest.json`.  
Exact subject SHA-256: `2b1375722b7fea1759ef56e6935277c8c96189db847de5a9972283905712520c`.

The saved bundle names that exact digest as its single subject. GitHub CLI 2.102.0 from the accepted pre-2B-7D2 verification toolchain was used; its retained Linux amd64 release archive still recomputes to the accepted official-checksum value `bb766f710eef8ede859c18578c72c327597cd4c8a85b06001b1f3843c6019386`.

Saved-bundle verification with current default trusted roots succeeded with exit 0. Public Good Sigstore verification was not disabled; no custom trust roots or fabricated bindings were supplied. The executed constraints were:

```sh
gh attestation verify lock_execution_manifest.json \
  --bundle github_attestation.bundle.json \
  --repo F1Lllewellyn/f1-data-publisher \
  --signer-workflow F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-forecast-lock-shadow-pilot.yml \
  --source-ref refs/heads/main \
  --source-digest bd3e5574713405f11cc401f94a6ce7a2b8d3e9a7 \
  --signer-digest bd3e5574713405f11cc401f94a6ce7a2b8d3e9a7 \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --deny-self-hosted-runners \
  --format json
```

Verified provenance:

| Field | Verified value |
|---|---|
| Statement type | `https://in-toto.io/Statement/v1` |
| Predicate type | `https://slsa.dev/provenance/v1` |
| Build type | `https://actions.github.io/buildtypes/workflow/v1` |
| Subject | `lock_execution_manifest.json` / `2b1375722b7fea1759ef56e6935277c8c96189db847de5a9972283905712520c` |
| Certificate issuer | `CN=sigstore-intermediate,O=sigstore.dev` |
| OIDC issuer | `https://token.actions.githubusercontent.com` |
| Certificate SAN / build signer | `https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-forecast-lock-shadow-pilot.yml@refs/heads/main` |
| Repository | `F1Lllewellyn/f1-data-publisher` |
| Workflow / ref | `.github/workflows/dr002-forecast-lock-shadow-pilot.yml` / `refs/heads/main` |
| Source digest | `bd3e5574713405f11cc401f94a6ce7a2b8d3e9a7` |
| Signer/build-config digest | `bd3e5574713405f11cc401f94a6ce7a2b8d3e9a7` |
| Runner environment | `github-hosted` |
| Workflow trigger | `workflow_dispatch` |
| Run invocation | `https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37377556251/attempts/1` |

The verified transparency timestamp returned by GitHub CLI is `2026-10-06T06:45:42+09:00`, exactly `2026-10-05T21:45:42Z`. The saved bundle records Rekor integrated time `1791236742`, the same UTC instant, plus an inclusion promise, proof, and checkpoint. Therefore the exact attested manifest bytes existed no later than `2026-10-05T21:45:42Z`.

The verifier's returned identity summary uses an issuer regex of `.*` despite the supplied `--cert-oidc-issuer` constraint. The actual verified certificate issuer is explicitly returned as `https://token.actions.githubusercontent.com` and was checked equal to the required issuer. No constraint was removed or weakened to obtain a pass.

## Run-head dependency reconciliation

Every relevant dependency independently recomputed to its accepted Git blob at the exact run head:

| Path | Git blob | Result |
|---|---|---|
| `.github/workflows/dr002-forecast-lock-shadow-pilot.yml` | `4daa7c0ebb22f9b31dd35f5b0109c2eb227a976c` | PASS |
| `scripts/forecast_bundles/dr002_forecast_lock_shadow_pilot_v1.py` | `17b129e97f8a73dbd216dc717ce6ad8ed7bc0a9a` | PASS |
| `tests/test_dr002_forecast_lock_shadow_pilot_v1.py` | `69ebaa2d27d5f0f3356ee2072dd2bf88d279d1dd` | PASS |
| `docs/DR002_PRE2B7H1_GITHUB_ATTESTED_LOCK_SHADOW_2026-10-05.md` | `bae42d4a04668024984c0081d32bb3bb6ecc1328` | PASS |
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | `af27586668c767de126af829c1131c6bae4634ad` | PASS |
| `scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py` | `1d3bfaf713807e799a6323875de670dc8d4e1a85` | PASS |
| `scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py` | `064d93ee5ae30354590a3fb95be598c5fe8b3b9a` | PASS |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` | PASS |
| `scripts/forecast_bundles/create_forecast_bundles_v1.py` | `1cdba43d3b22a1abcfb65bbbd6b2bfebd4684018` | PASS |

## Prohibited paths and claim ceiling

The job logs show no production workflow dispatch, repository commit/push, production locker call, OpenF1/F1 source request, Pipedream/Gmail use, stable-engine execution, verified binding, or canonical workbook mutation. The workflow has read-only repository contents permission and no commit/push step. The producer evidence records a disposed sandbox, `checkout_production_outputs_written=false`, `production_forecast_generated=false`, and `synthetic_inputs=true`.

The live run proves only that exact synthetic producer payload bytes were mechanically bound through the unchanged Gate 2B-4 `build_forecast_lock`, and that the exact successful lock manifest bytes were cryptographically tied to the expected GitHub workflow, run, attempt, ref, and head. The verified transparency time proves those manifest bytes existed no later than that instant.

It does not authenticate the internal lock clock, receipt-created time, producer generation clock, publisher/source truth, earliest or historical availability, revision completeness, durable storage, protected stable-engine execution, blind eligibility, predictive accuracy, or production enforcement. The synthetic producer and lock receipts remain internally hash-linked but externally unbound; this is not a full verified Gate 2B-1 chain or a production forecast lock.

No implementation file changed, no test suite was rerun, and no workflow was dispatched or retried by Coder. This Work Result adds one Markdown checkpoint only and remains unmerged for independent Science / Architecture Adviser review.

## Checkpoint

```text
live_lock_shadow_run_executed: true
run_attempt_one_only: true
exact_forecast_payload_bound: true
gate2b4_lock_constructor_exercised_live: true
github_attestation_cryptographically_verified: true
attested_manifest_existed_by_tlog: true
lock_clock_authenticated: false
producer_receipt_externally_bound: false
lock_receipt_externally_bound: false
full_gate2b1_chain_verified: false
durable_storage_proven: false
production_forecast_locked: false
stable_engine_execution_proven: false
blind_validation_eligible: false
dr002_activated: false
promotion_allowed: false
```
