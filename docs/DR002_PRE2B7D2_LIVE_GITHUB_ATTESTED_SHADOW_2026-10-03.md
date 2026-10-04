# DR-002 pre-2B-7D2 — Live GitHub-attested synthetic shadow

Work order: [F1-WO-DR002-PRE2B7D2-001 / Issue #146](https://github.com/F1Lllewellyn/f1-data-publisher/issues/146).
Recorded: 2026-10-04. The 2026-10-03 filename is the authorized checkpoint identifier.
Result: COMPLETED — independent GitHub CLI cryptographic verification PASS.
DR-002 remains **PROPOSED — NOT ACTIVATED**. This is synthetic execution evidence only.

## OBSERVED GITHUB FACT

Accepted predecessor PR #145 was merged unchanged as `444fee73a587532bccca38e34681717c51375531`.
Its three reviewed blobs matched after merge. The subsequent generated-artifact commit became the actual run head and documentation starting baseline: `be29ae581ee0f29e9f7e5105a86bcd9f1b1c6da7`.
Fresh main still matched this baseline before creating this documentation branch.

The user dispatched one new initial run after that merge. Coder did not dispatch, rerun, or rerun failed jobs.
The earlier run #1 (`37166164887`) is the accepted pre-attestation checkpoint, not a second dispatch for this work order.

| Run fact | Value |
|---|---|
| Run | [37171628089](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37171628089) |
| Run number / attempt | 2 / 1 |
| Event | workflow_dispatch |
| Workflow | DR-002 synthetic frozen producer shadow pilot |
| Workflow path | .github/workflows/dr002-frozen-producer-shadow-pilot.yml |
| Branch / ref | main / refs/heads/main |
| Head | `be29ae581ee0f29e9f7e5105a86bcd9f1b1c6da7` |
| Run created / started | 2026-10-04T02:37:31Z / 2026-10-04T02:37:31Z |
| Terminal run updated timestamp | 2026-10-04T02:40:30Z |
| Run status / conclusion | completed / success |
| Job ID / name | 111345568017 / shadow |
| Job created / started / completed | 2026-10-04T02:37:35Z / 2026-10-04T02:37:37Z / 2026-10-04T02:40:29Z |
| Job conclusion / runner | success / GitHub-hosted ubuntu-latest |

The run API exposes updated_at rather than a separate completion timestamp; the job completion is recorded separately above.

| Step | Started UTC | Completed UTC | Conclusion |
|---|---|---|---|
| Set up job | 2026-10-04T02:37:38Z | 2026-10-04T02:37:40Z | success |
| Run actions/checkout@v4 | 2026-10-04T02:37:40Z | 2026-10-04T02:40:24Z | success |
| Run actions/setup-python@v5 | 2026-10-04T02:40:24Z | 2026-10-04T02:40:24Z | success |
| One synthetic frozen-mode producer CLI shadow | 2026-10-04T02:40:24Z | 2026-10-04T02:40:25Z | success |
| Attest exact successful shadow manifest | 2026-10-04T02:40:25Z | 2026-10-04T02:40:26Z | success |
| Preserve attestation bundle and factual metadata | 2026-10-04T02:40:26Z | 2026-10-04T02:40:26Z | success |
| Run actions/upload-artifact@v4 | 2026-10-04T02:40:26Z | 2026-10-04T02:40:27Z | success |
| Post Run actions/setup-python@v5 | 2026-10-04T02:40:27Z | 2026-10-04T02:40:27Z | success |
| Post Run actions/checkout@v4 | 2026-10-04T02:40:27Z | 2026-10-04T02:40:28Z | success |
| Complete job | 2026-10-04T02:40:28Z | 2026-10-04T02:40:28Z | success |

| Artifact fact | Value |
|---|---|
| ID | 11291846463 |
| Name | dr002-frozen-producer-shadow-37171628089-1 |
| Size | 22868 bytes |
| ZIP SHA-256 | `95b44890fb16b516e603177b24a8f029b297cf06626d250da3c62ef24e881853` |
| Created / updated | 2026-10-04T02:40:27Z / 2026-10-04T02:40:27Z |
| Expires | 2027-01-02T02:37:34Z |
| Expired at inspection | false |

The downloaded ZIP hash independently equals GitHub's digest. Exactly 13 files were preserved beneath `gha-37171628089-1/`: execution_manifest.json, shadow_report.md, github_attestation.bundle.json, github_attestation_metadata.json, and the nine evidence files listed below. No scientific receipt file exists.

## OBSERVED ARTIFACT FACT

Exact execution_manifest.json SHA-256: `01ed0c0139c037e4a48b81df4314d8b0701e7fd30abe1762dee0d329eeadf111`.
Auxiliary file hashes:

| File | Exact-byte SHA-256 |
|---|---|
| shadow_report.md | `287794f7b952f03a2fe67675a53d1f14d54c392fd9d87c1adf08f1c2d1746b4a` |
| github_attestation.bundle.json | `d73926f1706ad95c0bf76f5ab655ecbddbcc18cd65643e26d96c342adcb168cc` |
| github_attestation_metadata.json | `0d16a48171586b5c44523e2ea24905baba4506d2befdb8840d9bd9a558cb03cf` |

All nine exact-byte evidence digests were independently recomputed:

| Evidence file | SHA-256 |
|---|---|
| evidence/drivers.csv | `a5225adcc4ab55f9ea33c11de7cef4fc06a30171c56a7d681fd4c4987b335ba0` |
| evidence/forecast_metadata.json | `41d8b7227e06c4d18670e66e284ead7f62d70fd689711556f93610ba65bf5d83` |
| evidence/forecast_rows.csv | `6633a01667d72df2749dbe58bc8f7f433b02cc912dc76dd2a6438edb0e6f88b2` |
| evidence/frozen_input_manifest.json | `6a4c7ba55884fbc989c7d19146d37b1470e85d78b75d5910935d8932d27fe6ec` |
| evidence/producer_audit.json | `72aa6c0bf58402f40821e7230f98a6691f572f7bd2dea3bc50dbb48111c23cc7` |
| evidence/producer_code.py | `8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564` |
| evidence/source_snapshot_manifest.csv | `91dbed9ad7704d2f368934f416b96f770611e3b1526f4a33d1721e8a71a2bcb8` |
| evidence/starting_grid.csv | `5562a093d45052ea2b1f6360b2b98d3960cf9671c9f3eb63e62a2edd52b77d76` |
| evidence/weather.csv | `9430d44f65329bdc68ba2afe20a577ace75f7643b90909805ba1a047f2631d52` |

The frozen-input manifest digest equals `6a4c7ba55884fbc989c7d19146d37b1470e85d78b75d5910935d8932d27fe6ec`.
Producer code bytes independently recompute to SHA-256 `8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564` and Git blob `af27586668c767de126af829c1131c6bae4634ad`.

Declared synthetic CSV counts independently recompute: drivers 2, starting_grid 2, weather 1.
Exactly two synthetic output rows exist: driver 20 / Synthetic Twenty / McLaren and driver 10 / Synthetic Ten / Ferrari.
Audit driver universe count is 2; all six undeclared source categories have zero rows.
Audit and metadata use frozen_manifest input mode; broad_discovery_used=false.

Execution manifest status is SHADOW_EXECUTION_ONLY_NOT_A_PRODUCTION_FORECAST; execution_mode is manual_github_synthetic_frozen_shadow.
Scope is event synthetic_dr002_frozen_producer_v1, meeting synthetic-meeting, session synthetic-session, gate post_qualifying, lane stable_baseline.
Producer exit code is 0, generated_row_count=2, source_readiness=0.48, producer_run_id=20261004T024025Z.
The producer's output rows and metadata independently agree on generation time **2026-10-04T02:40:25Z**, within the observed execution step. It was not supplied as a historical time.
producer_output_sandbox_disposed=true; checkout_production_outputs_written=false; production_forecast_generated=false; synthetic_inputs=true.

The unchanged inner producer output retains historical status/blind-note wording. That wording is artifact evidence, not authorization to publish these rows or claim blind eligibility. The outer shadow manifest's false trust flags govern this checkpoint.

Attestation metadata ID: [52510013](https://github.com/F1Lllewellyn/f1-data-publisher/attestations/52510013).
Metadata subject path: `_runtime/dr002_pre2b7c_frozen_producer_shadow/gha-37171628089-1/execution_manifest.json`.
Its subject digest independently matches the exact manifest bytes. Run ID, attempt, head, repository, workflow path/name/ref match GitHub's observed run.
The successful preservation step copied the action-produced bundle; logs identify its runner-temporary attestation.json path. The verifier-returned bundle is JSON-equivalent to the downloaded bundle. No separate download of the original runner-temporary bytes is available; no independent byte-comparison claim is made for that inaccessible temporary file.

## CRYPTOGRAPHICALLY VERIFIED GITHUB PROVENANCE

GitHub CLI **2.102.0** from the official GitHub release was used. Its Linux amd64 release archive SHA-256 matched the official checksums: `bb766f710eef8ede859c18578c72c327597cd4c8a85b06001b1f3843c6019386`.

The preferred online command, with the repository/workflow/ref/source-digest/signer-digest constraints below but without --bundle, exited **4** because GitHub CLI has no API login/token. This was a local verifier-access limitation, not an attestation failure or workflow retry.
Saved-bundle verification with current default trusted roots succeeded, exit **0**. Public Good Sigstore verification was not disabled; no custom trust roots or fabricated bindings were supplied.

Final executed command (relative paths identify the unchanged downloaded package):

```sh
gh attestation verify PATH/execution_manifest.json \
  --bundle PATH/github_attestation.bundle.json \
  --repo F1Lllewellyn/f1-data-publisher \
  --signer-workflow F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-frozen-producer-shadow-pilot.yml \
  --source-ref refs/heads/main \
  --source-digest be29ae581ee0f29e9f7e5105a86bcd9f1b1c6da7 \
  --signer-digest be29ae581ee0f29e9f7e5105a86bcd9f1b1c6da7 \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --deny-self-hosted-runners \
  --format json
```

An additional attempt to combine --cert-identity with --signer-workflow was rejected by CLI argument validation (exit 1) because those options are mutually exclusive. No evidence verification occurred in that attempt. The final command retains the required signer-workflow constraint and both exact commit constraints; no constraint was weakened to bypass a failed signature.

Verified statement type: https://in-toto.io/Statement/v1.
Verified predicate type: https://slsa.dev/provenance/v1.
Verified build type: https://actions.github.io/buildtypes/workflow/v1.
Verified subject: execution_manifest.json with digest `01ed0c0139c037e4a48b81df4314d8b0701e7fd30abe1762dee0d329eeadf111`.

The verifier returned these certificate facts:

```json
{
  "certificateIssuer": "CN=sigstore-intermediate,O=sigstore.dev",
  "subjectAlternativeName": "https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-frozen-producer-shadow-pilot.yml@refs/heads/main",
  "issuer": "https://token.actions.githubusercontent.com",
  "githubWorkflowTrigger": "workflow_dispatch",
  "githubWorkflowSHA": "be29ae581ee0f29e9f7e5105a86bcd9f1b1c6da7",
  "githubWorkflowName": "DR-002 synthetic frozen producer shadow pilot",
  "githubWorkflowRepository": "F1Lllewellyn/f1-data-publisher",
  "githubWorkflowRef": "refs/heads/main",
  "buildSignerURI": "https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-frozen-producer-shadow-pilot.yml@refs/heads/main",
  "buildSignerDigest": "be29ae581ee0f29e9f7e5105a86bcd9f1b1c6da7",
  "runnerEnvironment": "github-hosted",
  "sourceRepositoryURI": "https://github.com/F1Lllewellyn/f1-data-publisher",
  "sourceRepositoryDigest": "be29ae581ee0f29e9f7e5105a86bcd9f1b1c6da7",
  "sourceRepositoryRef": "refs/heads/main",
  "sourceRepositoryIdentifier": "1262398563",
  "sourceRepositoryOwnerURI": "https://github.com/F1Lllewellyn",
  "sourceRepositoryOwnerIdentifier": "291632822",
  "buildConfigURI": "https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-frozen-producer-shadow-pilot.yml@refs/heads/main",
  "buildConfigDigest": "be29ae581ee0f29e9f7e5105a86bcd9f1b1c6da7",
  "buildTrigger": "workflow_dispatch",
  "runInvocationURI": "https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37171628089/attempts/1",
  "sourceRepositoryVisibilityAtSigning": "public"
}
```

Verified transparency timestamp:

```json
[
  {
    "type": "Tlog",
    "uri": "https://rekor.sigstore.dev",
    "timestamp": "2026-10-04T13:40:26+11:00"
  }
]
```

The returned offset timestamp is exactly **2026-10-04T02:40:26Z** in UTC. The saved bundle records Rekor log index 3076202973, integratedTime 1791081626, inclusion promise and inclusion proof/checkpoint. GitHub CLI accepted the signature and transparency evidence using its trusted-root verification; hand-decoding alone was not used as proof.

Certificate source/signer digests and ref independently corroborate the exact GitHub run head. The verified statement resolved dependency also identifies that commit, and its invocation URI identifies run 37171628089 / attempt 1.
The returned verifiedIdentity issuer regex is `.*` despite the supplied --cert-oidc-issuer option; the actual verified certificate issuer is explicitly recorded above and independently checked equal to https://token.actions.githubusercontent.com. No claim is made that the returned regex itself enforces that issuer.

## EXECUTED LIVE SYNTHETIC SHADOW FACT

GitHub API run/job facts, successful CLI step logs, exact artifact hashes, unchanged run-head dependencies and cryptographically verified manifest provenance jointly support that the accepted frozen-mode producer path executed in this GitHub run with the listed synthetic inputs.
Cryptographic verification authenticates the workflow association of these exact manifest bytes. It does not alone establish the truth of every workflow-authored predicate or artifact field; those were checked separately as described above.

Every declared dependency Git blob on the actual run head matched. The additional reviewed attestation test blob also matched:

| Path | Expected and independently recomputed Git blob | Result |
|---|---|---|
| `.github/workflows/dr002-frozen-producer-shadow-pilot.yml` | `850e96cbea815c3dec3f14c3a731f2f65cce2944` | PASS |
| `tests/test_dr002_frozen_producer_attestation_v1.py` | `7439dca52468685f3f2b55690ebc90d6ae44f777` | PASS |
| `docs/DR002_PRE2B7D1_GITHUB_ATTESTED_SHADOW_2026-10-03.md` | `1c72917190f136dbfc42759d3515512dd63a5037` | PASS |
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | `af27586668c767de126af829c1131c6bae4634ad` | PASS |
| `scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py` | `1d3bfaf713807e799a6323875de670dc8d4e1a85` | PASS |
| `tests/test_dr002_frozen_producer_shadow_pilot_v1.py` | `defbc899f73b9b8bd6c01a50183e825bfb5ead8a` | PASS |
| `docs/DR002_PRE2B7C1_FROZEN_PRODUCER_SHADOW_WORKFLOW_2026-10-03.md` | `6bd54210c6d83c0cf38761b7dd3f2ab5b9aa82e0` | PASS |
| `docs/DR002_PRE2B7C2_LIVE_FROZEN_PRODUCER_SHADOW_2026-10-03.md` | `f033e4601443b85096a6ef07695de5462d2e2909` | PASS |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `91dfffd80635f643a2f605f75422c6311e93a9c6` | PASS |
| `.github/workflows/f1-actual-forecast-producer-v1.yml` | `e115718f2b7fed9f0e87a47b1138b3462b9b6cb1` | PASS |
| `.github/workflows/f1-automated-forecast-gate-orchestrator-v1.yml` | `32a1210a2f43065e9d65a9bd858c059b6166700f` | PASS |
| `scripts/forecast_bundles/orchestrate_forecast_gate_pipeline_v1.py` | `1f95311dc6f3874e207fdc889a1a1b49c9acafab` | PASS |

The shadow workflow has no repository commit/push step. Job logs show no dispatch, production-workflow invocation, stable-engine execution or repository-output publication. The wrapper's evidence records disposed sandbox and no checkout production outputs. No F1/OpenF1 request occurred in this synthetic workflow or evidence inspection.
The run head predates the run; fresh main remained that same SHA after completion. Coder performed only the accepted predecessor merge and this authorized documentation branch/PR mutation.

## UNPROVEN / NOT CLAIMED

All outer-manifest and auxiliary-metadata ceilings remain:

```json
{"production_authenticated":false,"historical_availability_proven":false,"stable_engine_execution_proven":false,"blind_validation_eligible":false,"dr002_activated":false}
```

GitHub execution provenance authentication is not production/source authentication.
No F1/OpenF1 publisher authenticity, historical availability, observation completeness, protected stable-engine execution, live forecast lock, live outcome boundary, revision completeness, accuracy improvement, blind eligibility or production readiness is proven.
No verified_receipt_bindings or DR-002 producer/engine/lock/outcome/revision receipt was created.
The stable_baseline lane label is not engine execution proof.

DR-002 remains PROPOSED — NOT ACTIVATED. Forecast gate remains OFF. Promotion remains NOT ALLOWED.
Engine_2026-06-07_STABLE and canonical workbook were untouched by this work. No production enforcement began. Pipedream/Gmail were not used.

## Documentation validation and review boundary

No producer was executed locally; no workflow was dispatched or rerun by Coder.
No repository test suite was rerun: relevant reviewed code was unchanged.
Validation comprised exact artifact hashing, CSV/count/audit checks, metadata/run identity comparison, actual run-head Git blob checks and independent GitHub CLI signature/provenance verification.
Exactly one new Markdown checkpoint is authorized in this Work Result PR; no raw artifact or implementation file is committed.
This PR is not self-accepting and must remain unmerged for Science / Architecture Adviser review. Rollback is removal/revert of this documentation-only addition.
