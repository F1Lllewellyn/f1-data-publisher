# DR-002 Gate 2B-5 — Full shadow assessment

Work order: F1-WO-DR002-2B5-001, GitHub issue #131. Starting main: `a003562f338b00bddbe2957bcedbfb537e10fe35`. Branch: `dr002-gate2b5-full-shadow-assessment-20261003`.

DR-002 remains **PROPOSED — NOT ACTIVATED**. This is an isolated read-only assessment across the integrity chain, not a new passing live chain. No existing implementation changed.

## Evidence basis and executed assessment

OBSERVED REPOSITORY FACT: all eleven declared dependency Git blob fingerprints matched fresh main. Accepted predecessors PR #129 and #130 are merged. The exact accepted Gate 2B-3B2 checkpoint SHA-256 is `1df8cfba0a5aca49b5bca1fb054ec772614b7ce8bdab405fcdce4b7dcde605af`.

The assessment reuses the adviser's previously accepted independent artifact inspection. GitHub run/artifact metadata was freshly checked; ZIPs were not downloaded or independently re-inspected in this task. Artifact metadata matching corroborates identity, not production authentication. The module takes explicit checkpoint bytes, run/artifact metadata and dependency bytes/fingerprints; it performs no GitHub or source requests itself.

| Accepted run / attempt | Head | Artifact ID / name | ZIP SHA-256 |
| --- | --- | --- | --- |
| 37133694090 / 1 | `5f25e048edeb6e46a5a77e70c5c97857a59f6bb6` | 11277594100 / dr002-weather-capture-37133694090-1 | `df9ced90ba0df602d4e896c48292964ff812880f9a38dd5b4f0867da88ff6b6d` |
| 37152568516 / 1 | `8d164fce63aea97aee7c2db71b6eb23d8f5e2055` | 11284482487 / dr002-shadow-execution-37152568516-1 | `92df37ad1a0c292b32f3f823ac5ae080399495a2251b75c1477b3967b12db507` |

Both metadata records report unexpired artifacts, workflow_dispatch, attempt 1 and successful runs. The accepted source is Baku meeting 1295/session 11371, 85 OpenF1 weather rows. Its October observation establishes no earlier historical availability.

EXECUTED RESULT: `assess()` ran on those explicit accepted facts and exact current dependency bytes. Result `COMPLETED`; no invalidation reasons. Runtime JSON stayed in scratch and is not committed. Identical inputs produce identical canonical output. Missing/changed pins downgrade live claims to HOLD. A scientifically correct HOLD finding does not imply that the assessment execution failed.

## Assessment matrix

PROVEN_LIVE below means accepted predecessor live evidence, not a fresh ZIP audit or authenticated issuer claim.

| Layer | Status | Strongest defensible claim | Blocker / limitation |
| --- | --- | --- | --- |
| Source capture | PROVEN_LIVE | Exact bytes persisted/read back, 85 rows | UNBOUND accepted observation |
| Temporal observation | PROVEN_LIVE | Observer possession on 2026-10-03 | No historical backdating |
| Event/session containment | PROVEN_LIVE | Single shadow source matched 1295/11371 | Does not contain the production producer |
| Frozen evidence | PROVEN_LIVE | Explicit receipt/content set bound | Limited to accepted weather shadow |
| Producer execution | PROVEN_LIVE | Shadow code/input/output relationships reviewed | NOT A PREDICTION |
| Engine execution | NOT_PROVEN | No separate engine executed | Engine fields null |
| Forecast lock | NOT_PROVEN | Contract proven offline | No live lock/time/storage proof |
| Outcome boundary | NOT_PROVEN | Contract proven offline | No separate live outcome capture |
| Revision handling | NOT_PROVEN | Contract proven offline | No live revision/completeness proof |
| Blind eligibility | NOT_APPLICABLE | OUTCOME_AWARE_EVALUATION_ONLY | post_event cannot be blind |
| External binding/authentication | NOT_PROVEN | UNBOUND | No authenticated issuer/clock/storage binding |
| Historical availability | NOT_PROVEN | October observation only | Later retrieval cannot prove earlier possession |
| Stable-engine provenance | NOT_PROVEN | No protected engine execution proof | Lane/configuration text is not execution |
| Current production-producer containment | HOLD | Broad discovery exists | Production path not contained by shadow contract |
| Readiness for production enforcement | HOLD | Assessment complete, enforcement not ready | Authentication/full-chain/replay evidence missing |

Lock, outcome and revision capability are separately reported as CONTRACT_PROVEN_OFFLINE, based on accepted PR #129 and its 47 reviewed tests. Those tests were not rerun. The unchanged Gate 2A classifier supplies post_event evaluation-only classification. Gate 2B-1 canonical JSON/hash helpers and Gate 2B-4 trust constants are reused.

## Current production incompatibilities

OBSERVED REPOSITORY FACT: source-code AST inspection of supplied bytes finds `find_sources()` using `rglob` at producer line 114; bundle locker stable lane label `Engine_2026-06-07_STABLE` at line 18; and `blind_validation_eligible: source_found` at line 197. Production modules were neither imported nor executed.

DETERMINISTIC INFERENCE: recursive candidate discovery remains a contamination risk; source existence is insufficient blind proof; a lane label cannot establish stable-engine execution. Existing candidate selection and driver-universe discovery are not constrained by this isolated assessment. No production defect is closed by adding the report.

## Validation and scope

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_full_shadow_assessment_v1.py' -v`

35 focused offline tests passed, zero failures/errors. Imports and AST parsing succeeded during the actual assessment execution. Tests cover status vocabulary, claim ceilings, metadata/checkpoint/dependency tampering, missing evidence, post_event, trust, deterministic results, no input mutation, and absence of network/clock/filesystem discovery or output writes. No unrelated suite or workflow was run.

Exactly three additions: the assessment module, its focused tests, and this checkpoint. No production caller is wired. No receipts or verified_receipt_bindings are created. No producer, stable engine, forecast, workbook, latest/history/ledger state, workflow or model changes occurred. Forecast gate OFF; promotion NOT ALLOWED. Source trust stays UNBOUND; production_authenticated=false; historical_availability_proven=false; dr002_activated=false. Pipedream/Gmail were not used.

## Bounded next decision

RECOMMENDATION: return the evidence gaps for Gate 2B-6 replay/leakage design review. Resolve authenticated capture/execution/lock/outcome/revision proof gaps before separately considering Gate 2B-7 enforcement. Neither gate has begun. Production enforcement requires separate authorization; this result does not authorize it. Rollback is reverting this isolated assessment PR; no data migration is needed.
