# F1 2026 high-frequency telemetry repair — 18 October 2026

**Terminal result: COMPLETE FOR THE AUTHORIZED 85-SESSION TELEMETRY SCOPE.** The country-name selector defect remains corrected, the five meeting-1308 sessions remain hash-verified, Netherlands Race session 11353 is recovered for all 22 historically verified participants, and the production 30-second feature builder now treats undefined efficiency ratios as missing values. No protected production system was changed.

## Scope and result

| Measure | Result |
|---|---:|
| Expected championship sessions | 85 |
| Sessions with driver-level car_data and location evidence | 85 |
| Missing sessions | 0 |
| Verified driver-session pairs | 1,869 |
| Verified driver/endpoint combinations | 3,738 |
| Accepted original-archive rows | 73,618,175 |
| Five meeting-1308 recovery rows | 5,660,622 |
| Netherlands Race recovery rows | 1,872,750 |
| Combined source rows | 81,151,547 |
| Accepted original 30-second feature rows | 7,172 |
| Six recovered-session production feature rows | 33,506 |
| Combined feature rows | 40,678 |

The original 80-session artifact was not re-downloaded, re-extracted or modified. Its accepted evidence remains GitHub Actions run 38586338521, final artifact 11916289450 with digest 4ca78ad6fbd1af8626429ef50166929c830f2a157520a92df7b92a182462c7dd, and checkpoint artifact 11916688564 with digest 1d0f0bc81e6dba789757d190e54e6086999e347edff51d7e03f6be21b5ea5880.

## Corrective implementation

The session selector excludes event identities rather than country names:

- Cancelled meetings: 1282 and 1283.
- Pre-season tests: 1304 and 1305.
- October meeting 1308 remains eligible.
- The bounded session-key allowlist, zero-retry setting and race-ground-truth skip remain available for isolated recovery.

The production feature correction is intentionally narrow:

- Zero RPM remains in the source observations.
- Speed/RPM ratios with a zero denominator are derived as missing, not zero performance.
- A zero or non-finite gear baseline is also derived as missing.
- Undefined ratios cannot create an efficiency-loss flag.
- Existing non-zero calculations retain their prior normalization.
- Risk coefficients and the stable engine are unchanged.

Six focused offline tests pass: four selector/allowlist tests plus gear-0/zero-RPM and valid non-zero efficiency regressions.

## Durable Netherlands recovery

The empty drivers response in the original extraction was not treated as proof of zero participation. The accepted historical record on PR #310 identifies 22 participants for meeting 1292, session 11353: 1, 3, 5, 10, 11, 12, 14, 16, 18, 22, 23, 27, 30, 31, 41, 43, 44, 55, 63, 77, 81 and 87.

Before retrieval, checkpoint persistence was proved by remote write, materialization and byte comparison. Checkpoints 046–049 were then reconstructed from durable storage; all first 20 manifest entries and referenced raw/Parquet files revalidated by SHA-256. Only combinations 21–44 were subsequently requested.

Each immutable checkpoint was materialized back and compared byte-for-byte before later requests:

| Checkpoint | Combinations | Library ID | ZIP SHA-256 |
|---|---:|---|---|
| 046 | 1–5 | libfile_3fbbc2da207c819187cdbe0a886643d6 | 2a50c986837dcebcbadcba6448eb4aedd4442fd1dbb4283f748666fce47dad27 |
| 047 | 6–10 | libfile_4af8ac57dccc81918e76ceeb520eafe4 | 446090afe869ac3719cdd7cd45dec9fc9b4da500f66ac0260f5c73adcf61020c |
| 048 | 11–15 | libfile_118514b0324081918ee8a1ed25dde832 | b5a60f71d4c963804a568a4eadea6013bc85e46bdad05137dc7329ed19c666f2 |
| 049 | 16–20 | libfile_dd40e76b6b488191b33164048bc8cc7c | 2a43cd2150c0bc098c29f7a3c1bf986445ed58b2bfed3d3ba5924950a5643dd2 |
| 050 | 21–25 | libfile_4c3d8867ea188191b96dfdc57ea01332 | da528c0ba0549b9139acdfee21fe1de236d9f8f30f09541d6df87c8a9986aaf6 |
| 051 | 26–30 | libfile_5008c4f5b534819189c232945b31d5c7 | 0bc295e4a183b45ce633b6b81ceccf06d20026eac86cbd3ea3c1711a0d76d2e6 |
| 052 | 31–35 | libfile_fe91a8e30cb48191ac06155df0cee837 | 0b5cac7b3435cf5d45181430ca760e5b4f66abed16c923005cdbc3013ee49255 |
| 053 | 36–40 | libfile_dd91d9a032c48191a7b14ebe07304dc9 | da95b7adef1fc81d4c2bf2e9fa76f7bc24caaf4f73449c441e2a299772a1a8fa |
| 054 | 41–44 final | libfile_2ecdb6742ba8819185bdbd0f0ce3667b | 41a80f9cca55f05b56862760ce586caad06466ae54aed04c81d5d96e1329add6 |

All 44 combinations are unique, complete and HTTP 200. Raw JSON and Parquet hashes, row counts, session identity and driver identity match the cumulative manifest; exact duplicate count is zero.

| Endpoint | Drivers | Rows | Earliest retained timestamp | Latest retained timestamp | Exact duplicates |
|---|---:|---:|---|---|---:|
| car_data | 22 | 942,040 | 2026-08-22T15:00:32.024Z | 2026-08-23T15:13:39.381Z | 0 |
| location | 22 | 930,710 | 2026-08-22T15:00:50.399Z | 2026-08-23T15:13:58.842Z | 0 |

The session-key responses span inactive periods; those provider timestamps are retained and are not represented as continuous on-track sampling.

Netherlands cumulative extraction manifest SHA-256: ddf16a608b1f41b7ea59e214ebcf1f861a7e6accb50bb30ce34cd74b2f51286b.

## Production feature and consumer validation

The unchanged production feature path was run offline over all five meeting-1308 sessions plus Netherlands Race:

- 132/132 driver-session feature builds succeeded.
- 33,506 30-second feature rows were produced.
- 132 driver-session risk rows were produced by compute_driver_session_risk.
- 15,881 buckets have an undefined efficiency mean and remain explicitly missing.
- No negative efficiency-loss counts or undefined-ratio false flags were observed.
- The prior per-session feature counts remain unchanged for sessions 11727–11731; Netherlands adds 8,272 rows.

Evidence hashes:

- Five-session extraction manifest: 96a18997568ecb2d3aaba7a3fe9e1c520512e686d1dad12c4a8e3797ab827141.
- Six-session feature manifest: bc87e9488ffbc748dbd8919c204a355241ff37371c785ed66781ae04a8aead79.
- Six-session production feature mart: e45902f0d85f61682b738367d9b59b64b7f940fd51d672f4e79dd2c207da94c4.
- Six-session driver-session risk scores: 0ddebf625c6ab24e5bf857cb9f87ed086474de444e8c63e72e6a871282f56454.

Reader/consumer status:

- **Raw historical reader:** PASS for all 132 recovered driver-session pairs and 264 endpoint combinations.
- **Production 30-second feature generator:** PASS for 132/132 driver-session pairs.
- **Reliability-risk consumer:** PASS for 132 driver-session outputs.
- **Reporting compatibility:** PASS using the existing read-only manifest-field compatibility mapping.
- **Fantasy consumer:** HOLD; the repository still declares fantasy authority but has no dedicated fantasy reader to exercise. This does not reduce source or production-feature coverage.

## 85-session coverage conclusion

The accepted original extraction selected 80 sessions but returned zero participants for Netherlands Race. The isolated Netherlands recovery closes that real gap without changing the original archive. Combined with the five meeting-1308 sessions:

- 85/85 expected championship sessions now have driver-level car_data and location evidence.
- 1,869 driver-session pairs and 3,738 endpoint combinations are accounted for.
- No required high-frequency session remains missing.
- This is a telemetry-source and feature-accessibility conclusion, not a retrospective prediction-provenance or forecast-readiness claim.

The exact per-session disposition is recorded in F1_2026_HIGH_FREQUENCY_TELEMETRY_COVERAGE.csv. Original-archive per-session row counts remain blank where the accepted run metadata did not expose them; the 603 MB artifact was not re-downloaded merely to restate unavailable per-session detail.

## Protection statement

No full historical extraction, FIA/grid reconciliation, historical backtest, workflow dispatch, stable-engine execution, forecast publication or DR-002 activation occurred. Issue #309, PRs #310/#311, the original 80-session artifacts, production workflows, canonical workbook, production forecasts, Engine_2026-06-07_STABLE, and DR-002 remain unchanged.
