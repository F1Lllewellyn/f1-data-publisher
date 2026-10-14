# DR-002 pre-2B-7 K4R27 — offline three-source Actions artifact intake

**Work order:** F1-WO-DR002-PRE2B7K4R27-001 / Issue #277

**Date:** 2026-10-14

**Result:** `OPENF1_THREE_SOURCE_ACTIONS_ARTIFACT_INTAKE_CANDIDATE_UNAUTHENTICATED` for the deterministic synthetic example only

**Classification:** `READ_ONLY_PRIVATE_ARTIFACT_INTAKE_NON_OPERATIONAL_CANDIDATE_ONLY`

## Outcome

K4R27 adds one pure, keyword-only, in-memory seam for three independently
supplied GitHub Actions artifact ZIP byte strings: Practice 2 weather, Practice
2 drivers, and Qualifying starting grid. Each archive must match an independent
caller-supplied whole-archive SHA-256 and the exact accepted publisher member
layout before any candidate derivation begins.

The intake rejects malformed, ambiguous, oversized, unsafe, encrypted, corrupt,
or wrongly scoped archive content. It checks the supplied capture assessment,
receipt, manifest, raw-response, and grid discovery bindings without rewriting
the evidence bytes. Only after all three archives pass preflight does it invoke
the unchanged K4R26 prospective candidate once. K4R26 remains the sole owner of
the accepted source, session, roster, projection, and pre-cutoff scientific
checks.

Optional caller-supplied GitHub run and artifact IDs remain
`UNVERIFIED_CALLER_ASSERTION` metadata. Neither those IDs nor an ordinary ZIP
digest authenticates GitHub custody, the source publisher, or an observation
clock.

## Exact authorized delta

Exactly three files were added; no existing file was modified:

1. `scripts/forecast_bundles/dr002_openf1_three_source_actions_artifact_intake_v1.py`
2. `tests/test_dr002_openf1_three_source_actions_artifact_intake_v1.py`
3. `docs/DR002_PRE2B7K4R27_OFFLINE_THREE_SOURCE_ACTIONS_ARTIFACT_INTAKE_2026-10-14.md`

No artifact was downloaded. No provider, GitHub Actions API, workflow dispatch,
filesystem extraction, producer/model execution, forecast creation, receipt
creation, repository output, or stable-engine operation occurred.

## Dependency fingerprint preflight

All 13 protected work-order pins matched the merged K4R26 baseline
`a4650b3a39c41552733246ea9b131edfb5a57c1c` before mutation:

| Protected dependency | Git blob |
|---|---|
| `scripts/forecast_bundles/dr002_openf1_three_source_precutoff_candidate_v1.py` | `ab69310fcb47bb7962d45ea771572d76436eb23b` |
| `scripts/forecast_bundles/dr002_openf1_three_source_event_compatibility_v1.py` | `f0850f4c13132b213f03a2b1aeaea01acebe2bf8` |
| `scripts/forecast_bundles/dr002_openf1_three_source_grid_projection_v1.py` | `63ae055aa54c9d9cbe12772c99301a41496863ab` |
| `scripts/forecast_bundles/dr002_openf1_weather_producer_adapter_v1.py` | `5061d8007d06c37e164df2c6cc643e385be885f8` |
| `scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py` | `357ac56a6cfe317e21d9ce71d78c58683e444a5a` |
| `scripts/forecast_bundles/dr002_openf1_starting_grid_producer_adapter_v1.py` | `702a1219c4b97450d7aeec16b5dd8409f2b73d75` |
| `scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py` | `e68fa528cd73cd5c72afd97622a00d6e5b29be19` |
| `scripts/openf1/publish_openf1_lightweight_source_closure.py` | `dbbc36dc01737084f2b1ff332e26c6c270be0049` |
| `.github/workflows/f1-openf1-lightweight-source-closure.yml` | `d277ceaaffbb148dbde4b0c32bfbbcd8664e4329` |
| `configs/openf1/openf1_lightweight_source_closure_policy.json` | `6ebb40e5fd42623a769eba8ee4feab09765c4b00` |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | `af27586668c767de126af829c1131c6bae4634ad` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

## Archive and delegation contract

The weather and drivers archives each require exactly five flat regular files;
the grid archive requires exactly six, including its exact session discovery
response. The preflight is bounded to 16 MiB per archive, 8 MiB per member, 24
MiB total uncompressed content, and a 200:1 maximum compression ratio. Only
stored and deflated members are accepted. Names containing absolute, nested,
parent, backslash, colon, or percent-encoded spellings are rejected, as are
directories, duplicates, symlinks, special files, encryption, unsupported
compression, bad CRC/readback, empty members, and unexpected member sets.

Exact receipt and raw-response bytes, plus the exact grid discovery and shadow
manifest bytes, are delegated to K4R26. The delegate is called exactly once
after successful preflight and zero times for malformed archives. The intake
does not call K4R21/K4R23 full post-event assessors or any producer.

## Focused synthetic verification

Commands:

```text
python -m py_compile scripts/forecast_bundles/dr002_openf1_three_source_actions_artifact_intake_v1.py tests/test_dr002_openf1_three_source_actions_artifact_intake_v1.py
python -m unittest -v tests.test_dr002_openf1_three_source_actions_artifact_intake_v1
git diff --check
```

Result: **39 focused tests passed**. The mock-only suite covers valid exact-byte
delegation and candidate-manifest hashing, all negative claim flags, independent
whole-archive hashes, malformed/tampered raw and sidecar evidence, wrong and
duplicate members, hidden extras, directories, path attacks, symlinks, special
files, encryption, unsupported compression, CRC corruption, truncation, size
and compression-ratio limits, prefixed/trailing ambiguous containers, swapped
source roles, scope/circuit/roster
mismatch, the three source roles after cutoff, minimal HOLD disclosure,
determinism, one/zero K4R26 call counts, the unchanged K4R21 post-event rule,
and absence of filesystem/network/clock/workflow/producer surfaces.

### Deterministic synthetic example evidence

These hashes belong only to deterministic, in-memory Testland fixtures. They
are not downloaded artifacts, real event evidence, GitHub custody proof, or a
source-availability attestation.

| Synthetic object | SHA-256 |
|---|---|
| weather archive | `539e5a8e3fb04d1aecbeb04b956391a75d582c09b7002239a1ce5524de207fd3` |
| drivers archive | `a7b37078c4b7657077d60dddd852d74e3831204df14ece01e113b0dcd246521a` |
| starting-grid archive | `5b212fedddb7578d5d87b95b32addf598e0703d32243101e5c4096afb5170c90` |
| candidate manifest | `c5396a1dcf480ed8e4b43dbc25b672026704c4a39edb14872c52cff1b4fd8e45` |
| `drivers.csv` | `f8120a85751c86c30177f57e98557a4e88954b30de5235f0f70c77d16c9c9999` |
| projected `starting_grid.csv` | `705f0a1a5b79c9d9dc8eae01cd7340d34e73ee334c5eff51874f836049c05c87` |
| `weather.csv` | `92e45fd59edcb5fad3324ac521aeef4b9c3fe6835975c3b9ba3ed6b9b4a179ae` |

## HOLD behavior

Any archive, sidecar, or delegated scientific failure returns `HOLD` with no
raw bytes, receipt/source IDs, archive or source digests, candidate manifest,
driver data, or partial candidate. The result contains only the schema, HOLD
status, at most eight bounded reason codes, and explicit false claim flags.
Malformed archive preflight never invokes K4R26. A K4R26 HOLD is preserved as a
bounded outer reason without exposing its partial inputs.

## Scientific and promotion limits

Success proves only deterministic consistency of caller-supplied private bytes
against caller-supplied archive hashes and the unchanged K4R26 contract. It
does not prove that GitHub produced or retained an archive, that OpenF1 served
its content, that receipt timestamps were externally observed, that the grid is
an official FIA final grid, or that any evidence was available before a real
forecast cutoff.

All external-attestation, GitHub identity, provider authentication, historical
availability, FIA authentication, production authentication, verified receipt
binding, producer execution, forecast generation/lock, blind eligibility,
DR-002 activation, promotion, and stable-engine proof flags remain false.

Engineering progress remains **92/100 PROVISIONAL (+0 for synthetic
capability)**. DR-002 remains **PROPOSED — NOT ACTIVATED**; forecast gate OFF;
promotion NOT ALLOWED; `Engine_2026-06-07_STABLE` protected. No K4R28 work was
performed.
