# DR-002 pre-2B-7 K4R26 — offline three-source pre-cutoff candidate

**Work order:** F1-WO-DR002-PRE2B7K4R26-001 / Issue #274

**Date:** 2026-10-14

**Result:** `PROSPECTIVE_ASOF_SOURCE_CANDIDATE_STRUCTURALLY_CONSISTENT_UNAUTHENTICATED` for the deterministic synthetic example only

**Classification:** `NON_OPERATIONAL_SANDBOX_PRE_CUTOFF_CANDIDATE_ONLY`

## Outcome

K4R26 adds a pure in-memory candidate seam for assessing whether three original
OpenF1 source captures are structurally compatible and internally no later than
an explicit caller-supplied cutoff. The seam reuses the accepted canonical
source-capture receipts, weather/drivers/starting-grid adapters, K4R21 session
validation, K4R21 grid-shadow diagnostics, and K4R23 two-column grid projection
helper without invoking either K4R21's post-event assessor or K4R23's full
post-event projector.

The implementation requires one unique non-Sprint Practice 2 → Qualifying →
Race sequence for the same meeting/event identity. The cutoff must be strictly
after Qualifying end and strictly before Race start. Each original receipt must
remain canonical and source-bound, with:

`first_observed_utc <= ingested_utc <= receipt_created_utc <= forecast_cutoff_utc`

The original weather and drivers evidence remains Practice 2 scoped. The
original five-column starting-grid evidence remains Qualifying scoped and
retains the separately declared Race target. Only a separate deterministic
`driver_number,position` view is placed in the non-operational candidate.

## Exact authorized delta

Three files were added; no existing file was modified:

1. `scripts/forecast_bundles/dr002_openf1_three_source_precutoff_candidate_v1.py`
2. `tests/test_dr002_openf1_three_source_precutoff_candidate_v1.py`
3. `docs/DR002_PRE2B7K4R26_OFFLINE_THREE_SOURCE_PRE_CUTOFF_CANDIDATE_2026-10-14.md`

No source capture, provider request, workflow dispatch, producer/model execution,
forecast creation, lock receipt, implementation attestation, or stable-engine
operation occurred.

## Dependency fingerprint preflight

All 13 work-order pins matched the observed `main` baseline before mutation:

| Protected dependency | Git blob |
|---|---|
| `scripts/forecast_bundles/dr002_openf1_three_source_event_compatibility_v1.py` | `f0850f4c13132b213f03a2b1aeaea01acebe2bf8` |
| `scripts/forecast_bundles/dr002_openf1_three_source_grid_projection_v1.py` | `63ae055aa54c9d9cbe12772c99301a41496863ab` |
| `scripts/forecast_bundles/dr002_openf1_weather_producer_adapter_v1.py` | `5061d8007d06c37e164df2c6cc643e385be885f8` |
| `scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py` | `357ac56a6cfe317e21d9ce71d78c58683e444a5a` |
| `scripts/forecast_bundles/dr002_openf1_starting_grid_producer_adapter_v1.py` | `702a1219c4b97450d7aeec16b5dd8409f2b73d75` |
| `scripts/forecast_bundles/dr002_replay_leakage_evidence_v1.py` | `b53b9f8473d912c924ad637724bbfef740704eb4` |
| `scripts/forecast_bundles/forecast_integrity_contract_v1.py` | `9f5a3585814f4e5eb7a1f95ecdada90a33090857` |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| `scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py` | `064d93ee5ae30354590a3fb95be598c5fe8b3b9a` |
| `scripts/forecast_bundles/dr002_fia_grid_document_candidate_v1.py` | `15867e3d1af56a5c00b2bd35c1220541e7e4f619` |
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | `af27586668c767de126af829c1131c6bae4634ad` |
| `docs/DR002_PRE2B7K4R25_ONE_BAKU_POSTEVENT_THREE_SOURCE_FROZEN_PRODUCER_MECHANICS_2026-10-14.md` | `bbfb491238289f9de984a692327477a25c85c48d` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

Observed baseline was `3e331c2f0a45befc31f55692f57fe18cd73aab72`,
which contains accepted K4R25 merge commit
`4ff03c5c056e31c6166ff4c458bc0198fb627781`.

## Focused synthetic verification

Command:

```text
python -m unittest tests.test_dr002_openf1_three_source_precutoff_candidate_v1
```

Result: **39 tests passed**. The suite covers at least 25 behaviorally distinct
cases, including the full three-source × three-timestamp cutoff matrix. It also
covers strict cutoff boundaries, ambiguous sessions, case-insensitive Sprint
classification, cross-event identities, canonical receipt/source URI/raw hash
failures, request-attempt and HTTP-200 diagnostics, equal-size 22-driver roster
mismatch, invalid grid slots, runtime-identity collision, deterministic output,
and the unchanged K4R21 post-event rule.

Syntax compilation of the new implementation and test module passed. Exact
delta inspection confirmed three added paths and no tracked modification.

### Deterministic synthetic example evidence

These hashes belong only to the in-memory synthetic Testland fixture. They are
not a real event capture or availability attestation.

| Synthetic object | SHA-256 |
|---|---|
| candidate manifest | `c5396a1dcf480ed8e4b43dbc25b672026704c4a39edb14872c52cff1b4fd8e45` |
| `drivers.csv` | `f8120a85751c86c30177f57e98557a4e88954b30de5235f0f70c77d16c9c9999` |
| projected `starting_grid.csv` | `705f0a1a5b79c9d9dc8eae01cd7340d34e73ee334c5eff51874f836049c05c87` |
| `weather.csv` | `92e45fd59edcb5fad3324ac521aeef4b9c3fe6835975c3b9ba3ed6b9b4a179ae` |
| original five-column Qualifying grid CSV | `8017fc08d457556b8aa292419bd1208727ff2b5c2ad975064443e23aa9373f5a` |

## HOLD behavior

Any malformed or ambiguous input returns `HOLD` with a bounded reason and all
claim flags false. A HOLD returns no manifest, runtime CSV, source/receipt ID,
or hash lineage. Representative HOLD conditions include:

- cutoff not strictly between Qualifying end and Race start;
- any source observed, ingested, or receipt-created after cutoff;
- missing/non-UTC/ambiguous timestamps or noncanonical receipt bytes;
- nonunique Practice 2, Qualifying, or Race, any same-meeting Sprint, or
  cross-meeting/year/circuit identity;
- source scope/URI/raw hash mismatch or adapter HOLD;
- missing request-attempt evidence or either HTTP status not exactly integer
  200 in the supplied grid-shadow manifest;
- roster mismatch, duplicate/holey/nonpositive grid positions, or source/runtime
  identity collision.

## Scientific and promotion limits

The result proves no external fact. Canonical receipts can contain fabricated
observation timestamps; no independent capture attestation is supplied here.
The candidate is not `VALID_LOCKED`, externally `AS_OF_CONTRACT_CLEAN`, an
official FIA final grid, authenticated publisher evidence, historical
availability proof, a production authorization, or a complete Gate 2B evidence
chain. It creates no forecast and provides no blind-validation or predictive
accuracy evidence.

Every success and HOLD path explicitly keeps external attestation,
authentication, historical availability, production authentication, verified
receipt bindings, producer execution, forecast generation/lock, blind
eligibility, DR-002 activation, promotion, and stable-engine proof false.

Engineering progress remains **92/100 PROVISIONAL (+0 for mock-only
capability)**. DR-002 remains **PROPOSED — NOT ACTIVATED**; forecast gate OFF;
promotion NOT ALLOWED; `Engine_2026-06-07_STABLE` protected.
