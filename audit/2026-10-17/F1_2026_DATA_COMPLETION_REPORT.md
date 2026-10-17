# F1 2026 historical session & race data completion audit — 17 October 2026

**Disposition: PARTIAL / HOLD; NOT 100% COMPLETE.** This is a verified, read-only **inventory**, not a completed data backfill. It does not modify protected engine, production prediction forecasts, canonical workbooks, or the open Austin Issue #309.

## Scope, authority, and evidence

- Official Formula 1 [2026 results/calendar](https://www.formula1.com/en/racing/2026): **17 completed Grands Prix**, through Singapore 11 October, next United States GP 25 October (excluded).
- Official [2026 Sprint calendar](https://www.formula1.com/en/latest/article/how-can-i-watch-the-2026-dutch-grand-prix.3PyLPAazrBNe8kQIS3wOfY): China, Miami, Canada, Great Britain, Netherlands, Singapore.
- **85 expected race-weekend sessions = 17 × 5.** Each Sprint weekend has FP1, Sprint Qualifying, Sprint, Qualifying and Race; each non-Sprint weekend has FP1, FP2, FP3, Qualifying and Race.
- Exact per-session keys are drawn from repository `latest/openf1_lightweight_source_closure/data/target_sessions.csv`, blob `65881fa1d003ea9daf35354a01b1ecd4c1b5802c`; cross-filtered against the 17 independently confirmed official race IDs, excluded cancelled April Bahrain/Saudi event targets and excluded pre-season tests.
- The October 16 source closure reports **101 target sessions**. That is NOT 101 officially completed championship sessions: this inventory isolates 85 actual sessions, 6 pre-season tests and 10 cancelled session rows from provider metadata. Completed-only selection in its CSV is not itself proof of a real completed race.

## Verified findings

| Measure | Value |
|---|---:|
| Completed 2026 championship weekends | 17 |
| Expected sessions | 85 |
| Current session-processor snapshots found | 46 |
| Processor snapshots marked clean | 33 |
| Processor snapshots requiring manual review | 13 |
| Expected sessions without current processor snapshot | 39 |
| Independently tested historical engine-consumer paths | 0 |
| Sessions proven end-to-end engine-complete | **0** (not tested; must not claim completion) |
| Targeted provider backfills performed in this audit | **0** |
| Repository protected files overwritten | **0** |
| Changes on main | **0** |

Each current processor manifest was fetched and its actual source classifications and row counts summarized in five staged evidence JSON files on this isolated branch. The coverage CSV includes **935 session/source rows** across the canonical 11 configured endpoints, with row counts, provenance pointers, source statuses and distinct engine-consumer status.

**Important:** a clean source within a processor manifest is marked `VERIFIED_COMPLETE` at the *source classification layer only*. Its separate `engine_accessibility` remains `RAW_PATH_INDICATED_RUNTIME_CONSUMER_UNTESTED`; **no session is classified fully complete at the combined source-plus-engine level**.

The separate October 16 lightweight source closure reports pass for 9 aggregate lanes; this is post-event historical retrieval, cannot prove publisher revision completeness, official FIA grid authority, original pre-race data availability, or full consumer readiness.

### Global lightweight lane reconciliation

| Lane | Observed CSV rows | Summary rows | Reconciled |
|---|---:|---:|---|
| drivers | 1209 | 1209 | MATCH |
| pit | 497 | 497 | MATCH |
| race_control | 5074 | 5074 | MATCH |
| starting_grid | 330 | 330 | MATCH |
| stints | 4558 | 4558 | MATCH |
| weather | 7680 | 7680 | MATCH |
| team_radio | 573 | 573 | MATCH |

The very large intervals (289688 rows) and position (33126 rows) are **not redownloaded** here; only summary metadata is observed. Per-session counts are taken from existing processor manifests when available.

### June artifact reuse

The retained original June CSV archive `F1_2026_Line_By_Line_API_Ingest_v4_COMPLETED.zip` has verified SHA-256 `21e068b06cf7ad482b00289c26f7c2af4720c8a803f94e36b5527c9f7b8f07fd`. It contains 5,272 race lap records over rounds 1–5, 110 race classifications over rounds 1–5, 129 qualifying records over rounds 1–6, and 136 race pit-stop rows over rounds 1–5. These are preserved as **partial historical evidence** only; they do not establish that the current engine has loaded those results.

### Unresolved gaps and risks

1. **39 absent current session processor snapshots:** address by event/session and required data lane using the coverage CSV. Do not assume missing upstream raw data when a processor snapshot is absent.
2. **13 actual nonclean manifests:** predominantly `openf1_starting_grid` provenance review on race/sprint sessions. For Singapore race the explicit unresolved anomalies are `fia_final_grid_unverified` and `grid_revision_time_unestablished_after_start`. Never silently clear a historical grid review using new post-event rows.
3. **All consumer paths require an actual bounded smoke test:** verified data presence and clean manifests do not prove end-to-end engine accessibility.
4. **Source completeness ceiling:** Oct 16 observations cannot establish what was known before any earlier 2026 GP or prove every upstream publisher revision was seen.
5. **Official calendar exception:** The round 16 Bahrain Grand Prix occurred at **Sepang, Malaysia**; do not conflate it with the separately cancelled April Bahrain round.
6. **No heavy telemetry or broad provider calls:** high-frequency car-data/location not downloaded; only existing metadata and compact historical source rows were inspected.

## Work performed and outcome

- Reused existing accepted repository pipeline, current processor manifests, October 16 lightweight closure, and the original June CSV archive.
- Produced a fresh consolidated 85-session/11-source inventory with preserved exact source evidence pointers.
- Identified 39 processor gaps and 13 nonclean current processors.
- **No new historical data acquired or ingested:** current access permits read-only GitHub metadata and this isolated audit branch, but not an authorized target-by-target backend ingest/replay and verified historical engine-consumer write/read. All unverified work is explicitly left OPEN.
- No GitHub Actions dispatch, retries, new model logic, regression suite, prediction production, stable-engine changes, promotion, deletion or merge was performed.
- This is **not a completion certificate**. To finish, execute only the remaining bounded remediation work through an explicitly approved data-ingest path, without touching Austin's work order.

## Low-credit continuation / step estimates

1. [3 steps] Perform one deterministic consumer-path resolution check against existing clean snapshots (read-only), stop if inaccessible.
2. [4 steps per bounded batch] Recover missing current processor snapshots, reusing already retained source rows and loading only actual gaps. Process single-date/event batches; no repeated architectural audits.
3. [3 steps per distinct grid provenance issue] Reconcile FIA authoritative final-grid/revision timing against source data, keeping HOLD where unauthenticated.
4. [2 steps] Validate changed rows/manifests once, compare with the inventory, generate final accepted completion report (no producer forecast/replay).
5. [2 steps] Independent Adviser review of the isolated remediation delta. Merge/promote only if separately authorized and accepted.

**Stop conditions:** any ambiguous source identity, temporal contradiction, unauthorized main/prospective workflow mutation or reliance on unsupported provider revision claims must HOLD only that segment. Issue #309 remains untouched and due only after its October 23 time gate.

**Supporting artifacts:** [audit/2026-10-17/F1_2026_SESSION_COVERAGE.csv](https://github.com/F1Lllewellyn/f1-data-publisher/blob/audit/2026-10-17-historical-session-reconciliation-01/audit/2026-10-17/F1_2026_SESSION_COVERAGE.csv), [audit/2026-10-17/F1_2026_DATA_GAPS.csv](https://github.com/F1Lllewellyn/f1-data-publisher/blob/audit/2026-10-17-historical-session-reconciliation-01/audit/2026-10-17/F1_2026_DATA_GAPS.csv) and five immutable JSON staging evidence parts in this branch.

This file is the one audit report, not a declaration that the user's historical data completion request is finished.
