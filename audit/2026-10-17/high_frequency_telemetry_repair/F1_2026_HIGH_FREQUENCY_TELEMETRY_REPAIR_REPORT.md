# F1 2026 high-frequency telemetry repair — 18 October 2026

**Terminal result: COMPLETE FOR THE AUTHORIZED 85-SESSION TELEMETRY SCOPE.** The country-name selector defect remains corrected, the five meeting-1308 sessions remain hash-verified, Netherlands Race session 11353 is recovered for all 22 historically verified participants, and the production 30-second feature builder now fails closed on undefined or out-of-contract control signals. No protected production system was changed.

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
- The documented OpenF1 analytical domains are enforced without changing raw bytes: throttle 0–100, brake 0/100, and integer gear 0–8.
- Out-of-contract or unavailable readings become missing only in derived calculations; they are not clamped, interpolated, or converted to normal readings.
- Undefined inputs cannot create anomaly flags, thermal load, efficiency loss, or a reliability score.
- Bucket outputs include explicit valid-sample counts, and all-missing anomaly counts remain undefined rather than zero.
- The risk consumer ranks only defined values and omits an entirely undefined driver/session rather than assigning zero risk.
- Existing non-zero calculations retain their prior normalization.
- Risk coefficients and the stable engine are unchanged.

Ten focused offline tests pass: four selector/allowlist tests plus zero-RPM, valid efficiency, invalid-control, missing-brake, valid-boundary and undefined-risk regressions. The invalid-control test also verifies that the source Parquet hash is unchanged after feature generation.

## Independent signal-quality evidence

The retained independent QA package was used without any provider request. Its SHA-256 is `7ad312acf8f2ae19c98bfe25a2e597f60f5d458edf85887a24ebf272b2a37f54`; the contained JSON evidence SHA-256 is `6eb84ec1770f88d0f1915835a54edf1c9c938484f22ecd117926e47f23c469cc`.

The QA evidence references the OpenF1 `car_data` contract and confirms the following source domains: throttle is an integer percentage from 0 through 100, brake is 0 or 100, and `n_gear` is an integer from 0 through 8. Against those domains, Netherlands session 11353 contains:

| Derived-invalid channel | Raw observations retained |
|---|---:|
| throttle = 104 | 97,054 |
| brake = 104 | 97,622 |
| n_gear outside 0–8 | 82 |

These values are preserved as original source evidence. The correction changes only their analytical interpretation.

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

The production feature path was run offline before and after the signal-validity correction over all five meeting-1308 sessions plus Netherlands Race:

- 132/132 driver-session feature builds succeeded.
- Feature row identity is unchanged: 33,506 before and 33,506 after, with a one-to-one match on session, driver and 30-second bucket.
- Risk output identity is unchanged: 132 driver-session rows before and 132 after.
- 15,881 buckets now have undefined reliability, efficiency-loss and thermal-stress results because their required efficiency input is unavailable; the prior implementation had silently represented that unavailable state as zero risk.
- 5,130 throttle/speed mismatch counts and 22 short-shift counts are newly undefined where required control state is unavailable.
- Among still-defined values, 2,287 reliability means, 91 reliability maxima, 1,997 thermal means, 118 thermal maxima, 51 short-shift counts, 28 mismatch counts and 8 efficiency-loss counts changed after invalid readings were excluded.
- All 132 retained driver-session risk values changed and decreased; none increased. The mean absolute change is 0.0309699902 and the maximum is 0.1412385354. This is a correction of prior missing-as-zero/ranking behavior, not evidence of improved prediction accuracy.
- The prior per-session feature counts remain unchanged for sessions 11727–11731; Netherlands adds 8,272 rows.

Evidence hashes:

- Five-session extraction manifest: 96a18997568ecb2d3aaba7a3fe9e1c520512e686d1dad12c4a8e3797ab827141.
- Before feature mart: e45902f0d85f61682b738367d9b59b64b7f940fd51d672f4e79dd2c207da94c4.
- Before risk scores: 0ddebf625c6ab24e5bf857cb9f87ed086474de444e8c63e72e6a871282f56454.
- After signal-validated feature mart: fe5bb6a645105e4d5d770c38dedd94b5ad492ed1174fd06862f5be54d995ad25.
- After signal-validated risk scores: 6d824bd406058443fc63b2ddebce829129e98372f80cf176118a29d750501084.
- After driver-session manifest: 97111782f8f2f0ef4fc7cb49c4ab7938e653b26e991993a090290df38f7b1d28.
- Before/after summary: 25b98bd46a8554b81ac9c9219ab3d412e887f003d6dae682bb35e9c42eb17d3a.
- Durable signal-quality validation bundle: `libfile_4df223e2446c819191d404eb393e1d96`, SHA-256 `3e8c531aef78ef475ed6d47118aa36403d4d510cb622bf2be6d47766c6441b29`.

Reader/consumer status:

- **Raw historical reader:** PASS for all 132 recovered driver-session pairs and 264 endpoint combinations.
- **Production 30-second feature generator:** PASS for 132/132 driver-session pairs with explicit validity accounting.
- **Reliability-risk consumer:** PASS for 132 driver-session outputs; no undefined bucket was converted to zero risk.
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
