# DR-002 pre-2B-7 K4R28 — manual OpenF1 source custody attestation capability

**Work order:** F1-WO-DR002-PRE2B7K4R28-001 / Issue #280

**Date:** 2026-10-14

**Result:** `OPENF1_MANUAL_SHADOW_CUSTODY_MANIFEST_PREPARED_UNATTESTED` for deterministic synthetic fixtures only

**Classification:** `CUSTODY_ONLY_NON_OPERATIONAL_SOURCE_EVIDENCE_INVENTORY`

## Outcome

K4R28 adds one separately permissioned follow-on job to the existing OpenF1
source-closure workflow. It is eligible only after the original capture job
succeeds during a manual dispatch on `refs/heads/main` with a nonempty explicit
session key and one of the existing `weather`, `drivers`, or `starting_grid`
endpoints. Scheduled, default/empty-key, non-main, unsupported-endpoint, and
failed original jobs cannot enter the attestation job.

The new pure offline helper accepts only the exact existing flat artifact
layouts: five members for weather, five for drivers, and six for starting grid.
It validates the original raw bytes, parentless canonical source-capture
receipt, sanitized assessment, publisher manifest, execution identity, scope,
and all relevant hashes before producing one deterministic canonical custody
manifest. For grid evidence it also validates the exact session-discovery
bytes, a distinct Qualifying source and Race target in the same event, both
request-attempt flags, and exact integer HTTP 200 statuses. No new receipt is
created and no cross-session producer authority is conferred.

After successful preflight, the job reuses the accepted H2 immutable
`actions/attest` mechanism to attest the exact custody-manifest bytes. The
action-produced DSSE bundle is preserved byte-for-byte with factual metadata in
a separate 30-day custody-only artifact. Local DSSE inspection checks only
structure and subject-digest consistency; every cryptographic-signature,
trusted-Tlog, signer, source, production, and promotion claim remains false.

No workflow was dispatched. No provider was contacted, no real artifact was
downloaded, no live attestation was performed, and no producer, model, forecast,
repository publication, or stable-engine operation occurred.

## Exact authorized delta

Exactly four paths are present in the work result:

1. Modified `.github/workflows/f1-openf1-lightweight-source-closure.yml`
2. Added `scripts/forecast_bundles/dr002_openf1_manual_shadow_custody_attestation_v1.py`
3. Added `tests/test_dr002_openf1_manual_shadow_custody_attestation_v1.py`
4. Added `docs/DR002_PRE2B7K4R28_MANUAL_OPENF1_SOURCE_CUSTODY_ATTESTATION_CAPABILITY_2026-10-14.md`

The original workflow bytes remain an exact prefix of the modified file. Their
SHA-256 is
`b7fb291274f5c1f31cceb54cc43bfca5fef88e0d1fd76a6288f219a3be18d35a`,
and their original Git blob is `d277ceaaffbb148dbde4b0c32bfbbcd8664e4329`.
Thus the existing inputs/defaults, triggers, concurrency, permissions, capture
job, GET behavior, artifact naming/retention, scheduled commits, and path-write
behavior are byte-for-byte unchanged.

## Protected dependency fingerprint preflight

All 14 protected work-order pins matched the merged K4R27 baseline
`6793094d6f8463c8634f52addc5f1e1add34c4e2` before the change and remain
unchanged in this result:

| Protected dependency | Git blob |
|---|---|
| `scripts/openf1/publish_openf1_lightweight_source_closure.py` | `dbbc36dc01737084f2b1ff332e26c6c270be0049` |
| `scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py` | `e68fa528cd73cd5c72afd97622a00d6e5b29be19` |
| `scripts/forecast_bundles/dr002_openf1_three_source_actions_artifact_intake_v1.py` | `b124f4b717041006bdab04572574c0634ed7a5e9` |
| `scripts/forecast_bundles/dr002_openf1_three_source_precutoff_candidate_v1.py` | `ab69310fcb47bb7962d45ea771572d76436eb23b` |
| `scripts/forecast_bundles/dr002_openf1_three_source_event_compatibility_v1.py` | `f0850f4c13132b213f03a2b1aeaea01acebe2bf8` |
| `scripts/forecast_bundles/dr002_openf1_three_source_grid_projection_v1.py` | `63ae055aa54c9d9cbe12772c99301a41496863ab` |
| `scripts/forecast_bundles/dr002_openf1_weather_producer_adapter_v1.py` | `5061d8007d06c37e164df2c6cc643e385be885f8` |
| `scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py` | `357ac56a6cfe317e21d9ce71d78c58683e444a5a` |
| `scripts/forecast_bundles/dr002_openf1_starting_grid_producer_adapter_v1.py` | `702a1219c4b97450d7aeec16b5dd8409f2b73d75` |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | `af27586668c767de126af829c1131c6bae4634ad` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |
| `.github/workflows/dr002-forecast-lock-shadow-pilot.yml` | `4daa7c0ebb22f9b31dd35f5b0109c2eb227a976c` |
| `docs/DR002_PRE2B7H2_LIVE_GITHUB_ATTESTED_LOCK_SHADOW_2026-10-05.md` | `1e6177001a7e939cb18af6d8581748559d5bc859` |

The download action was independently resolved to the official immutable
`actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093`
(`v4.3.0`) tag. The attestation step exactly reuses accepted H2 pin
`actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`
(`v4.2.2`).

## Workflow isolation and permission equivalence

The added job is `openf1-manual-shadow-custody-attestation` and declares only:

```text
contents: read
actions: read
id-token: write
attestations: write
```

It checks out `${{ github.sha }}` with `persist-credentials: false`, downloads
only the selected original artifact from the same current workflow run, and
uploads only the generated custody manifest, DSSE bundle, and metadata. The
disposable downloaded source directory is outside that upload path. The job has
no provider request, `contents: write`, repository commit, or push surface.

The weather/drivers `PRACTICE_2_*` and grid
`QUALIFYING_STARTING_GRID_SOURCE_CAPTURE_FOR_RACE_TARGET` labels state the
authorized downstream evidence roles. They do not authenticate a session
classification, publisher, or observation clock and do not alter the original
receipt scope. The grid source-to-target relationship remains an OpenF1
provider-discovery claim with cross-session producer authorization false.

## Focused synthetic verification

Commands:

```text
python -m py_compile scripts/forecast_bundles/dr002_openf1_manual_shadow_custody_attestation_v1.py tests/test_dr002_openf1_manual_shadow_custody_attestation_v1.py
python -m unittest -v tests.test_dr002_openf1_manual_shadow_custody_attestation_v1
python -c "import yaml; yaml.safe_load(open('.github/workflows/f1-openf1-lightweight-source-closure.yml'))"
git diff --check
```

Result: **36 focused unittest methods passed, covering 42 enumerated checks**;
syntax compilation, YAML parsing, and diff checks passed. The suite covers the
three valid endpoint layouts, deterministic complete member inventory, exact
source/receipt/sidecar/discovery bindings, execution and scope mismatch,
duplicate/noncanonical JSON, missing/extra/unsafe/symlink/oversized evidence,
grid source/target and HTTP constraints, false trust flags, output containment,
DSSE subject-digest consistency without verification claims, and static
workflow isolation, condition, permission, pin, and ordering checks.

Deterministic synthetic custody-manifest evidence:

| Synthetic fixture | SHA-256 | Bytes |
|---|---|---:|
| weather | `48f5c7bd4f490e7dee9ef2d79166c06a7736519ec48d347f16c159d7121c142b` | 2673 |
| drivers | `a68afe92318424865ab064e5f6a0e94cda5bf632f018341c3acac0201e438838` | 2673 |
| starting grid | `8445a459419367b14c71f0dfdaceb6ac7a108dd8587563668dcda3b32590168d` | 3129 |

These hashes describe mock Testland fixtures only. They are not real source
evidence, GitHub custody proof, a signed attestation, or scientific evidence.

## HOLD behavior

Preparation fails closed before attestation on a missing, extra, duplicate,
unsafe, linked, special, empty, oversized, unreadable, or changing member; any
malformed or noncanonical JSON; any receipt, raw-byte, assessment, manifest,
scope, endpoint, URI, source identity, repository, workflow, ref, head, run, or
attempt mismatch; and any invalid grid discovery, relationship, request-attempt,
or HTTP-status evidence. Preservation fails closed on a malformed action bundle,
missing/empty signature field, wrong DSSE statement or subject digest, changed
manifest, execution mismatch, or inconsistent attestation identity/URL.

No work-order HOLD condition was encountered in the synthetic implementation
and verification. A future live job can still HOLD on any of these gates; no
failed/HOLD evidence is attested by this capability.

## Scientific and promotion limits

A later independently verified trusted-Tlog entry can establish only that the
exact custody-manifest bytes existed by the Tlog time. It does not authenticate
OpenF1 as publisher, prove the raw bytes' first-observed clock or earlier
historical availability, establish revision completeness, authenticate an
official FIA final grid, authorize cross-session production use, or prove a
producer, forecast lock, model, or stable-engine execution.

Engineering progress remains **92/100 PROVISIONAL (+0 for synthetic capability)**.
DR-002 remains **PROPOSED — NOT ACTIVATED**; forecast gate OFF; promotion NOT
ALLOWED; `Engine_2026-06-07_STABLE` protected. No K4R29 work was performed.
