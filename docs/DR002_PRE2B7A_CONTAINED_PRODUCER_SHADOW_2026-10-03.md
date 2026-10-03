# DR-002 pre-2B-7A — Contained current-producer shadow

Work order: **F1-WO-DR002-PRE2B7A-001**, GitHub issue #136. Starting main: `9ddc93ede09bf68f13f9d7ddf9fbc01887ade25f`. Accepted predecessor: PR #134, merged at that same SHA. All ten declared dependency fingerprints matched. Branch: `dr002-pre2b7a-contained-producer-shadow-20261003`.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Gate 2B-7 is not implemented. This is a synthetic contained mechanics proof, not production enforcement, a production forecast, accuracy evidence or model promotion.

## Executed facts

OBSERVED REPOSITORY FACT: the pinned current generic producer exposes read_csv(), build_driver_universe(), starting_grid_map(), source_readiness_score(), score_driver(), probability_from_rank() and produce_rows() independently of find_sources()/main()/write functions. The new adapter invokes those exact real functions. No algorithms, weights, priors or probabilities were reimplemented or changed.

The fixed producer byte identity is:

- implementation: `scripts/forecasts/produce_actual_forecast_rows_v1.py`
- Git blob: `05296f3e9b0aa433b2679864fef5bb7276e44627`
- exact code SHA-256: `dc91487b5cbc7dca9df8040604c7ef19e6922c8b103f217e469310588409e8fa`

EXECUTED RESULT: an explicit synthetic post_qualifying/stable_baseline case supplied two driver rows and two starting-grid rows. Only synthetic drivers 10 and 20 entered the universe; the grid was 20=1, 10=2. All seven omitted source types had zero counts. Real readiness calculation returned **0.38**; explicitly adding one weather row returned **0.48**; removing it restored the original readiness. The producer emitted two unchanged internal rows, wrapped in status:

`CONTAINED_CURRENT_PRODUCER_SHADOW_ONLY_NOT_A_PRODUCTION_FORECAST`

Supplied generation time: `2026-01-01T10:00:00Z` (synthetic explicit value, not a real forecast timestamp). Repeated identical inputs produced identical canonical result bytes/hash:

`7500cbe9e04365513824e5813a655d1d3b2a1a43db085853257d10245fc436b2`

This hash covers the deterministic result body, excluding its outer hash field. Runtime JSON remained in scratch, outside the repository PR.

## Explicit interface and containment

`run_contained_shadow()` accepts an explicit list of source records: source_name, source_id, exact content bytes, source_sha256 and optional source_capture receipt. It accepts event/meeting/session scope, a current producer gate/lane and explicit generation time. No input source paths or repository root are accepted. Source names must belong to the pinned producer's SOURCE_FILES keys. Duplicate names/identities, absent/mismatched bytes, invalid gate/lane and invalid provenance fail closed.

Only supplied bytes are materialized as `<source_name>.csv` in a disposable temporary directory. They are read back exactly before the producer parser sees them. Source maps contain only those paths; missing source types stay absent. Temporary directory names and host paths are excluded from the result/hash. No latest/history/ledger/workbook path is searched or written. Cleanup disposes temporary inputs even on exceptions.

The fixed implementation file is read and fingerprint-checked **before** executing its exact code into a fresh module namespace with a non-main name. This is not a sandbox for arbitrary/unreviewed Python. Changed producer bytes fail before execution. Standard-library imports and the accepted function call paths were inspected; no production entry point is invoked. Fresh namespaces avoid mutating a shared production module. Only utc_now is temporarily replaced for the bounded produce_rows() call and restored in finally, including on failure.

Optional receipt/content pairs use the unchanged Gate 2B-3A frozen evidence builder through an explicit in-memory reader; no parallel provenance/hashing semantics were added. Source identity and scope are checked. Scope-bearing CSV columns, when present, must also match the explicit event/meeting/session. Missing row-level scope is not inferred as independent proof: receipt-free data is explicitly NO_CAPTURE_RECEIPT. Partial receipt coverage is reported as a subset, not complete provenance. No source or execution receipts are emitted; no verified_receipt_bindings are created.

## Eight scientific conclusions

1. **Can current scoring logic run from explicitly frozen inputs only?** Yes, for the inspected pinned implementation and synthetic case; parser, universe, grid, readiness, scoring, probabilities and row production ran unchanged.
2. **Can discovery be bypassed without production code changes?** Yes in this isolated shadow. Tests deny find_sources, candidate-priority, main, copy_to_latest_and_history, write_csv and write_json. Rogue driver/grid/weather/pit files in latest/history-like trees under an actual changed working directory did not affect universe, grid, readiness, scores or output hash. rglob is also denied in a focused test.
3. **Can the output be deterministic with explicit time?** Yes. Canonical repeated results match; the original clock cannot leak into row timestamps and is restored after success/failure.
4. **Does this prove the stable engine executed?** **No.** Stable lane/config label != stable engine execution proof. engine_implementation=null, engine_execution=NOT_PROVEN, stable_engine_executed=false. The generic producer ran, not Engine_2026-06-07_STABLE.
5. **Does this close authentication?** **No.** Byte hashes and Git blobs prove identity, not truthful issuer/timing or runtime authentication. Sources remain UNBOUND; production_authenticated=false; historical_availability_proven=false.
6. **Does this close live lock/outcome/revision proof?** **No.** None were captured or emitted. There is no forecast eligibility, blind scoring or historical availability claim.
7. **What eventual production change is needed?** RECOMMENDATION: separately authorize an explicit frozen-input interface at the producer/orchestration entry boundary, with validated exact inputs replacing find_sources on the enforced path. Reuse existing parser/scoring functions, preserve missing-source semantics, and add authenticated lineage/lock/outcome/revision bindings. This adapter is not wired into main, scheduled workflows or production consumers.
8. **What remains before Gate 2B-7?** Authenticated capture/execution/clock/storage binding, real lock/separate outcome/revision evidence and completeness, approved product cutoff/deadline/source policy, integration of frozen containment into actual production entry paths, and satisfactory replay/shadow evidence. This isolated proof does not authorize enforcement.

## Validation and scope

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_contained_producer_shadow_v1.py' -v`

**41 focused offline tests passed; zero failures/errors.** Syntax/import checks and repeated actual synthetic execution passed. Tests spy on all required real producer functions, deny discovery/writes, exercise rogue inputs, exact byte/hash tampering, duplicate/missing inputs, receipt scope/content mismatch, gate/lane validation, temporary-only reads/writes, disposal, deterministic ordering and clock restoration. No unrelated suite ran and no workflow was dispatched.

Exactly three additions: adapter, tests and this checkpoint. Existing producer/DR-002 code and schema, stable engine, model, canonical workbook, workflows, schedules, latest/history/ledgers and Pipedream/Gmail are untouched. No production forecast was generated. Internal producer rows retain their original strings as required; the outer wrapper is authoritative shadow metadata and must not be stripped to publish them as production forecasts.

Forecast gate OFF; promotion NOT ALLOWED; dr002_activated=false. No engine_execution, producer_execution, normalization, lock, outcome or revision receipt is emitted. Rollback: revert this isolated PR; no production/data migration. Return to adviser review; no merge or enforcement is implied.
