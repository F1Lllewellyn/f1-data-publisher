# DR-002 pre-2B-7K1 — Observer coverage versus revision completeness contract

Work order: [F1-WO-DR002-PRE2B7K1-001 / Issue #197](https://github.com/F1Lllewellyn/f1-data-publisher/issues/197)  
Recorded: 2026-10-07  
Result: COMPLETED — deterministic pure/offline contract and focused tests PASS.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Purpose

This checkpoint adds the smallest offline distinction between:

1. complete execution of an explicitly declared observation schedule;
2. exact receipt and content binding for each successful observation; and
3. global or publisher revision completeness, which remains unproven.

A fully executed polling schedule does not prove that no publisher change occurred between slots. One or many revision receipts do not prove that every publisher revision was discovered.

## Pure/offline API

`assess_observer_coverage` accepts only explicit caller-supplied values:

- exact source ID and URI plus event, meeting, and session scope;
- exact observation-window start and end;
- an ordered list of planned slot IDs and due times;
- explicit attempts keyed by slot ID, with status and observation time;
- exact canonical `source_capture` receipt bytes for successful attempts; and
- exact source-content bytes for successful attempts.

The implementation reuses the unchanged Gate 2B-1 canonical JSON, SHA-256, receipt-envelope, timestamp, and temporal validation functions. It performs no filesystem discovery, network access, wall-clock read, subprocess call, environment/secret read, GitHub/OpenF1 call, workflow operation, or repository mutation.

The output is an assessment envelope, not a receipt. No receipt type was added.

## Decision semantics

| Result | Meaning |
|---|---|
| `DECLARED_WINDOW_SCHEDULE_COVERAGE_PROVEN` | Every declared slot has exactly one successful attempt, and every successful attempt has exact canonical parentless source-capture and source-content binding. |
| `DECLARED_WINDOW_SCHEDULE_COVERAGE_INCOMPLETE` | The input is structurally valid, but at least one declared slot is missing, failed, or cancelled. |
| `HOLD` | Input is malformed, ambiguous, noncanonical, out of scope/window, tampered, or attempts to assert unsupported publisher/global completeness. |

For a proven schedule, the contract requires:

- unique slot IDs;
- strictly increasing and unique due times inside the declared window;
- no undeclared or duplicate attempt slot;
- exactly one valid in-window attempt for every slot;
- `SUCCESS` for every slot;
- an exact canonical Gate 2B-1 `source_capture` for each successful slot;
- a parentless source-capture receipt;
- exact source-content bytes matching `payload.source_sha256`;
- exact source ID, source URI, event, meeting, and session scope;
- attempt observation time equal to receipt `first_observed_utc`; and
- ingestion not before first observation.

Missing, failed, and cancelled slots remain valid incomplete schedule evidence and are listed in `missed_or_failed_slots`. Duplicate or undeclared slots, invalid timing, mismatched bytes/scope, malformed receipts, and unsupported completeness assertions fail closed to `HOLD`.

## Trust ceiling

Even when declared-window schedule coverage is proven, every assessment keeps these values false:

```text
publisher_revision_completeness_proven: false
global_observation_completeness_proven: false
publisher_source_authenticated: false
observation_clock_authenticated: false
historical_availability_proven: false
production_revision_tracking_proven: false
full_gate2b1_chain_verified: false
stable_engine_execution_proven: false
blind_validation_eligible: false
dr002_activated: false
promotion_allowed: false
```

The contract emits separate facts for `declared_window_schedule_coverage_proven`, `all_successful_observations_receipt_bound`, missed/failed slot IDs, exact scope, exact window, and slot/attempt counts. It refuses caller attempts to set publisher or global completeness true.

## Focused verification

Cheap syntax compilation and direct import succeeded. The focused suite ran 20 tests successfully:

```text
python3 -m py_compile \
  scripts/forecast_bundles/dr002_observer_coverage_contract_v1.py \
  tests/test_dr002_observer_coverage_contract_v1.py

python3 -m unittest -v tests/test_dr002_observer_coverage_contract_v1.py

Ran 20 tests in 0.009s
OK
```

The suite covers complete coverage; missing, failed, and cancelled slots; duplicate and undeclared slots; duplicate/unordered due times; out-of-window attempts; noncanonical, malformed, parented, and wrong-type receipts; content hash mismatch; source/scope mismatches; attempt/receipt observation-time mismatch; ingestion before observation; immutable trust ceilings; changed source hashes; rejected completeness assertions; deterministic repeat equality; absence of a new receipt type; pure/offline implementation; and all named dependency pins.

## Accepted dependency pins

All named Issue #197 dependencies remained unchanged:

| Path | Git blob | Result |
|---|---|---|
| `docs/DR002_PRE2B7J2_LIVE_GITHUB_ATTESTED_REVISION_SHADOW_2026-10-06.md` | `8803e8f7d6373ea7f4319a7737f9430feb90893b` | PASS |
| `scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py` | `064d93ee5ae30354590a3fb95be598c5fe8b3b9a` | PASS |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` | PASS |
| `scripts/forecast_bundles/dr002_full_shadow_assessment_v1.py` | `b86c69ee7574ad4941b574962a91bcaf8bfb1501` | PASS |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` | PASS |

## Required checkpoint answers

**Can this contract prove that every declared observation slot executed successfully?**  
YES, when the supplied evidence satisfies the contract.

**Can it prove that every upstream publisher revision was observed?**  
NO.

**Can it prove global observation completeness?**  
NO.

**Does a revision receipt prove revision completeness?**  
NO.

**What additional evidence would be needed later?**  
A separately reviewed, authoritative publisher-history/version-sequence mechanism or equivalent trusted source-side completeness proof, plus authenticated observer timing and identity.

**Is Gate 2B-7 authorized?**  
NO.

## Claim ceiling and repository delta

K1 proves only a deterministic offline distinction between declared observer schedule coverage and unproven publisher/global revision completeness. It does not establish a live observer, real publisher revision history, publisher authentication, authenticated observer time, absence of changes between polls, production revision tracking or enforcement, stable-engine execution, blind eligibility, predictive accuracy, or DR-002 activation/promotion.

This Work Result adds exactly:

- `scripts/forecast_bundles/dr002_observer_coverage_contract_v1.py`;
- `tests/test_dr002_observer_coverage_contract_v1.py`; and
- `docs/DR002_PRE2B7K1_OBSERVER_COVERAGE_COMPLETENESS_CONTRACT_2026-10-07.md`.

No existing file changed. No workflow was added or dispatched. Gate 2B-7 did not begin.
