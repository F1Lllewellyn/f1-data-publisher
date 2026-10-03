# DR-002 Gate 2B-6 — Replay and leakage evidence

Work order **F1-WO-DR002-2B6-001**, issue #133. Part A landed reviewed PR #132 unchanged as merge `4ece6b3f548c66f25c537568fb20e92cbc50261e`; this is also the starting Part B main SHA. All 14 declared dependency Git blob fingerprints matched. Branch: `dr002-gate2b6-replay-leakage-evidence-20261003`.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Gate 2B-7 is **NOT AUTHORIZED / not ready**. This is an isolated offline audit, not production enforcement, new capture, forecast execution or a history upgrade.

## Selected real case and observed facts

OBSERVED REPOSITORY FACT: exactly the four named files under `history/forecast_bundles/2026_1295_azerbaijan_baku_baku/20260925T150434Z/post_qualifying/stable_baseline/` were fetched read-only and checked against the work-order blobs. No history discovery or passing-case selection occurred.

| File | Exact Git blob SHA |
| --- | --- |
| bundle_lock_manifest.json | `0e5d8b62625f5a35d35914b6451e6d85cb73e7df` |
| source_snapshot_manifest.csv | `64fda6e9dbced3daa4141b343a6d71fad4ba897e` |
| engine_lane_config.json | `2c82835c2025113c4e9b3fe817fbf847552d947b` |
| forecast_rows.csv | `74b26427d606e53ac91212b52887b844a9bf4d8e` |

The manifest says locked, `forecast_lock_utc=2026-09-25T15:04:34Z`, and `blind_validation_eligible=true`. Lane/config text names Engine_2026-06-07_STABLE. There are **30 forecast rows** in this exact case. The sole source snapshot row is `forecast_source`, referencing the producer's latest forecast_rows.csv; its source_timestamp_utc equals lock time. It binds no upstream source_capture or upstream first observation.

The snapshot's source SHA is `9ee560d7010afb28f271d2050fa9d1b9075e91211ce4c754f377ecde92b6a2b4`. Exact bundled forecast_rows.csv SHA is `e3f3009d8082f9964e1e42d66faa2cf4f8523141172283b8f457f258b83963cf`. Those are different objects/hashes; a pre-copy source reference cannot be silently treated as the exact bundled artifact or upstream source provenance. The difference alone does not prove corruption or leakage.

CSV CRLF bytes were preserved for exact blob verification. The tests embed a compact compressed, pinned copy of these four read-only historical byte fixtures, not newly generated predictions. The module accepts explicit bytes and performs no filesystem reads/writes or discovery.

## Six required conclusions

1. **Can this real bundle be certified blind?** No. EXECUTED RESULT: the unchanged Gate 2A classifier returns `TEMPORAL_ELIGIBILITY_UNPROVEN`, `blind_validation_eligible=false`, reason `legacy_or_unknown_schema`. The original history is untouched; this is a separate audit result.
2. **What is missing?** Upstream exact source captures and first_observed/ingestion provenance; independently authenticated bindings; a frozen consumed input manifest with scope/cutoff/deadline/mandatory-source policy; actual producer and distinct engine execution proof; credible lock and separate outcome-boundary proof. No cutoff, source observation or outcome boundary was invented from the lock or snapshot timestamp.
3. **Is actual leakage proved?** No. **Leakage cannot be ruled out / temporal eligibility is unproven** is the supported conclusion. It is not the claim **leakage occurred**. The audit records actual_leakage_proven=null. Lane text cannot prove stable-engine execution.
4. **Can a clean replay fixture be represented?** Yes, conditionally. Synthetic source_capture bytes, scopes, hashes, chronology and independently supplied synthetic external bindings pass as-of contract checks. `execution_mode=replay` still classifies `OUTCOME_AWARE_EVALUATION_ONLY` under unchanged Gate 2A. Input cleanliness, forecast classification and production blind eligibility remain distinct. No fixture is upgraded to historical blind prediction.
5. **What minimum evidence is needed for trustworthy replay?** Exact source bytes plus immutable scoped capture receipts establishing observer possession before the declared cutoff, ingestion eligibility where required, authorized predictive/outcome role declarations, authenticated issuer/clock/storage bindings, frozen consumed inputs, exact code/execution/output proof, and separately evidenced lock/outcome/revision boundaries with approved policy. A hash or later API/latest/history/Git availability cannot establish earlier possession. Revision completeness also requires a trustworthy observation process.
6. **Is production enforcement ready?** No. This audit resolves none of the accepted live authentication, lock/outcome/revision or production broad-discovery gaps. Gate 2B-7 remains not ready and not authorized.

## Evaluator semantics and trust boundary

`evaluate_as_of()` accepts only explicit forecast records, capture dicts, exact byte mappings, declared evidence roles and optional externally supplied bindings/execution records. It constructs no bindings or receipts. Gate 2B-1 envelope, chronology, canonical/hash helpers and Gate 2A classification are reused unchanged; Gate 2B-4 trust constants are reused.

| Input evidence state | Meaning |
| --- | --- |
| AS_OF_CONTRACT_CLEAN | All declared source contract checks pass, conditional on external bindings; not production authentication |
| INELIGIBLE | Explicit temporal/ingestion/outcome-input violation is detected |
| UNPROVEN | Observation, capture, policy or external provenance is missing |
| HOLD | Malformed, inconsistent, tampered or out-of-scope evidence |

The source-role map is an explicit declaration, not independent source authority. Missing role fails unproven; outcome/race_result/post_event input fails ineligible. Future adapters must substantiate role policy. No naming heuristic certifies source semantics.

Observation uses only first_observed_utc; early publisher/event timestamps cannot rescue a late capture. Required late ingestion fails. Matching source bytes observed later do not establish earlier possession. Generation/lock relative to an explicitly supplied outcome boundary is reported separately; Gate 2A forecast state is never reinterpreted. Missing boundary times remain unproven. Self-asserted trust fields confer no trust.

Source trust remains UNBOUND; production_authenticated=false; historical_availability_proven=false; dr002_activated=false. AS_OF_CONTRACT_CLEAN is synthetic/conditional contract evidence, not a production provenance claim. The module conservatively reports engine execution NOT_PROVEN; it does not implement an engine audit or infer it from a stable lane label.

## Non-duplication: existing operational replay

OBSERVED REPOSITORY FACT: `session_processor_loop_replay_validation_runner_v30x.mjs` loads embedded or explicit session-loop fixtures, classifies no-gate/readiness/blocking/governance states in classifyCase(), and summarizes expected-status agreement as replay_passed. The v30x policy provides four no-op/contract-ready/data-ready/blocking fixture cases with live fixture evidence disabled and consumer writes blocked.

DETERMINISTIC INFERENCE: those operational fixture statuses test session-loop/control behavior, not source first-observation, frozen forecast inputs or DR-002 leakage safety. Their replay_passed is not temporal proof. This new evaluator refines the forecast-evidence audit layer; neither existing file was modified or executed.

## Validation and protected scope

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_replay_leakage_evidence_v1.py' -v`

36 focused tests passed, zero failures/errors. This includes exact pinned real Baku bytes, changed/missing-byte HOLD, clean/late/missing synthetic observation, ingestion, early publisher/event timestamps, outcome inputs, replay evaluation-only state, stable labels, unchanged legacy blind flags, exact source pairing, trust boundaries, determinism and no input mutation. AST/import checks passed. Only this suite ran; no broader tests, F1 API queries or workflows were executed. Initial local validation caught a scratch CSV newline conversion; exact CRLF bytes were restored and all pinned hashes then passed. No repository history changed.

Exactly three new files: evaluator, focused tests and this checkpoint. No existing code/schema/workflow/model/stable-engine/workbook/latest/history/ledger changed. No production producer or engine ran; no forecast was generated. Forecast gate OFF; promotion NOT ALLOWED. Pipedream/Gmail were not used.

RECOMMENDATION: adviser delta review of this bounded evidence audit and its remaining proof gaps. No Gate 2B-7 work is authorized by completion. Rollback is reverting this isolated PR; no production/data migration is needed.
