# DR-002 pre-2B-7G2 — Protected stable historical-artifact custody

Work order: [Issue #165](https://github.com/F1Lllewellyn/f1-data-publisher/issues/165), `F1-WO-DR002-PRE2B7G2-001`.

Assessment baseline: `b11f2975ddb6f8cb025969dab611b6852c3175bc`, the accepted PR #163 merge. Handoff contract Git blob: `85ce44807ef159b5ba5d3bfd543ea1f945097f77`. Accepted predecessor checkpoint Git blob: `a7f5d9368d3a6fbb5652dd915e1c667f62a0bc53`, [pre-2B-7G1](DR002_PRE2B7G1_STABLE_ENGINE_EXECUTION_SURFACE_2026-10-05.md).

**Finding: route E.** Both exact historical workbooks are recoverable and verified. The protected v17 forecast core is recorded as stored forecast values with analyst reasoning and contextual rules; the recovered package does not expose a self-contained deterministic primary forecast executable. Preserve the historical baseline. A later, separately authorized change should correct generic-producer metadata/provenance that implies execution of `Engine_2026-06-07_STABLE`. No route is implemented here.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate OFF. Promotion NOT ALLOWED.

## Exact custody and method

Exact-filename retrieval returned the following Library objects. Raw downloaded bytes independently matched both work-order size/hash pairs. No later version, reconstruction, search summary or rendered workbook was substituted.

| Artifact | Exact filename | Library object | Bytes | Sheets | Formula cells |
| --- | --- | --- | ---: | ---: | ---: |
| v17 | `F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v17_backtest_calibrated.xlsx` | `libfile_62ece5aa55a88191b3256834f7c1eca9` | 385753 | 110 | 475 |
| v25 | `F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v25_v17_core_density_restored.xlsx` | `libfile_9b21d90d16708191a0fb386368de6ca5` | 402284 | 120 | 475 |

v17 raw SHA-256: `6db052abfc587f1c44fb1b879497880aaea9d9e9eafdf0eb5f6e20825edb3192`.

v25 raw SHA-256: `b66bbf814fad79b985a4532059435809c0a96664aa2afb257428672a07ceb83e`.

The read-only inspection used Python standard-library ZIP and XML parsing. Worksheet names were resolved through `xl/workbook.xml` and `xl/_rels/workbook.xml.rels`; cell values and formula text came from the mapped worksheet XML, resolving string storage where needed. Formula counts count cells containing an XML `<f>` element, including formulas returning literal labels. All 110/120 worksheets were inventoried, not only the required subset. All 475 formula cells in each package have ordinary formula elements without shared-formula attributes. ZIP integrity checks passed and package entry names were unique.

No workbook was modified, normalized, opened in Excel/LibreOffice, recalculated, saved or resaved. No formula was evaluated and no cached value was treated as independent execution evidence. Raw size/SHA-256 checks before inspection, after inspection and at final report preparation matched the values above. Only this Markdown checkpoint is included in the repository delta.

Neither package contains VBA-project, macrosheet, external-link, connection, query-table or embedded-object parts; neither declares defined names. These package observations support the bounded conclusion about the recovered artifacts, not a claim that no external/manual process ever existed.

## Required v17 surfaces

The following counts were independently observed in both packages. XML locators below are the v17 worksheet parts.

| Sheet | Formula cells | XML part | Content role |
| --- | ---: | --- | --- |
| Predictions | 0 | `xl/worksheets/sheet21.xml` | Stored forecast positions, drivers, probabilities and explanatory reasons. |
| Model Weights | 0 | `xl/worksheets/sheet26.xml` | Stored feature/track/adaptive weights and notes. |
| Race Type Templates | 0 | `xl/worksheets/sheet30.xml` | Stored track-profile weights, risks and checklists. |
| Prediction Scorecard | 285 | `xl/worksheets/sheet28.xml` | Compares entered forecasts with entered outcomes; hit/partial/miss, scores and Brier terms. |
| Probability Scoring v7 | 7 | `xl/worksheets/sheet51.xml` | Brier terms from stored probability/outcome values. |
| Monte Carlo Simulator v7 | 0 | `xl/worksheets/sheet55.xml` | Stored ranks, probabilities, risk values and explanatory reasons; no sampling calculation. |
| Monte Carlo Inputs Live | 0 | `xl/worksheets/sheet69.xml` | Stored input/readiness/source descriptions; no executable source-ingestion entry. |
| Monte Carlo Race Output | 0 | `xl/worksheets/sheet70.xml` | Stored forecast ranks, probabilities and risks. |
| Backtest Summary v17 | 10 | `xl/worksheets/sheet103.xml` | Aggregation of already-entered accuracy metrics. |
| Accuracy Metrics v17 | 12 | `xl/worksheets/sheet105.xml` | Stored per-race metrics plus aggregation and two formula label cells. |
| Calibration Learnings v17 | 0 | `xl/worksheets/sheet108.xml` | Narrative observations and recommendations. |
| Weight Updates v17 | 0 | `xl/worksheets/sheet109.xml` | Narrative weight-update recommendations, not a parameter-application chain. |

### Exact representative cells and calculation direction

- `Predictions!F5:G5:H5` stores position `1`, `Kimi Antonelli`, probability `0.3`; `D5` says `Backtest after model upgrades`. `F10:G10:H10` stores `1`, `Kimi Antonelli`, `0.48`; `D10` says `Pre-race baseline after qualifying`. Column J contains textual race/weekend reasons. These forecast cells have no formulas.
- `Model Weights!B5` is `0.25` and `G5` is `0.2`; the feature is `Car/chassis pace`. `Race Type Templates` contains static contextual weights. Neither sheet calculates primary forecast outputs.
- `Monte Carlo Simulator v7!D2:E2:F2` stores `1`, `58`, `88`; `J2` contains narrative reasoning. `Monte Carlo Race Output!C3:D3` stores `58`, `88`. The Monte Carlo names and static output rows do not establish a simulation executable.
- `Monte Carlo Inputs Live!A3:C3` stores `True Pace Distribution`, `Jolpica lap KPIs / Team Pace KPIs`, `Available R1–R5` (source/readiness descriptions).
- `Weight Updates v17!D2` recommends keeping a high weight with a `0.52–0.60` range depending on track conversion; `D3` recommends increasing once OpenF1 intervals are available. Neither is an executable update.

Formula text below omits Excel's display-prefix `=`; the text is taken from raw XML.

| Cell | Exact formula text | Direction |
| --- | --- | --- |
| Prediction Scorecard!J3 | `IF(OR(G3="",H3=""),"",IF(G3=H3,"Hit",IF(ISNUMBER(SEARCH(H3,G3)),"Partial","Miss")))` | Entered prediction G and actual H → assessment |
| Prediction Scorecard!K3 | `IF(J3="","",IF(J3="Hit",1,IF(J3="Partial",0.5,0)))` | Hit category → score |
| Prediction Scorecard!L3 | `IF(I3="","",(I3/100-IF(J3="Hit",1,0))^2)` | Entered probability I and assessment → Brier term |
| Probability Scoring v7!H2 | `(F2/100-G2)^2` | Entered probability/outcome → Brier term |
| Probability Scoring v7!H6 | `IF(ISNUMBER(G6),(F6/100-G6)^2,"")` | Same, guarded for pending outcome |
| Backtest Summary v17!B8 | `AVERAGEIF('Accuracy Metrics v17'!C:C,"Baseline pre-race",'Accuracy Metrics v17'!D:D)` | Existing metrics → summary |
| Accuracy Metrics v17!D15 | `AVERAGEIF(C:C,"Baseline pre-race",D:D)` | Existing race metrics → aggregate |

The scorecard has 95 formula cells in each of J/K/L, totaling 285. None calculates its forecast or probability inputs. Accuracy Metrics has ten metric aggregation cells plus two formula cells returning the labels `"Baseline pre-race"` and `"Post-DNS update"`; twelve formulas do not mean twelve forecast-generation cells.

### Complete formula inventory

All formula-bearing sheets are listed below. Their counts account for all 475 formula cells in each workbook; the other 101/111 sheets contain none.

| Sheet | Count | Formula function / scope |
| --- | ---: | --- |
| Dashboard | 7 | COUNTA log/prediction counts and averages of Calibration errors |
| Calibration | 42 | Equality, absolute rank error and top-ten outcome checks |
| Prediction Scorecard | 285 | Forecast scoring and audit |
| Lap Data 2026 | 73 | Stored lap-time text → seconds |
| Probability Scoring v7 | 7 | Outcome/Brier scoring |
| Lap-Time Forecasts v7 | 15 | ABS of stored predicted/actual times and ranks |
| Elevation Air Density v16 | 24 | Pressure, air density and relative density calculations |
| Backtest Summary v17 | 10 | Accuracy aggregation |
| Accuracy Metrics v17 | 12 | Ten aggregates and two label formulas |
| **Total** | **475** | **No primary race/qualifying generation chain** |

The auxiliary environmental calculations are real deterministic formulas: `Elevation Air Density v16!D9` is `1013.25*(1-2.25577E-5*B9)^5.25588`, `E9` is `D9*100/(287.05*(C9+273.15))`, and `F9` is `E9/1.225*100`. These repeat through row 16. They calculate environmental quantities; no formula chain connects them to primary forecast positions/probabilities. The sheet explicitly describes a modifier rather than a standalone pace predictor.

`Lap-Time Forecasts v7!L2` is `ABS(E2-I2)` and `M2` is `ABS(D2-H2)`; predicted time/rank inputs are stored values. Thus the package contains auxiliary transforms as well as evaluation/reporting formulas. Their presence does not supply a frozen-evidence → primary forecast entry point.

## v24/v25 identity evidence

The exact v25 package contains the v24 reset/workflow documentation and four v25 density sheets. The ten sheets added relative to v17 contain zero formula cells.

The following are exact stored-cell declarations, not independently authenticated historical clock records or new performance proofs:

| v25 sheet / cell | Exact stored content |
| --- | --- |
| v24 Operational Reset!B2 | 2026-06-07 06:29 UTC |
| v24 Operational Reset!B3 | Use v17 as the current operational prediction engine because later practical formulas did not consistently beat it on race-specific predictions. |
| v24 Operational Reset!B4 | v18–v23 added valuable data and experimental logic, but some versions over-averaged and diluted the race-by-race driver × track × car × weekend reasoning that made v17 sharper. |
| v24 Operational Reset!B5 | New data is advisory until it passes a promotion test against v17. Bulk data must support race-specific reasoning, not replace it. |
| v24 Operational Reset!B6 | Use this v24 workbook as the operational model. Keep v18–v23 as experimental/data-learning history, not as the default practical forecast engine. |
| v24 Operational Reset!A9 | v17 race/qualifying core |
| v24 Operational Reset!B9 | Canonical operational |
| v24 Operational Reset!C9 | Primary forecasts |
| v25 Density Operational!B2 | 2026-06-07 06:34 UTC |
| v25 Density Operational!B3 | The elevation / air-density framework from v16 is present in the v24 lineage because v17 was built on top of v16. v24 restored v17 as the operational core, so the layer exists but was treated as a learning/advisory layer rather than an active operational modifier. |
| v25 Density Operational!B4 | Restore altitude/elevation/barometric pressure as a race-specific operational context factor, but with v24 guardrails: it can change the forecast only when the track/weekend activates it and the direction is explainable. |
| v25 Density Operational!B6 | Do not apply density as a generic pace correction. It must be activated by circuit profile: high altitude, low pressure, heat, cooling-limited tracks, heavy braking, or open/drag-sensitive layouts. |

The reset's A9/B9/C9 row explicitly binds the v17 race/qualifying core to canonical operational primary forecasts. The stored v24 Data Guardrails, Candidate Promotion, Monaco Lesson and Race Weekend Workflow sheets reinforce advisory overlays and promotion tests, rather than automatic replacement of v17. Density restoration adds race-specific, explainable context under those guards; it does not add an executable primary forecast chain.

### Byte identity of four carried-forward sheets

Comparison used the original uncompressed worksheet XML bytes, without XML canonicalization or rewriting. Both packages map each sheet below to the same part, and byte comparison was equal.

| Sheet | XML part in both packages | SHA-256 of identical XML bytes |
| --- | --- | --- |
| Backtest Summary v17 | `xl/worksheets/sheet103.xml` | `e7415b1f589ec82614d5173a8da510c9dbf5a0eae25d479dc6fc8043a554af5e` |
| Accuracy Metrics v17 | `xl/worksheets/sheet105.xml` | `f9d8f13ee590c69116ebf928fb6f23060c197b908582cbe053a72d98ee316957` |
| Calibration Learnings v17 | `xl/worksheets/sheet108.xml` | `bfeca78b7d93b68ec13e19a50efa976fbf86f59040edbccd32fd25d294f9e7e5` |
| Weight Updates v17 | `xl/worksheets/sheet109.xml` | `253050545b4c5460e2e2dbcbcbdcb8738d1bff10f72820a66e98d19addd7d32c` |

This is a four-sheet identity claim, not whole-workbook byte identity. The other eight required surfaces have different XML hashes between packages despite unchanged formula counts. No preservation claim for their full XML bytes is made.

## Scientific classification

| Question | Answer | Basis and limit |
| --- | --- | --- |
| Exact v17 recoverable? | **yes** | Exact filename, size and raw hash independently verified. |
| Exact historical workbook artifact? | **yes** | Recovered bytes match the designated historical custody identity; embedded dates alone do not prove historical availability. |
| Deterministic executable entry from frozen evidence to primary race/qualifying forecasts without manual forecast entry? | **no** | Complete raw formula inventory exposes no such entry or calculation chain. Forecast-bearing cells are stored values. |
| Materially human-entered / analyst-reasoned primary core? | **yes** | Classification inference from stored forecast outputs, explicit narrative reasons, contextual decision rules and advisory/promotion instructions. This means an analyst-in-loop core; the package does not authenticate which person/tool typed a particular cell or reconstruct the original reasoning session. |
| Unchanged artifact can legitimately satisfy separate Gate 2B-1 engine_execution? | **no** | Custody identifies workbook bytes, not an invocation producing primary forecasts. No deterministic historical engine entry, input-to-output execution or separate engine run is supplied. |
| Translation/reimplementation creates a new implementation identity requiring replay/backtest? | **yes** | Encoding narrative decisions and manual/contextual choices introduces implementation choices absent from the historical calculation surface. New code cannot prove historical execution of the protected engine. |

These answers classify the recovered packages. They do not rule out an unrecovered external reasoning process. No such process is imported into this evidence, and no missing algorithm is invented.

The accepted pre-2B-7G1 checkpoint records Gate 2B-1 verifier blob `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae`: separate engine identity and invocation linkage, code/commit, input manifests, result hash and external proof are required. Hashing this workbook or copying its stored forecasts would prove custody/copying, not that separate engine execution. Existing accepted verifier tests were not rerun for a one-file documentary change.

### Historical scientific ceiling

`Backtest Summary v17!B2` stores `2026-06-07 05:10 UTC`. B3 states exactly:

> Retrospective v16/v17 model reconstruction using currently available 2026 data; not a fully blind pre-season record.

That ceiling is preserved. Entered metrics, scoring formulas and later retrieval do not establish blind pre-race eligibility or independently validated predictive accuracy. v24 claims about outperforming later practical formulas are historical workbook statements, not newly verified performance findings.

## Recommended next route and stopping boundary

**E only:** preserve the verified v17/v25 artifacts as historical baseline evidence. Separately authorize correction of current producer/writer/locker metadata and provenance so a generic producer does not imply execution of `Engine_2026-06-07_STABLE`. Any future code translation requires a distinct implementation identity and separate replay/backtest evidence.

D is unsupported because no deterministic primary forecast entry was recovered. F is unnecessary because exact custody and the complete formula inventory suffice to classify these artifacts. No metadata correction, adapter, translation, prediction, receipt, workflow dispatch, activation or enforcement is performed under this order.

Verification was confined to raw package custody, worksheet/formula inspection, four byte comparisons and the one-file documentation delta. Workbooks remain unchanged and are not committed. No accuracy claim, promotion or successor implementation is authorized by this checkpoint.

## Final checkpoint

```text
v17_raw_artifact_verified: true
v25_raw_artifact_verified: true
v17_primary_forecast_deterministic_executable: false
v17_human_in_loop_forecast_core: true
v17_can_satisfy_separate_engine_execution_receipt_unchanged: false
reimplementation_would_be_new_engine_identity: true
recommended_next_route: E
```
