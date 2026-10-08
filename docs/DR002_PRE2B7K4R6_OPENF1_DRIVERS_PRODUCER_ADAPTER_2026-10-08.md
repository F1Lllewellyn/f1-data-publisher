# DR-002 pre-2B-7K4R6 — deterministic OpenF1 drivers producer adapter

**Date:** 2026-10-08

**Work order:** `F1-WO-DR002-PRE2B7K4R6-001` / Issue #222

**Observed main:** `afa4e0c2adbc2f9bdf80620114cda12a6a80952f`

**Status:** bounded implementation; Adviser acceptance pending

## Delivered boundary

`dr002_openf1_drivers_producer_adapter_v1.py` is a pure, offline, in-memory
adapter. It accepts an exact parentless OpenF1 `source_capture` receipt, the
exact raw `drivers` response bytes, and explicit event/meeting/session scope.
It validates the receipt and raw bytes, builds and validates the existing
frozen-evidence manifest through an explicit in-memory reader, then derives
deterministic producer-compatible `drivers.csv` bytes.

The raw receipt and raw JSON remain the evidence. The CSV is only a derived
runtime representation. The adapter performs no filesystem write, network or
OpenF1 request, GitHub API call, clock read, environment-secret access,
subprocess call, producer execution, or production write.

## Input and containment contract

The adapter requires:

- canonical exact receipt bytes with strict duplicate-key/nonfinite rejection;
- the unchanged Gate 2B-1 envelope and temporal semantics;
- a parentless `source_capture` whose scope exactly equals the explicit scope;
- an exact raw-content SHA-256 match;
- canonical URI
  `https://api.openf1.org/v1/drivers?session_key=<session_id>`;
- the K4R1 deterministic `openf1:drivers:<uri-sha256>` source identity; and
- frozen-manifest trust fixed at `UNBOUND`, with
  `production_authenticated=false` and
  `historical_availability_proven=false`.

The raw response must be a nonempty list of objects. Every row requires
`meeting_key`, `session_key`, `driver_number`, `broadcast_name`, `full_name`,
and `team_name`. The only optional fields are `first_name`, `last_name`,
`name_acronym`, `team_colour`, `headshot_url`, and the optional/deprecated
`country_code`. Unknown fields, foreign scope, duplicate driver numbers,
non-positive or non-integer driver numbers (including bool), malformed optional
metadata, and empty or untrimmed required name/team strings cause a complete
HOLD.

HOLD includes neither derived CSV bytes nor a partial frozen manifest.

## Deterministic output

The exact header is:

```text
driver_number,broadcast_name,full_name,team_name,meeting_key,session_key
```

Source row order and accepted strings are preserved. Encoding is UTF-8 with LF
line endings. The result exposes the exact CSV bytes and SHA-256 plus the
identity `derived:openf1-drivers-csv:<csv-sha256>`. It adds no retrieval time or
provenance column to the producer data. The compatibility filename is
`drivers.csv`; no file is written.

## Dependency verification

Relevant-path/blob comparison on the observed main matched every authorized
pin before mutation:

| Dependency | Git blob SHA |
|---|---|
| K4R4 weather adapter | `5061d8007d06c37e164df2c6cc643e385be885f8` |
| K4R5 composition | `090c61af27ef932aae51a8fb83fe828c20c13a68` |
| K4R1 capture contract | `e68fa528cd73cd5c72afd97622a00d6e5b29be19` |
| Frozen evidence manifest | `8dfd855184b172ce88235ee7de3ea33a68031b2e` |
| Gate 2B-1 receipt verifier | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| Current producer | `af27586668c767de126af829c1131c6bae4634ad` |
| Handoff contract | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

The three authorized target paths were absent. No existing file changed.

## Focused verification

The focused test module covers the 25 work-order categories: valid derivation;
raw-evidence binding; exact header, ordering, determinism and hashes; strict
receipt, URI, identity, scope and JSON rejection; required/allowed driver
schema; optional `country_code`; driver-number and name constraints; absence of
invented timestamps; unchanged trust and claim ceilings; pure/offline adapter
imports and calls; actual unchanged-producer consumption of driver number/name/
team columns; and exact dependency blob pins.

Only the focused K4R6 tests and cheap syntax/import checks are authorized for
this work result.

Executed verification:

- `python -m unittest -v tests/test_dr002_openf1_drivers_producer_adapter_v1.py`
  — **26 tests passed**;
- `python -m py_compile` for the adapter and focused test — **passed**;
- direct adapter import with the bundle path — **passed**; and
- `git diff --check` — **passed**.

## Claim ceiling

This delta proves only deterministic source transformation and containment for
explicitly supplied inputs. It does not prove a live drivers capture, official
FIA/F1 roster authority, producer execution, trustworthy starting-grid
evidence, stable-engine execution, blind eligibility, production rollout or
enforcement, DR-002 activation, promotion, or an accuracy improvement.

OpenF1 remains unofficial. Official FIA/F1/team facts override conflicting
driver or roster facts. DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast
gate remains **OFF**. Promotion remains **NOT ALLOWED**.
