# F1 2026 high-frequency telemetry repair — 17 October 2026

**Terminal result: TARGETED RECOVERY COMPLETE / SEASON COVERAGE PARTIAL.** The country-name selection defect is corrected and all five authorized meeting-1308 sessions are recovered and hash-verified. The 85-session audit found one pre-existing uncovered session (Netherlands Race, session 11353), so this work does not claim complete season telemetry coverage.

## Scope and result

| Measure | Result |
|---|---:|
| Expected championship sessions | 85 |
| Sessions with driver-level `car_data` and `location` evidence | 84 |
| Missing sessions | 1 |
| Verified driver-session pairs | 1,847 |
| Verified driver/endpoint combinations | 3,694 |
| Accepted original-archive rows | 73,618,175 |
| Newly reconciled five-session rows | 5,660,622 |
| Combined source rows | 79,278,797 |
| Accepted original 30-second feature rows | 7,172 |
| New isolated 30-second feature rows | 25,234 |
| Combined feature rows | 32,406 |

The original 80-session artifact was not re-downloaded or re-extracted. Its accepted validation evidence is GitHub Actions run `38586338521`, final artifact `11916289450`, archive digest `4ca78ad6fbd1af8626429ef50166929c830f2a157520a92df7b92a182462c7dd`, and checkpoint artifact `11916688564`, digest `1d0f0bc81e6dba789757d190e54e6086999e347edff51d7e03f6be21b5ea5880`. The run selected 80 sessions, completed successfully, and reported 73,618,175 extracted rows and 7,172 feature rows.

## Selector correction

The ingest now excludes explicit event identities rather than country names:

- Cancelled meetings: `1282`, `1283`.
- Pre-season tests: `1304`, `1305`.
- October meeting `1308` remains eligible even though its provider country name is Bahrain.
- A bounded session-key allowlist supports recovery without launching another season extraction.
- A zero-retry setting and optional race-ground-truth skip preserve bounded recovery behavior.

Four focused offline tests prove the 85-session selection, meeting-1308 inclusion, exact five-session allowlist, fail-closed missing key handling, and invalid allowlist parsing.

## Durable recovery

Checkpoint 034 (`libfile_6c0ae29e110881918f2e09502c1a4b00`) was materialized and independently reconstructed with checkpoints 000–033. Before any new request, all 170 entries were verified against their raw and Parquet hashes and row counts. They contained 3,062,422 source rows. The remaining 50 combinations contained 2,598,200 rows and were requested once each.

The prior HTTP 502 for session `11728`, driver `27`, `car_data` remains preserved in `failures/ORIGINAL_11728_27_CAR_DATA_HTTP_502_EVIDENCE.json`. Its one separately authorized bounded recovery is present exactly once as `bounded_recovery_after_preserved_http_502_11728_27_car_data`.

Every resumed checkpoint was uploaded to durable storage, materialized back, byte-compared and ZIP-tested before later provider calls. A network-control interruption after combination 188 was captured separately in checkpoint 038 before work continued.

| Checkpoint | Combinations | Library ID | ZIP SHA-256 |
|---|---:|---|---|
| 035 | 171–175 | `libfile_ef386090ba1081919dc88815c871fe1f` | `4aaf0a933c607fa51b553c0afd135ef246933f740ed436441f6637f9ef615145` |
| 036 | 176–180 | `libfile_29e5d94350d881919db8a94a07c48372` | `58bea960f458fb28f0949110bba0dc6c728c633523cf0034696c239d963fb027` |
| 037 | 181–185 | `libfile_683e4c5f71948191bf65da31c1b6dc86` | `6210817b4dfc7f7a92229b0c5b968d19cfce777447d6381432fe526e5a904310` |
| 038 | 186–188 interruption | `libfile_72cd276f0ff88191883b288536c40008` | `7d3e42cfaf533c30e799d52115a981b3b63bc777d3d35311a82a3d80c965c363` |
| 039 | 189–193 | `libfile_b36ba0f474b48191a5e3d68bb0f8cd4c` | `f5a8298171784b3cca7ad2102cc2b9c996f57ffb3a67d54b40337f3723f5fb0b` |
| 040 | 194–198 | `libfile_d3f9617623208191a9277ee98d237d89` | `7b305d3e194c2b3f35745fb4c41a5330f1efc8720a9e5f9dc9cd4f4030bd5eb6` |
| 041 | 199–203 | `libfile_aa18d3654a208191aba99f79afa43ada` | `c1a90075a0859853d56929c1a54bc0d766287e786fa0520a09de3ef0a9ab9dbe` |
| 042 | 204–208 | `libfile_cf876d85fb988191910179b45a8a22f3` | `8b66d4f29d928e6556045fe5caa9c2d5cad37a7368c1897db447ab9491e95b83` |
| 043 | 209–213 | `libfile_32b8767a68fc8191997510f01a57f2f9` | `fd807e8e55c42e74493e70723c52b174e202c81aacc33313652ea2f9b3f2a692` |
| 044 | 214–218 | `libfile_4dcca4e0fe6081919c2bd7af6706afb8` | `0c587b642c8d08426b8ea396020375298399a7e52d6dd330fa3e35635e53ce66` |
| 045 | 219–220 | `libfile_a7aa837a577c819192ddbdd8f7c6c4ba` | `5632de278681c098e838d2a22bf4658161142950d172556d1f669146c38f9c04` |

## Five-session validation

All 220 combinations are unique, complete and HTTP 200, with 110 `car_data` and 110 `location` records. Raw JSON and Parquet hashes and row counts match; every row retains the expected session and driver identity; no exact duplicate rows were found.

| Endpoint | Combinations | Rows | Median interval range | Maximum p95 interval | Exact duplicates |
|---|---:|---:|---:|---:|---:|
| `car_data` | 110 | 2,801,260 | 0.240–0.240 s | 0.440 s | 0 |
| `location` | 110 | 2,859,362 | 0.240–0.241 s | 0.439 s | 0 |

The large maximum gaps (up to 76,017.247 seconds) are retained provider observations inside a session-key response spanning inactive periods; they are not silently interpolated or classified as continuous on-track sampling.

Evidence hashes:

- Extraction manifest: `96a18997568ecb2d3aaba7a3fe9e1c520512e686d1dad12c4a8e3797ab827141`.
- Driver/endpoint validation: `b0c4f664a15e98f21a52cfd6b606fc4a0796a863b61056850f6900e38901f9df`.
- Feature manifest: `17445500364679741356876528c694e0bce4bcb43ae34f41ae6da6cb179cfa04`.
- 30-second feature mart: `722dc177239ece05e9fc6176595ea3eb6542839248c68ae0037720ac9a43adda`.
- Driver-session risk scores: `3d0d13901f190d3bce811ca8112dc96060a8795f97e2f7e5ebdf6392e5c936a7`.
- Validation summary: `a881ea1c1b1ddcd030e8c802156b6b61446952f0525ae59444d29954f667a3ee`.

## Downstream accessibility

- **Raw historical reader:** PASS for all five recovered sessions; all 220 Parquet files load and preserve source identity.
- **30-second feature generation:** PASS in an isolated adapter for 110/110 driver-session pairs and 25,234 buckets.
- **Risk consumer:** PASS; `compute_driver_session_risk` produced 110 driver-session rows.
- **Reporting consumer:** PASS through an isolated read-only compatibility view mapping recovery `row_count` to the existing report reader's `rows` field.
- **Fantasy consumer:** HOLD. The repository declares fantasy/reporting authority but contains no dedicated fantasy reader that can be exercised against this feature mart.

The production feature builder has a confirmed zero-denominator defect: gear 0 maps to an efficiency baseline of zero and raises `ZeroDivisionError` for 107/110 recovered driver sessions under pandas 3.0.6. The isolated adapter treats only that zero denominator as undefined (`NaN`) and retains every raw observation. The production implementation was not expanded in this PR; therefore production feature accessibility remains partial even though the isolated derived output is valid.

## 85-session audit and remaining gaps

The accepted original extraction selected 80 sessions, but selection was not equivalent to driver-level coverage. Its log shows session `11353` (Netherlands Race) ran both endpoints with zero drivers. Independent historical evidence on PR #310 confirms 22 participants for that race, so this is a real missing high-frequency session, not a legitimate zero-participant case. Barcelona Practice 1 (`11300`) has 21 drivers in both the extraction log and accepted session source and remains verified.

Accordingly:

- 84 sessions are source-verified at the driver telemetry layer.
- 1 session is missing required high-frequency data: `11353`.
- All five meeting-1308 sessions are fully recovered.
- Smallest safe remedy: a separately authorized two-endpoint, 22-driver recovery for session `11353`, followed by the same hash/identity and isolated feature checks.
- A separate narrow code repair is required before the production 30-second generator can claim full consumer accessibility.

The exact per-session disposition is in `F1_2026_HIGH_FREQUENCY_TELEMETRY_COVERAGE.csv`. Blank original-archive per-session row counts are deliberate: the accepted 603 MB artifact was not re-downloaded merely to restate data that was not available in run metadata.

## Protection statement

No full historical extraction, FIA/grid reconciliation, historical backtest, workflow dispatch, stable-engine execution, forecast publication or DR-002 activation occurred. Issue #309, PRs #310/#311, the original 80-session artifacts, production workflows, canonical workbook, `Engine_2026-06-07_STABLE`, and DR-002 remain unchanged.
