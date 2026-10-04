# DR-002 pre-2B-7E2 — live GitHub-attested source capture

Work order: F1-WO-DR002-PRE2B7E2-001 / [Issue #150](https://github.com/F1Lllewellyn/f1-data-publisher/issues/150).
Recorded 2026-10-04. Work Result: COMPLETED, pending independent Adviser review.
DR-002 remains **PROPOSED — NOT ACTIVATED**; forecast gate OFF; promotion NOT ALLOWED.

## OBSERVED GITHUB FACT

PR #149 was merged unchanged by Coder as `20145a7920a735535a0a10b23540da7c4b50296b`.
Reviewed head: `a0328574555aefdd883aaff15dda075d528714d0`. Its exact three landed blobs matched the work order.
The human subsequently dispatched exactly one new run. Adviser comments 5983682587 and 5983717188 identify that run. Fresh Actions retrieval corroborates run #2 / attempt 1; the only other capture run is historical #1, `37133694090`. Coder dispatched/reran nothing.

[Run 37229086347](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37229086347)

```json
{
  "id": 37229086347,
  "name": "DR-002 isolated capture provenance pilot",
  "path": ".github/workflows/dr002-capture-provenance-pilot.yml",
  "run_number": 2,
  "run_attempt": 1,
  "event": "workflow_dispatch",
  "head_branch": "main",
  "head_sha": "ffe26a8427cf1c783336b67c519c5c177964febe",
  "created_at": "2026-10-04T19:39:05Z",
  "run_started_at": "2026-10-04T19:39:05Z",
  "updated_at": "2026-10-04T19:42:41Z",
  "status": "completed",
  "conclusion": "success"
}
```
The ref is `refs/heads/main`. The run API exposes `updated_at`; this is not relabeled as an exact completion event. Job completion is separately exposed.

```json
{
  "id": 111514752319,
  "name": "fixed-weather-capture",
  "created_at": "2026-10-04T19:39:06Z",
  "started_at": "2026-10-04T19:39:09Z",
  "completed_at": "2026-10-04T19:42:40Z",
  "conclusion": "success",
  "runner_name": "GitHub Actions 1000009676",
  "runner_group_name": "GitHub Actions"
}
```

| Step | Conclusion | Started UTC | Completed UTC |
|---|---|---|---|
| Set up job | success | 2026-10-04T19:39:09Z | 2026-10-04T19:39:11Z |
| Run actions/checkout@v4 | success | 2026-10-04T19:39:11Z | 2026-10-04T19:42:32Z |
| Run actions/setup-python@v5 | success | 2026-10-04T19:42:32Z | 2026-10-04T19:42:32Z |
| Fixed Baku Practice 2 weather capture (one request) | success | 2026-10-04T19:42:32Z | 2026-10-04T19:42:34Z |
| Attest exact successful source capture receipt | success | 2026-10-04T19:42:34Z | 2026-10-04T19:42:36Z |
| Preserve capture attestation bundle and factual metadata | success | 2026-10-04T19:42:36Z | 2026-10-04T19:42:37Z |
| Upload runtime-only evidence and HOLD diagnostics | success | 2026-10-04T19:42:37Z | 2026-10-04T19:42:38Z |
| Post Run actions/setup-python@v5 | success | 2026-10-04T19:42:38Z | 2026-10-04T19:42:38Z |
| Post Run actions/checkout@v4 | success | 2026-10-04T19:42:38Z | 2026-10-04T19:42:38Z |
| Complete job | success | 2026-10-04T19:42:38Z | 2026-10-04T19:42:38Z |

All capture, attestation, metadata-preservation and upload steps succeeded. Logs corroborate the fixed capture invocation and action bundle path `/home/runner/work/_temp/YHCe2a/attestation.json`. This temporary runner file was not independently downloaded; no separate byte comparison to that inaccessible original is claimed. Reviewed packaging code copies the bundle bytes and verifies read-back.

Artifact metadata:

```json
{
  "id": 11312353979,
  "name": "dr002-weather-capture-37229086347-1",
  "size_in_bytes": 13576,
  "url": "https://api.github.com/repos/F1Lllewellyn/f1-data-publisher/actions/artifacts/11312353979",
  "archive_download_url": "https://api.github.com/repos/F1Lllewellyn/f1-data-publisher/actions/artifacts/11312353979/zip",
  "expired": false,
  "created_at": "2026-10-04T19:42:38Z",
  "expires_at": "2027-01-02T19:39:06Z",
  "updated_at": "2026-10-04T19:42:38Z",
  "digest": "sha256:9b8ef27fc86513619ee092b136c02f2b58673271000a3c14e18a1e81cc59d67e",
  "workflow_run": {
    "id": 37229086347,
    "repository_id": 1262398563,
    "head_repository_id": 1262398563,
    "head_branch": "main",
    "head_sha": "ffe26a8427cf1c783336b67c519c5c177964febe"
  }
}
```
The downloaded ZIP is 13,576 bytes and independently hashes to `9b8ef27fc86513619ee092b136c02f2b58673271000a3c14e18a1e81cc59d67e`, matching GitHub. Not expired at inspection.

## Run-head dependency verification

All ten fresh Git blob checks PASS at actual run head `ffe26a8427cf1c783336b67c519c5c177964febe`. Observed main before publication was the same commit.

| Path | Verified Git blob |
|---|---|
| `.github/workflows/dr002-capture-provenance-pilot.yml` | `883fcbc1a00ec9ae1dd6dd40423a03af05ae1fe3` |
| `scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py` | `b9b1f9acc1be30d5b7cdf42424853e3d652b9466` |
| `tests/test_dr002_capture_provenance_pilot_v1.py` | `fa11b27c7e32638985944f404815a1a7fe04e4a2` |
| `tests/test_dr002_capture_attestation_v1.py` | `bf880b206c128ae77c4d435e6c532895b4fea9ce` |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| `docs/DR002_GATE2B2A_CAPTURE_PROVENANCE_PILOT_2026-10-03.md` | `675f6884b631dbc5cd158195ea41005b3252e741` |
| `docs/DR002_GATE2B2B_LIVE_CAPTURE_CHECKPOINT_2026-10-03.md` | `ba08ea34754af1a3d09c2a1751618474bbf7a954` |
| `docs/DR002_PRE2B7D2_LIVE_GITHUB_ATTESTED_SHADOW_2026-10-03.md` | `d07a0ff228227378af863313a487e6d64c21fd50` |
| `docs/DR002_PRE2B7E1_GITHUB_ATTESTED_CAPTURE_2026-10-03.md` | `f37e72326864f4dcb485025b1a85ae20c33bb7f5` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `91dfffd80635f643a2f605f75422c6311e93a9c6` |

## OBSERVED ARTIFACT FACT

Exactly seven logical files occur under `gha-37229086347-1/`. No unexpected scientific receipt or external binding file exists. Independently recomputed exact-byte hashes:

| File | SHA-256 |
|---|---|
| `pilot_report.md` | `5379b6ab195855305c20930d4c4aa5a846236aed1dc4c07aceaade7cd06b8f1d` |
| `github_attestation_metadata.json` | `a6389cf388e15dfad0590d2a265a18532a112712e551c86ab4b9539c15262bcb` |
| `capture_manifest.json` | `5b7ff5ffae2e6b1192272be9b2cf7c8ea2e4483977b809f8abce4feacc4efd30` |
| `github_attestation.bundle.json` | `34f4a87e79a80094dd82c4b6abcf36f25586b20425649239d3f6559d893e8fd1` |
| `source_capture_receipt.json` | `3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69` |
| `raw/openf1_weather.response.json` | `bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6` |
| `normalized/openf1_weather.normalized.json` | `0bcdab4dcb6ce16e96bbb6bef6f6bc15e7e04ded360466b8aa7e692947ec764c` |

The unchanged capture validator accepts all **85 rows**, each with meeting 1295 and session 11371, valid timezone-aware date, usable finite weather measurement and no duplicate canonical row. Raw length is **18,359 bytes**. Normalized bytes equal canonical encoding of the independently parsed raw rows; their hash matches the manifest.

Raw hash matches receipt payload, capture manifest, metadata and read-back hash. HTTP status is 200; readback_verified is true; validation_status is CAPTURED_UNBOUND. HTTP status and request timing are workflow-authored capture facts corroborated by code/log execution, not a separately signed OpenF1 response.

Receipt structural/temporal validation, parentless type, fixed source/scope/implementation, capture_ref, deterministic observation-specific receipt ID, canonical receipt hash, metadata identities and false trust flags all independently passed.

Exact receipt bytes equal `canonical_json_bytes(receipt)` in THIS package. Consequently exact-file SHA-256 equals canonical `receipt_sha256`, both `3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69`. This was checked, not assumed: a different whitespace/serialization representation could retain the canonical hash while changing the exact attestation subject digest.

Exact source-capture receipt:

```json
{
  "parent_receipt_ids": [],
  "payload": {
    "capture_ref": "_runtime/dr002_gate2b2_capture_pilot/gha-37229086347-1/raw/openf1_weather.response.json",
    "event_time_utc": null,
    "first_observed_utc": "2026-10-04T19:42:34.866980Z",
    "implementation": "scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py",
    "ingested_utc": "2026-10-04T19:42:34.867390Z",
    "publisher_time_utc": null,
    "source_id": "openf1:weather:1295:11371",
    "source_sha256": "bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6",
    "source_uri": "https://api.openf1.org/v1/weather?session_key=11371"
  },
  "receipt_created_utc": "2026-10-04T19:42:34.868462Z",
  "receipt_id": "source_capture:c4564601dd7a9c75648a0fc6594088f2339ed404d5cce721658f50de3190929b",
  "receipt_type": "source_capture",
  "schema_version": "dr002-receipt-v1",
  "scope": {
    "event_id": "2026_1295_azerbaijan_baku_baku",
    "meeting_id": "1295",
    "session_id": "11371"
  }
}
```
Capture manifest:

```json
{
  "binding_status": "UNBOUND",
  "byte_count": 18359,
  "dr002_activated": false,
  "endpoint": "weather",
  "event_id": "2026_1295_azerbaijan_baku_baku",
  "first_observed_utc": "2026-10-04T19:42:34.866980Z",
  "historical_availability_proven": false,
  "http_method": "GET",
  "http_status": 200,
  "implementation": "scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py",
  "implementation_git_sha": "ffe26a8427cf1c783336b67c519c5c177964febe",
  "ingested_utc": "2026-10-04T19:42:34.867390Z",
  "meeting_id": "1295",
  "normalized_sha256": "0bcdab4dcb6ce16e96bbb6bef6f6bc15e7e04ded360466b8aa7e692947ec764c",
  "production_authenticated": false,
  "raw_artifact_path": "_runtime/dr002_gate2b2_capture_pilot/gha-37229086347-1/raw/openf1_weather.response.json",
  "readback_sha256": "bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6",
  "readback_verified": true,
  "reason": null,
  "receipt_created_utc": "2026-10-04T19:42:34.868462Z",
  "receipt_path": "_runtime/dr002_gate2b2_capture_pilot/gha-37229086347-1/source_capture_receipt.json",
  "receipt_sha256": "3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69",
  "request_started_utc": "2026-10-04T19:42:33.927655Z",
  "request_uri": "https://api.openf1.org/v1/weather?session_key=11371",
  "response_completed_utc": "2026-10-04T19:42:34.866980Z",
  "row_count": 85,
  "run_id": "gha-37229086347-1",
  "schema_version": "dr002-capture-pilot-v1",
  "session_id": "11371",
  "source_sha256": "bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6",
  "validation_status": "CAPTURED_UNBOUND"
}
```
Preserved factual attestation metadata:

```json
{
  "attestation_id": "52636060",
  "attestation_url": "https://github.com/F1Lllewellyn/f1-data-publisher/attestations/52636060",
  "binding_status": "UNBOUND",
  "capture_ref": "_runtime/dr002_gate2b2_capture_pilot/gha-37229086347-1/raw/openf1_weather.response.json",
  "dr002_activated": false,
  "first_observed_utc": "2026-10-04T19:42:34.866980Z",
  "git_head_sha": "ffe26a8427cf1c783336b67c519c5c177964febe",
  "historical_availability_proven": false,
  "ingested_utc": "2026-10-04T19:42:34.867390Z",
  "production_authenticated": false,
  "receipt_id": "source_capture:c4564601dd7a9c75648a0fc6594088f2339ed404d5cce721658f50de3190929b",
  "repository": "F1Lllewellyn/f1-data-publisher",
  "run_attempt": "1",
  "run_id": "37229086347",
  "schema_version": "dr002-github-source-capture-attestation-metadata-v1",
  "scope": {
    "event_id": "2026_1295_azerbaijan_baku_baku",
    "meeting_id": "1295",
    "session_id": "11371"
  },
  "source_sha256": "bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6",
  "source_uri": "https://api.openf1.org/v1/weather?session_key=11371",
  "subject_relative_path": "_runtime/dr002_gate2b2_capture_pilot/gha-37229086347-1/source_capture_receipt.json",
  "subject_sha256": "3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69",
  "workflow_name": "DR-002 isolated capture provenance pilot",
  "workflow_path": ".github/workflows/dr002-capture-provenance-pilot.yml",
  "workflow_ref": "F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-capture-provenance-pilot.yml@refs/heads/main"
}
```

The only scientific receipt is the original source_capture receipt. Attestation bundle and auxiliary metadata are not additional scientific receipts. All seven files were inspected; no raw OIDC/GitHub credential or verified_receipt_bindings is present. Auxiliary source inspection also confirms token values are not read into the package. Raw data consists of weather rows.

## CRYPTOGRAPHICALLY VERIFIED GITHUB PROVENANCE

[Attestation 52636060](https://github.com/F1Lllewellyn/f1-data-publisher/attestations/52636060).

Official GitHub CLI **2.102.0 (2026-09-30)** Linux amd64 archive downloaded from the official release. Archive SHA-256 `bb766f710eef8ede859c18578c72c327597cd4c8a85b06001b1f3843c6019386` matches that release's checksums. Initial tar extraction reported unsupported uid/gid ownership restoration; extraction of the binary with `--no-same-owner` succeeded. This was local tooling setup, not a workflow rerun or evidence verification failure.

Executed command (PATH denotes the downloaded unchanged package):

```sh
gh attestation verify PATH/source_capture_receipt.json \
  --bundle PATH/github_attestation.bundle.json \
  --repo F1Lllewellyn/f1-data-publisher \
  --signer-workflow F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-capture-provenance-pilot.yml \
  --source-ref refs/heads/main \
  --source-digest ffe26a8427cf1c783336b67c519c5c177964febe \
  --signer-digest ffe26a8427cf1c783336b67c519c5c177964febe \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --deny-self-hosted-runners \
  --format json
```

**PASS / exit 0**, empty stderr. One saved-bundle verification invocation; no weaker identity options or custom roots; Public Good Sigstore was not disabled. Current default trusted roots were used. Verifier-returned bundle is JSON-equivalent to the downloaded bundle. Verified statement equals the independently decoded statement and has exactly one subject with the expected name and exact receipt hash.

Full verified result (excluding the redundant raw bundle, which remains in the GitHub artifact):

```json
{
  "mediaType": "application/vnd.dev.sigstore.verificationresult+json;version=0.1",
  "signature": {
    "certificate": {
      "certificateIssuer": "CN=sigstore-intermediate,O=sigstore.dev",
      "subjectAlternativeName": "https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-capture-provenance-pilot.yml@refs/heads/main",
      "issuer": "https://token.actions.githubusercontent.com",
      "githubWorkflowTrigger": "workflow_dispatch",
      "githubWorkflowSHA": "ffe26a8427cf1c783336b67c519c5c177964febe",
      "githubWorkflowName": "DR-002 isolated capture provenance pilot",
      "githubWorkflowRepository": "F1Lllewellyn/f1-data-publisher",
      "githubWorkflowRef": "refs/heads/main",
      "buildSignerURI": "https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-capture-provenance-pilot.yml@refs/heads/main",
      "buildSignerDigest": "ffe26a8427cf1c783336b67c519c5c177964febe",
      "runnerEnvironment": "github-hosted",
      "sourceRepositoryURI": "https://github.com/F1Lllewellyn/f1-data-publisher",
      "sourceRepositoryDigest": "ffe26a8427cf1c783336b67c519c5c177964febe",
      "sourceRepositoryRef": "refs/heads/main",
      "sourceRepositoryIdentifier": "1262398563",
      "sourceRepositoryOwnerURI": "https://github.com/F1Lllewellyn",
      "sourceRepositoryOwnerIdentifier": "291632822",
      "buildConfigURI": "https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-capture-provenance-pilot.yml@refs/heads/main",
      "buildConfigDigest": "ffe26a8427cf1c783336b67c519c5c177964febe",
      "buildTrigger": "workflow_dispatch",
      "runInvocationURI": "https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37229086347/attempts/1",
      "sourceRepositoryVisibilityAtSigning": "public"
    }
  },
  "verifiedTimestamps": [
    {
      "type": "Tlog",
      "uri": "https://rekor.sigstore.dev",
      "timestamp": "2026-10-04T21:42:36+02:00"
    }
  ],
  "verifiedIdentity": {
    "subjectAlternativeName": {
      "subjectAlternativeName": "",
      "regexp": "^https://github\\.com/F1Lllewellyn/f1-data-publisher/\\.github/workflows/dr002-capture-provenance-pilot\\.yml(@(refs/.*|[0-9a-fA-F]+))?$"
    },
    "issuer": {
      "issuer": "",
      "regexp": ".*"
    },
    "runnerEnvironment": "github-hosted"
  },
  "statement": {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [
      {
        "name": "source_capture_receipt.json",
        "digest": {
          "sha256": "3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69"
        }
      }
    ],
    "predicateType": "https://slsa.dev/provenance/v1",
    "predicate": {
      "buildDefinition": {
        "buildType": "https://actions.github.io/buildtypes/workflow/v1",
        "externalParameters": {
          "workflow": {
            "path": ".github/workflows/dr002-capture-provenance-pilot.yml",
            "ref": "refs/heads/main",
            "repository": "https://github.com/F1Lllewellyn/f1-data-publisher"
          }
        },
        "internalParameters": {
          "github": {
            "event_name": "workflow_dispatch",
            "repository_id": "1262398563",
            "repository_owner_id": "291632822",
            "runner_environment": "github-hosted"
          }
        },
        "resolvedDependencies": [
          {
            "digest": {
              "gitCommit": "ffe26a8427cf1c783336b67c519c5c177964febe"
            },
            "uri": "git+https://github.com/F1Lllewellyn/f1-data-publisher@refs/heads/main"
          }
        ]
      },
      "runDetails": {
        "builder": {
          "id": "https://github.com/F1Lllewellyn/f1-data-publisher/.github/workflows/dr002-capture-provenance-pilot.yml@refs/heads/main"
        },
        "metadata": {
          "invocationId": "https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37229086347/attempts/1"
        }
      }
    }
  }
}
```

The CLI's returned verifiedIdentity issuer regex is `.*` despite the supplied issuer option. This record does not claim that returned regex enforces the issuer. The actual cryptographically verified certificate issuer extension was separately asserted exactly equal to `https://token.actions.githubusercontent.com`. Certificate SAN/signer URI, source/signer/build-config commit, main ref, hosted runner and invocation URI were also independently asserted against the expected values.

Additional independent local check: Python cryptography verified the DSSE ECDSA/SHA-256 signature over the exact DSSEv1 pre-authentication encoding using the bundle leaf certificate public key: PASS. This additional check does not itself establish certificate trust. Certificate-chain and transparency authentication are supplied by the successful GitHub CLI default-root verification; no second independent full chain/Rekor implementation was claimed.

Verified transparency time: **2026-10-04T19:42:36Z** (CLI rendered `2026-10-04T21:42:36+02:00`), service `https://rekor.sigstore.dev`. Integrated time `1791142956`; bundle logIndex `3078464279`; inclusionProof logIndex `2956560017`; tree size `2956560018`. Those two API fields are recorded distinctly, not conflated. Bundle contains signed inclusion promise, inclusion proof and signed checkpoint; GitHub CLI accepted verification. Run ID, attempt and head are independently corroborated across GitHub API/logs, package metadata and the verified certificate/statement.

## EXECUTED LIVE SOURCE-CAPTURE FACT

The accepted, unchanged fixed one-request capture path executed in this GitHub-hosted run and produced the inspected capture package. Evidence is joint: exact code Git blobs, successful job/step/log evidence, captured raw and normalized bytes, existing receipt semantics, and independently verified attestation of the exact receipt. Coder did not locally execute a source request or invoke the capture function; local inspection used only pure validation/hash helpers. No live OpenF1 request occurred outside the one authorized workflow execution.

Attestation cryptographically associates exact receipt bytes with the expected GitHub workflow provenance. The receipt semantically/hash-binds raw source bytes, scope and observation fields under the unchanged contract. The attestation does not independently certify every workflow-authored field or authenticate the OpenF1 publisher cryptographically.

## TEMPORAL INTERPRETATION

Internal chronology independently checked:

- Request started: 2026-10-04T19:42:33.927655Z.
- Complete response / first_observed_utc: 2026-10-04T19:42:34.866980Z.
- Ingested: 2026-10-04T19:42:34.867390Z.
- Receipt created: 2026-10-04T19:42:34.868462Z.
- Verified transparency time: 2026-10-04T19:42:36Z.

Ordering is consistent with GitHub capture then attestation then preservation/upload. GitHub step timestamps have whole-second precision; capture completion `19:42:34Z` must not be treated as an exact subsecond boundary contradicting the internal `.866980` response time. Timestamp consistency does not authenticate the precision or truth of the runner's internal first_observed clock value.

The exact receipt bytes existed no later than the verified transparency time. This does not prove earliest-ever observation, complete observation coverage, or source availability at historical weather-row dates. No historical temporal eligibility has been upgraded.

## UNPROVEN / NOT CLAIMED

- OpenF1 publisher cryptographic authenticity.
- Earliest-ever source availability or historical availability before first_observed_utc.
- Global observation completeness.
- Protected Engine_2026-06-07_STABLE execution or blind predictive eligibility.
- Live production forecast lock, outcome-boundary proof or revision completeness.
- Production readiness/enforcement or predictive accuracy improvement.

binding_status remains UNBOUND; production_authenticated=false; historical_availability_proven=false; dr002_activated=false. No verified_receipt_bindings was created. Mapping GitHub provenance into the external-binding interface needs a separate reviewed decision.

## Work boundary and next decision

Exactly one new documentation file; no existing file edited. No workflow dispatch/rerun, workflow repair, capture-script/receipt-contract/model/producer/orchestrator/stable-engine/workbook/ledger mutation, new receipt type, live lock/outcome/revision proof, Pipedream or Gmail. No unrelated test suite rerun. Artifact validation and cryptographic verification above were actually executed against this downloaded package.

No raw artifact, credentials or verifier output file is committed separately. The seven logical evidence files remain retrievable through the exact GitHub artifact. This checkpoint records the verification output and identities; local scratch paths are optional intermediates.

Stop at this one-file Work Result PR. Adviser acceptance, PR merge, DR-002 activation, Gate 2B-7 enforcement and promotion are not implied.
