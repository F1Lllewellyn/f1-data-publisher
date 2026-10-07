# DR-002 pre-2B-7K2 — OpenF1 stream version-evidence contract

Work order: [F1-WO-DR002-PRE2B7K2-001 / Issue #200](https://github.com/F1Lllewellyn/f1-data-publisher/issues/200)  
Recorded: 2026-10-07  
Result: COMPLETED — deterministic pure/offline contract and focused tests PASS.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Purpose and provider semantics

This checkpoint represents and validates caller-captured OpenF1 stream messages without connecting to OpenF1. Under the provider semantics recorded in Issue #200, `_id` is a unique, ever-increasing message identifier usable for chronological ordering, while messages on the same topic with the same `_key` are versions or updates of one underlying document.

Those semantics do not promise contiguous identifiers, lossless client delivery, replay of every historical version, authenticated clocks, or complete receipt of publisher-side revisions. K2 therefore validates only observed chronology and observed same-object version evidence.

## Pure/offline API

`assess_openf1_stream_version_evidence` accepts only explicit caller-supplied values:

- provider identifier, required exactly `openf1`;
- declared subscription topics;
- connection identifier and observation-window strings supplied as facts;
- captured message records containing topic, exact raw JSON bytes, and a caller-supplied receive-order index;
- an optional already-produced K1 assessment; and
- explicit unsupported-claim fields, all of which must remain false.

The implementation imports only `hashlib` and `json`. It performs no network, MQTT, WebSocket, filesystem discovery, wall-clock, subprocess, environment, secret, credential, or workflow operation.

Each raw JSON value is parsed strictly with duplicate-key rejection and must be an object containing a non-negative integer `_id` and a non-empty string `_key`. No other provider payload field is required. Exact supplied bytes are preserved by SHA-256 in the assessment.

The output is an assessment envelope, never a scientific receipt. No receipt type was added.

## Assessment semantics

Successful validation reports `OPENF1_STREAM_VERSION_EVIDENCE_VALIDATED`. Malformed, ambiguous, undeclared, duplicated, incompatible, or unsupported evidence reports `HOLD`.

For validated evidence, the assessment records:

- total messages and unique `_id` count;
- duplicate detection and minimum/maximum observed `_id`;
- whether `_id` values are strictly increasing in caller-supplied receive order;
- whether numeric gaps are present, without treating gaps as loss;
- the observed topic set;
- identities keyed by `(topic, _key)`;
- exact raw-byte SHA-256 for every message;
- per-object sequences sorted by `_id`;
- per-object message and distinct-payload-hash counts; and
- identities with more than one observed message.

Different topics with the same `_key` remain distinct identities. Non-monotonic receive order is retained as an observed fact while per-object chronology remains sorted by `_id`; it does not create a transport-loss or completeness conclusion.

## K1 composition

An optional K1 assessment is accepted only when its schema, assessment type, status, coverage fact, receipt-binding fact, and immutable trust ceilings are structurally compatible with the accepted K1 contract. K1 `PROVEN` preserves declared-window schedule coverage as a separate true fact. K1 `INCOMPLETE` preserves it as false. Omitting K1 reports coverage as not supplied and unproven.

K1 is not reimplemented. No K1 status can upgrade OpenF1 publisher or global completeness.

## Immutable claim ceiling

Every successful K2 assessment keeps the following false:

```text
openf1_id_contiguity_assumed
message_loss_proven_from_id_gaps
publisher_revision_completeness_proven
global_observation_completeness_proven
publisher_source_authenticated
observation_clock_authenticated
historical_availability_proven
production_revision_tracking_proven
full_gate2b1_chain_verified
stable_engine_execution_proven
blind_validation_eligible
dr002_activated
promotion_allowed
```

Caller attempts to assert any of these fields true fail closed to `HOLD`. OpenF1 API authentication is not treated as cryptographic publisher authenticity for each message.

## Focused verification

Cheap syntax compilation and direct import succeeded. The focused suite ran 23 tests successfully:

```text
python3 -m py_compile \
  scripts/forecast_bundles/dr002_openf1_stream_version_evidence_v1.py \
  tests/test_dr002_openf1_stream_version_evidence_v1.py

python3 -m unittest -v tests/test_dr002_openf1_stream_version_evidence_v1.py

Ran 23 tests
OK
```

The suite covers valid synthetic evidence; exact raw-byte hashes; same-topic/same-key grouping; cross-topic key separation; per-object `_id` ordering; non-contiguous identifiers; duplicate identifiers; malformed JSON and duplicate keys; missing or invalid identifiers and keys; undeclared topics; malformed or duplicate receive indexes; non-monotonic receive order; immutable completeness ceilings; K1 proven/incomplete composition and malformed K1 rejection; caller assertion rejection; determinism; absence of a new receipt type; pure/offline implementation; and all named dependency pins.

## Accepted dependency pins

All Issue #200 dependencies remained unchanged:

| Path | Git blob | Result |
|---|---|---|
| `scripts/forecast_bundles/dr002_observer_coverage_contract_v1.py` | `e0794e3c901b70a636b5d552ffd673576aeea412` | PASS |
| `tests/test_dr002_observer_coverage_contract_v1.py` | `d8ea5592057f6c2f8e083636de65ea5e477f99ba` | PASS |
| `docs/DR002_PRE2B7K1_OBSERVER_COVERAGE_COMPLETENESS_CONTRACT_2026-10-07.md` | `63d5e579ed7c95a74e0fdf878bb37c366b90c9e3` | PASS |
| `docs/DR002_PRE2B7J2_LIVE_GITHUB_ATTESTED_REVISION_SHADOW_2026-10-06.md` | `8803e8f7d6373ea7f4319a7737f9430feb90893b` | PASS |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` | PASS |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` | PASS |

## Required checkpoint answers

**Can OpenF1 `_id` provide observed chronological ordering?**  
YES, under provider-documented semantics.

**Can same-topic same-`_key` messages represent observed versions/updates of one object?**  
YES, under provider-documented semantics.

**Do gaps in observed `_id` prove message loss?**  
NO.

**Do unique/increasing `_id` values prove all messages were received?**  
NO.

**Does observing every declared K1 slot prove all OpenF1 revisions were received?**  
NO.

**Does K2 prove publisher/global revision completeness?**  
NO.

**Is a future live OpenF1 stream observer technically plausible?**  
YES, but it requires separate authorization, credentials handling, connection-loss semantics, and evidence design.

**Is Gate 2B-7 authorized?**  
NO.

## Repository delta and limits

K2 adds exactly:

- `scripts/forecast_bundles/dr002_openf1_stream_version_evidence_v1.py`;
- `tests/test_dr002_openf1_stream_version_evidence_v1.py`; and
- `docs/DR002_PRE2B7K2_OPENF1_STREAM_VERSION_EVIDENCE_CONTRACT_2026-10-07.md`.

No existing file changed. No workflow was added or dispatched. No provider connection, credential access, live observer, new receipt type, production path, completeness proof, Gate 2B-7 work, activation, or promotion occurred.
