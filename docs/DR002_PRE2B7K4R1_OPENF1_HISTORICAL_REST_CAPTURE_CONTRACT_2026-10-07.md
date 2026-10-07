# DR-002 pre-2B-7K4R1 — hosted OpenF1 historical REST capture contract

Work order: [F1-WO-DR002-PRE2B7K4R1-001 / Issue #207](https://github.com/F1Lllewellyn/f1-data-publisher/issues/207)  
Observed main: `b22554149f91d04fc44fc0b2a156e8caf46622df`  
Recorded: 2026-10-07  
Result: CONTRACT IMPLEMENTED — OFFLINE ONLY; focused tests PASS.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Decision and architecture boundary

We use the hosted OpenF1 REST API at exactly `https://api.openf1.org/v1`; we do not self-host `br-g/openf1`.

This contract is for historical, post-session capture. It is not a live-streaming, MQTT, or WebSocket contract. It does not use or authorize paid live access. The fixed 30-minute delay after the caller-supplied session end keeps this lane outside OpenF1's documented live window and allows the prediction products to use the hosted historical REST path they actually need.

This is a refinement of the existing lightweight OpenF1 source-closure lane, not a second ingestion architecture. No existing source-closure file or workflow changed, and no workflow was added or dispatched.

OpenF1 is an unofficial provider. Its evidence does not outrank official FIA, F1, team, or Pirelli evidence.

## Pure caller-supplied contract

`scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py` accepts only explicit in-memory facts and bytes:

- exact `event_id`, `meeting_id`, and `session_id` scope;
- one structurally valid OpenF1 endpoint name;
- a non-empty mapping of scalar request parameters;
- exact raw HTTP response bytes and HTTP status;
- caller-supplied session-end, first-observed, ingestion, and receipt-creation UTC timestamps;
- caller-supplied capture reference and implementation identity; and
- optional explicit valid event and publisher timestamps.

It performs no network, filesystem, clock, subprocess, environment, credential, or secret access. The caller remains responsible for obtaining and persisting the response bytes.

## Deterministic request and exact-byte handling

The canonical request URI is built from the fixed API base, one safe endpoint segment, and key-sorted UTF-8 percent-encoded scalar parameters. Parameter order supplied by the caller cannot change the URI or receipt.

The raw response must be non-empty exact `bytes`. Its SHA-256 is computed before any JSON interpretation, and the same bytes are returned unchanged in the assessment. JSON is parsed only for structural acceptance and list row count. Duplicate keys at any nesting depth, malformed JSON, non-standard numeric constants, and top-level scalar JSON fail closed. Top-level lists and objects are accepted; only lists receive a numeric `row_count`.

The bytes are never reserialized before hashing. Noncanonical whitespace therefore changes the bound response digest exactly as it should.

## Historical-window and chronology semantics

The historical-window eligibility time is exactly:

```text
session_end_utc + 1800 seconds
```

Validation requires:

```text
historical_window_eligible_utc <= first_observed_utc <= ingested_utc <= receipt_created_utc
```

Observation exactly at the boundary is eligible. Observation one microsecond before it is `HOLD`. Non-200 HTTP status, malformed scope/request/bytes/timestamps, or inconsistent chronology also produces `HOLD`.

`openf1_documented_historical_window_satisfied=true` means only that the explicit +1800-second rule was met. Exact bytes first observed later do not prove that those bytes existed earlier, and the contract never backdates availability.

## Existing source-capture receipt binding

A validated assessment creates canonical bytes for the existing Gate 2B-1 `source_capture` receipt type. No new scientific receipt type is introduced. The receipt is parentless and uses the existing schema fields exactly:

- `source_id` derived deterministically from OpenF1, endpoint, meeting, and session;
- canonical `source_uri`;
- `source_sha256` equal to the exact raw-response SHA-256;
- explicit valid event/publisher times or `null`;
- caller-supplied `first_observed_utc`, `ingested_utc`, `capture_ref`, and `implementation`;
- exact DR-002 scope; and
- caller-supplied `receipt_created_utc`.

The unchanged Gate 2B-1 envelope and temporal validators must both accept the receipt. The assessment returns its canonical bytes and exact SHA-256. It does not create or claim any `verified_receipt_bindings`; external provenance binding remains a separate trust interface.

## Immutable trust ceiling

Even on `OPENF1_HISTORICAL_REST_CAPTURE_VALIDATED`, all of these remain false:

```text
publisher_source_authenticated
openf1_official_f1_source
observation_clock_authenticated
historical_availability_before_first_observation_proven
publisher_revision_completeness_proven
global_observation_completeness_proven
production_revision_tracking_proven
stable_engine_execution_proven
blind_validation_eligible
dr002_activated
promotion_allowed
```

Any caller attempt to assert one of these fields true produces `HOLD`.

## Focused verification

```text
python3 -m py_compile \
  scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py \
  tests/test_dr002_openf1_historical_rest_capture_v1.py

python3 -m unittest -v tests/test_dr002_openf1_historical_rest_capture_v1.py

Ran 22 tests
OK
```

The suite covers valid list/object responses, exact noncanonical raw bytes, deterministic parameter ordering, the exact boundary and one-microsecond failure, both chronology failures, HTTP failure, malformed and duplicate-key JSON, malformed endpoints/parameters, unchanged parentless receipt validation, exact source/receipt hashes, absence of fabricated verified bindings, immutable trust ceilings, rejected trust assertions, deterministic repetition, pure/offline behavior, optional timestamp handling, no new receipt type, and all named dependency pins.

## Accepted dependency pins

| Path | Git blob | Result |
|---|---|---|
| `scripts/openf1/publish_openf1_lightweight_source_closure.py` | `ebdba37477b7efdc584c2550295cb7c61cf53481` | PASS |
| `.github/workflows/f1-openf1-lightweight-source-closure.yml` | `7521e0e91e201b0610d8771a8524393c59ba1ecb` | PASS |
| `configs/openf1/openf1_lightweight_source_closure_policy.json` | `d21765b33e66dfa499b92c9f44a4543608f2c6a4` | PASS |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` | PASS |
| `scripts/forecast_bundles/dr002_verified_source_consumer_v1.py` | `e402939202ed579c368499f3baefb3641de27de7` | PASS |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` | PASS |

Relevant-path/blob comparison was used; unrelated generated-output movement on main did not alter these dependencies.

## Claim ceiling and next integration step

This contract proves only that explicit caller-supplied post-window OpenF1 REST response bytes can be validated, retained exactly, and deterministically bound into the existing parentless `source_capture` receipt schema.

It does not prove official-source authority, publisher authenticity, authenticated observation time, historical availability before local first observation, publisher/global completeness, production revision tracking, stable-engine execution, blind eligibility, model accuracy, DR-002 activation, or promotion. It does not authorize Gate 2B-7.

If this contract is accepted and merged, the next integration step is to wire it into the existing lightweight source-closure publisher without creating a second ingestion architecture. That integration requires a separate authorized work order.

This Work Result adds exactly:

- `scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py`;
- `tests/test_dr002_openf1_historical_rest_capture_v1.py`; and
- `docs/DR002_PRE2B7K4R1_OPENF1_HISTORICAL_REST_CAPTURE_CONTRACT_2026-10-07.md`.

No existing file changed. No workflow was added or dispatched.
