# DR-002 pre-2B-7K4R23 offline unscoped grid mechanics projection

**Work order:** Issue #265 / `F1-WO-DR002-PRE2B7K4R23-001`

**Result:** pure offline mock-only implementation and focused validation PASS

**Classification:** `POST_EVENT_SANDBOX_PROJECTION_ONLY_NOT_A_PREDICTION`

**DR-002:** PROPOSED — NOT ACTIVATED

**Forecast gate:** OFF

**Promotion:** NOT ALLOWED

## Scope-safe projection contract

The new in-memory entry point first requires the unchanged K4R21 three-source
compatibility assessor to return its full accepted post-event-mechanics-only
status. It then independently reruns the unchanged K4R4 weather, K4R6 drivers,
and K4R16 starting-grid adapters against the same explicit raw and receipt
bytes. Adapter scope, source receipt, raw hash, row count, derived hash, trust
state, and claim ceilings must match the K4R21 result or the complete operation
returns a minimal `HOLD`.

On a validated synthetic input only:

- weather and drivers CSV bytes remain byte-for-byte the adapter outputs and
  retain their original Practice 2 `session_key` scope;
- the original K4R16 five-column starting-grid CSV remains Qualifying-scoped
  lineage and is not supplied as a Practice 2 producer input;
- a separate deterministic UTF-8/LF `driver_number,position` view is built in
  numeric position order, without event, meeting, or session columns;
- the projected view has a distinct
  `derived:postevent-unscoped-qualifying-grid-projection:<sha256>` identity;
- a deterministic `dr002-frozen-producer-input-v1` sandbox-candidate manifest
  names exactly `weather.csv`, `drivers.csv`, and `starting_grid.csv`, binds
  only their derived runtime identities and exact byte hashes, and truthfully
  declares the Practice 2 mechanics session `11371`; and
- original weather/drivers Practice 2 `11371`, Qualifying grid `11373`, and
  target Race `11377` identities and chronology remain separate in bounded
  lineage metadata.

The projection drops scope columns only from the additional grid runtime view.
It does not change the original Qualifying derived CSV, relabel a Qualifying
source as Practice 2 or Race, create a receipt, authenticate an FIA grid,
authorize a cross-session producer join, or establish pre-race availability.

## Fail-closed behavior

Every K4R21 HOLD or downstream invariant failure returns only schema, `HOLD`, a
bounded reason code, and false trust/operational flags. It returns no input CSV
bytes, projected bytes, manifest, receipt identity, raw identity, hash lineage,
or partial materialization.

Focused mock coverage includes ambiguous Practice 2, case-insensitive Sprint,
non-unique Qualifying/Race, invalid JSON, wrong receipt/raw/source scope,
post-Race temporal failure, roster mismatch, empty/holey grid, request-attempt
and exact-integer-200 diagnostics, manifest hash mismatch, adapter result
substitution, runtime identity collision checks, deterministic bytes, exact
manifest bindings, and the absence of filesystem/network/clock/subprocess/
producer/model surfaces.

## Synthetic deterministic example

These digests are from the small synthetic test fixture only. They are not the
accepted Baku artifact digests and do not represent a real-source replay.

| Synthetic runtime object | SHA-256 |
| --- | --- |
| unchanged weather adapter CSV | `af7ab8f869a78d2dec9480dcebf81ddc4b04ab62220fb2da688ac73a7e88f862` |
| unchanged drivers adapter CSV | `97abcb585c58d92e4967e2b389c59c7f439c0f4c6b02148b15067642bcfb2823` |
| projected two-column grid CSV | `705f0a1a5b79c9d9dc8eae01cd7340d34e73ee334c5eff51874f836049c05c87` |
| original five-column Qualifying grid CSV | `72f398c9f0cfe4bf8a3d0f98788358c22f96c5aaa4b487e4de8e82dd9db3c0f6` |
| candidate producer manifest | `e3fb481662a3b59ae793342b87273795f2f545adb4cb567332022466a68c6f5f` |

## Focused offline verification

All authorized suites passed on 2026-10-14:

| Suite | Result |
| --- | ---: |
| K4R23 grid projection mock suite | 30 passed |
| K4R21 three-source compatibility suite | 41 passed |
| K4R4 weather adapter suite | 25 passed |
| K4R6 drivers adapter suite | 26 passed |
| K4R16 starting-grid adapter suite | 30 passed |
| **Total** | **152 passed, 0 failed** |

The new module and test file also passed Python syntax compilation, and the
three-path delta passed whitespace and scope checks.

## Dependency and execution audit

Implementation began from observed main `857d5bdf2`, after verifying the exact
K4R21 assessor, three adapters, K4R9 composer, frozen-evidence contract,
protected producer, K4R19 publisher, handoff contract, and accepted K4R22
report blobs pinned by Issue #265. Scheduled `latest/**` / `history/**` movement
did not alter those dependencies.

Original artifact downloads: **0**. Live OpenF1/FIA/provider requests: **0**.
Workflow dispatches: **0**. Original Baku compatibility replays: **0**.
Producer/model/stable-engine executions: **0**. Filesystem output from the new
entry point: **0**. Public raw source rows: **0**. Existing protected files
modified: **0**.

This mock-only result proves only that the proposed in-memory projection is
fail-closed and structurally preserves truthful source scope. A real-artifact
projection, producer acceptance, forecast, accuracy measurement, activation,
and promotion all require later separate authorization.
