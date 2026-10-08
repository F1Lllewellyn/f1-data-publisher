# DR-002 pre-2B-7K4R9 — evidenced weather/drivers frozen-producer composition

**Date:** 2026-10-08

**Work order:** `F1-WO-DR002-PRE2B7K4R9-001` / Issue #231

**Observed main:** `1d5bcb5112dfa1131a386bf5325081e46768a7d0`

**Status:** dual-source mechanics capability only — **NOT A PREDICTION**;
Adviser acceptance pending

## Delivered boundary

K4R9 adds one bounded offline wrapper that composes the unchanged accepted K4R4
weather adapter and unchanged accepted K4R6 drivers adapter into the unchanged
real current producer's frozen-input CLI.

The public function accepts only exact in-memory parentless weather/drivers
`source_capture` receipt bytes, their respective exact raw OpenF1 response
bytes, one explicit common event/meeting/session scope, and a 40-character
lowercase implementation Git SHA used only as informational execution context.
Both adapters must return their accepted `VALIDATED` status before the wrapper
builds or materializes producer inputs. Any adapter HOLD returns complete K4R9
HOLD before a producer subprocess, with no derived input bytes, manifest, or
partial producer evidence in the result.

The exact raw responses and their separate parentless receipts remain the
scientific evidence. Weather and drivers CSVs are deterministic derived runtime
representations only. Their independent raw source IDs, raw SHA-256 values,
receipt IDs, and per-source frozen RAW manifests and hashes remain separate.
Both RAW manifests remain `UNBOUND`, with
`production_authenticated=false` and
`historical_availability_proven=false`. No scientific, normalization, or
producer-execution receipt and no verified binding is created.

## Synthetic-grid mechanics boundary

After both adapters validate, K4R9 derives an explicitly synthetic
`starting_grid.csv` from the exact K4R6 driver universe. Driver numbers are
sorted numerically and assigned deterministic positions `1..N`. The strict
header is:

```text
driver_number,position,event_id,meeting_id,session_id
```

The grid has exact one-to-one driver membership, UTF-8 LF bytes, and identity:

`synthetic:starting-grid-csv:<exact-csv-sha256>`

These positions are not observed grid positions and do not claim FIA/F1
authority. The producer's unchanged `0.48` post-event readiness value is a
mechanics score from the presence of drivers (`0.18`), synthetic grid (`0.20`),
and weather (`0.10`). It is not authentic readiness, confidence, prediction,
or accuracy evidence.

## Frozen producer execution and verification

K4R9 reuses K4R5's accepted bounded-write, tree-fingerprint, expected-count,
evidence-readback, mirror-readback, and exact-sandbox-file-set helpers. It does
not modify K4R5 or reuse K4R5's two-synthetic-driver verifier. Its new minimal
differential verifier handles dynamic `N` and requires every generated row to
match the K4R6 driver number, broadcast name, team, and deterministic synthetic
grid position.

The exact fixed source set and order are:

1. `drivers` — `derived:openf1-drivers-csv:<sha256>`;
2. `starting_grid` — `synthetic:starting-grid-csv:<sha256>`; and
3. `weather` — `derived:openf1-weather-csv:<sha256>`.

Their source IDs are distinct from each other and from both original raw
OpenF1 source IDs. The canonical `dr002-frozen-producer-input-v1` manifest binds
their exact scope, relative paths, identities, SHA-256 values, and row counts.

The wrapper verifies the unchanged producer Git blob
`af27586668c767de126af829c1131c6bae4634ad` before and after execution, then
invokes it exactly once in one disposable temporary repository root with:

- `--frozen-input-manifest` and `--strict-source`;
- explicit event, meeting, and session identifiers;
- gate `post_event`;
- lane `experimental_challenger`;
- a race name ending `NOT A PREDICTION`;
- the sandbox as `--repo-root`; and
- the minimal environment `PYTHONDONTWRITEBYTECODE=1`.

There is no retry. The verifier requires frozen mode, broad discovery disabled,
the exact three sources/hashes/counts/scope, dynamic `N` driver rows, exact
driver identity and synthetic positions, `0.48` mechanics-only readiness,
false trust claims, byte-identical sandbox latest/history outputs and
compatibility mirrors, selected evidence hashes, exact sandbox allowlist, and
disposal. The checked-out `latest/**` and `history/**` metadata fingerprints
must remain unchanged. Any subprocess, readback, input, manifest, audit,
snapshot, row, mirror, containment, disposal, or producer-fingerprint failure
returns HOLD and exposes no partial producer evidence.

## Dependency verification

Relevant path/blob comparison against observed main matched every Issue #231
pin before mutation:

| Dependency | Git blob SHA |
|---|---|
| K4R4 weather adapter | `5061d8007d06c37e164df2c6cc643e385be885f8` |
| K4R6 drivers adapter | `357ac56a6cfe317e21d9ce71d78c58683e444a5a` |
| K4R5 composition | `090c61af27ef932aae51a8fb83fe828c20c13a68` |
| K4R5 focused tests | `4079b6ba65b582b67112fa291afad46d3b44b7bd` |
| Frozen evidence contract | `8dfd855184b172ce88235ee7de3ea33a68031b2e` |
| Current real producer | `af27586668c767de126af829c1131c6bae4634ad` |
| K4R3 weather checkpoint | `db92fb23ff0adf95e59a80f14dcd527b6d1f9906` |
| K4R8 drivers checkpoint | `943440c604163913a95690322bdcdfc850e03b58` |
| Handoff contract | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

The three authorized target paths were absent. No existing file or workflow was
changed.

## Focused offline verification

Tests construct clearly non-live mock historical OpenF1-looking bytes and
K4R1-style parentless receipts through the unchanged accepted capture contract.
They do not retrieve or reuse the K4R3/K4R8 live artifacts.

The new K4R9 module's 20 focused tests cover:

- distinct valid weather/drivers receipts at common scope and one real producer
  subprocess in a disposable sandbox;
- mandatory calls to both unchanged adapters and independent RAW bindings;
- adapter HOLD, wrong raw bytes, swapped receipts, and cross-scope HOLD before
  producer invocation;
- deterministic dynamic-N synthetic grid membership and positions independent
  of source row order;
- exact raw/derived/synthetic identity and SHA-256 separation;
- canonical exact three-source manifest;
- frozen-mode audit, metadata, snapshot, output, scope, name/team/grid, and
  `0.48` readiness verification;
- one attempt, bounded command, minimal environment, no network/API/secret/
  workflow-dispatch/source-discovery path;
- audit, snapshot, manifest, driver-row, input-readback, and producer-failure
  sabotage rejection without retry;
- exact sandbox file set, mirrors, hashes, checkout-output preservation, and
  disposal;
- complete false trust/promotion/forecast ceiling; and
- all nine named dependency pins.

Executed verification:

- `python -m unittest tests.test_dr002_openf1_weather_drivers_frozen_producer_composition_v1`
  — **20 tests passed**;
- focused K4R4/K4R5/K4R6/K4R9 compatibility command — **96 tests passed**;
- Python syntax compilation of both new Python files — **passed**; and
- `git diff --check` — **passed**.

No broad regression, live OpenF1 request, artifact download, GitHub Actions
dispatch, stable/model/production workflow, or checkout production-output
write is part of K4R9.

## Claim ceiling

Successful execution returns:

`DUAL_SOURCE_FROZEN_PRODUCER_MECHANICS_ONLY_NOT_A_PREDICTION`

K4R9 proves only a source-provenance-preserving dual-input sandbox execution
capability for current producer mechanics, using receipt-validated
real-structure weather/drivers test fixtures and a synthetic grid. It does not
assert that the exact K4R3 and K4R8 captured artifacts were executed together,
that either source existed at a pre-race cutoff, that the grid is official or
observed, or that this is a real/blind forecast.

It does not prove official FIA/F1 roster or final-grid authority, authenticated
provider truth, stable-engine execution, predictive performance, production
enforcement, accuracy, accuracy improvement, DR-002 activation, or promotion.
OpenF1 remains unofficial and does not outrank official FIA/F1/team/Pirelli
evidence.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion
**NOT ALLOWED**.
