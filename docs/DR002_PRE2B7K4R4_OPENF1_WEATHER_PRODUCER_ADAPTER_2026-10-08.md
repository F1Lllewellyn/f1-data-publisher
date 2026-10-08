# DR-002 pre-2B-7K4R4 — deterministic OpenF1 weather producer adapter

Date: 2026-10-08

Work order: `F1-WO-DR002-PRE2B7K4R4-001` / Issue #216

Status: transformation/containment capability only

## Result

K4R4 adds one pure, offline, in-memory adapter from an exact parentless OpenF1 `source_capture` receipt plus its exact raw historical weather JSON bytes to deterministic producer-compatible `weather.csv` bytes.

The raw response remains the scientific source evidence. The CSV is a separate derived runtime representation. The adapter creates no source-capture, normalization, or other scientific receipt and creates no verified binding.

## Validation boundary

Before deriving CSV, the adapter:

1. strict-parses the exact receipt bytes with duplicate-key and nonfinite rejection;
2. requires those bytes to equal the Gate 2B-1 canonical JSON encoding;
3. validates the unchanged receipt envelope and temporal semantics;
4. requires a parentless `source_capture` whose recomputed receipt identity and exact event/meeting/session scope match;
5. binds the exact raw bytes to the receipt `source_sha256`;
6. requires the canonical hosted REST URI `https://api.openf1.org/v1/weather?session_key=<session_id>` and its deterministic K4R1 `source_id`; and
7. builds and validates the existing frozen-evidence manifest through an explicit in-memory reader over the raw receipt/content only.

Frozen-evidence trust remains exactly `UNBOUND`, with `production_authenticated=false` and `historical_availability_proven=false`. Any validation failure returns `HOLD` without derived CSV bytes or a partial frozen manifest.

## Exact weather contract

The raw response must be a nonempty top-level JSON list. Every row must contain exactly, in contract terms, the following fields:

`date,session_key,meeting_key,air_temperature,track_temperature,humidity,pressure,rainfall,wind_direction,wind_speed`

Every session and meeting key must match the explicit request scope. Dates must be timezone-aware UTC values in the unchanged receipt contract's `Z` form. Weather values must be finite integer or floating-point scalars; booleans are rejected. Duplicate JSON keys, nonfinite constants, malformed rows, missing/extra fields, foreign scope, unsupported values, an object top level, and an empty list all fail closed.

## Deterministic CSV representation

The successful status is `OPENF1_WEATHER_PRODUCER_ADAPTER_VALIDATED`.

The adapter preserves source row order, uses the fixed field order above, emits deterministic UTF-8 bytes with LF line endings, and computes the producer-input SHA-256 over those exact bytes. Its compatibility target is `weather.csv`, already recognized by the unchanged producer. It performs no filesystem write.

The CSV contains no invented retrieval/observation timestamp and no provenance column. The result records the validated scope, source receipt ID, raw source hash, frozen manifest and hash, row count, exact CSV bytes and hash, and an explicit raw-to-derived lineage statement.

## Architecture boundary

Gate 2B-1 `normalization` receipts belong to forecast-payload ancestry and are not reused for this raw-source transformation. K4R4 records transformation lineage only in its result envelope:

- `derived_csv_is_source_evidence=false`
- `new_scientific_receipt_created=false`
- `normalization_receipt_created=false`
- `verified_receipt_bindings_created=false`
- `stable_engine_execution_proven=false`
- `blind_validation_eligible=false`
- `production_forecast_generated=false`
- `dr002_activated=false`
- `promotion_allowed=false`

## Verification

Focused offline tests cover the valid transformation, raw rather than derived frozen binding, exact header and LF encoding, row-order preservation, deterministic repetition, raw/receipt hash mismatch, malformed/noncanonical/parented/wrong-type receipts, receipt/source/scope identity failures, strict JSON failures, empty or wrong top level, row shape, foreign scope, UTC dates, numeric scalar rules, exact derived hashing, absence of invented columns and fabricated receipts/bindings, unchanged frozen trust, pure/offline implementation, existing producer `weather.csv` compatibility, and all named dependency blob pins.

Only the focused adapter suite and cheap Python syntax/import checks are run. No live OpenF1 call or GitHub Actions workflow is part of K4R4.

## Claim ceiling

K4R4 does not prove a producer execution, stable-engine execution, blind eligibility, publisher authentication or completeness, an authenticated observation clock, earlier historical availability, production rollout/enforcement, model accuracy improvement, DR-002 activation, or promotion.

OpenF1 remains an unofficial source and does not outrank official FIA/F1/team/Pirelli evidence.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion **NOT ALLOWED**.
