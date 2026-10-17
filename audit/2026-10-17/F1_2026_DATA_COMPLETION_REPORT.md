# F1 2026 historical session & race data completion — 17 October 2026

**Disposition: PARTIAL / HOLD; not 100% complete.** The 39 missing processor snapshots were recovered, but 24 sessions retain evidence-backed review holds. Issue #309 and Austin's prospective workflow were not changed or dispatched.

## Result

| Measure | Verified result |
|---|---:|
| Officially completed Grands Prix through 17 October | 17 |
| Expected completed sessions | 85 |
| Fully source-verified sessions | 61 |
| Sessions still requiring review | 24 |
| Sessions missing required retrieved data | 0 |
| Sessions successfully resolved by the existing engine-facing reader | 85 |
| Source files parsed and row-count checked | 935 |
| Source rows parsed by the reader check | 538,111 |

Every expected session now has a retained processor manifest: 46 pre-existing and 39 isolated recovery manifests. The accepted aggregation-v2 policy reclassifies Barcelona FP2 (session 11301) as `clean / usable_with_optional_context_gaps`; its four required sources remain unchanged and clean.

## Bounded recovery

- Direct provider: only `https://api.openf1.org/v1/`, enforced by the recovery wrapper allowlist.
- Batches: 24 terminal receipts; no batch exceeded four sessions or eight provider GETs.
- Provider requests: 125, all HTTP 200, no automatic retry. Endpoint counts: {"drivers": 17, "laps": 39, "position": 21, "race_control": 5, "session_result": 20, "starting_grid": 5, "weather": 18}.
- Newly retrieved provider rows: 40,034. Existing retained OpenF1 rows were reused before retrieval.
- Recovered session results: 27 clean and 12 review-required. The five initially absent Race/Sprint grids were fetched once each from their exact qualifying source session after a confirmed wrapper defect was repaired; no completed lane was downloaded again.
- Review package: `audit/2026-10-17/recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz`. Extracting it at repository root restores `audit/2026-10-17/recovery/processor_outputs/`, including response hashes, observation timestamps, per-session raw rows, validations, manifests, checkpoint and batch receipts.

## Validation and accessibility

The existing `f1_1b_output_contract_v16` reader loaded all 85 manifests and all 935 referenced JSON sources. Every raw list length matched its manifest row count; no session identity or path resolution failed. This proves repository reader accessibility only. It is not a model run, accuracy backtest, forecast, promotion, or stable-engine execution.

## Remaining holds

- 23 Race/Sprint sessions retain `openf1_starting_grid` review because post-event OpenF1 rows do not authenticate the official FIA final grid or establish revision timing. Singapore remains included in this HOLD group.
- One recovered Practice 1 session retains required-source duplicate-row anomalies in position/weather and is not force-cleaned.
- No required retrieved lane is missing, but the 24 review holds prevent a 100% completion claim. `F1_2026_DATA_GAPS.csv` lists the precise evidence and smallest safe remedy for each.

## Scientific and operational boundaries

All new observations are post-event historical recovery. They do not prove pre-race availability for earlier races and cannot be promoted as contemporaneous forecast evidence. No FIA PDF was downloaded, no alternate provider or scraper was used, no workflow was dispatched, no producer/model/backtest ran, no canonical workbook or stable engine changed, and DR-002 remains proposed—not activated.

## Evidence

- `audit/2026-10-17/F1_2026_SESSION_COVERAGE.csv` — 935 event/session/source rows.
- `audit/2026-10-17/F1_2026_DATA_GAPS.csv` — 24 unresolved HOLD sessions only.
- `audit/2026-10-17/F1_2026_HISTORICAL_RECOVERY_VALIDATION.json` — request, checkpoint, reader and output hashes.
- `audit/2026-10-17/recovery/F1_2026_HISTORICAL_RECOVERY_EVIDENCE_2026-10-17.tar.gz` — lossless extracted evidence tree; terminal checkpoint is 39 attempted, 39 processed, zero failed.
