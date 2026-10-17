# F1 2026 historical testing and scientific backtest — 17 October 2026

**Terminal result: PHASE 1 PASS / PHASE 2 HOLD.** The isolated historical environment is complete and readable, but the saved experimental producer inputs do not satisfy event-isolated, immutable source binding. A comprehensive scientific walk-forward was therefore not executed and no retrospective accuracy claim is made.

## Historical environment

| Check | Result |
|---|---:|
| Completed events | 17 |
| Expected sessions | 85 |
| Required-source clean sessions | 85 |
| Original source files parsed | 935 |
| Original source rows parsed | 538,111 |
| Optional partial source records | 159 |
| FIA final-grid overlays consumed | 23 |
| Miami corrected analytical views consumed | 2 |
| Reader or consumer failures | 0 |

All 159 partial records are optional and remain explicitly partial: {'intervals': 67, 'pit': 33, 'race_control': 14, 'session_result': 19, 'starting_grid': 5, 'stints': 21}. They are not silently promoted to observed data.

## Scientific backtest gate

| Measure | Result |
|---|---:|
| Archived experimental bundles audited | 195 |
| Saved pre-race prediction-gate bundles | 130 |
| Exact 22-driver pre-race bundles | 4 |
| Events represented by those exact bundles | 2 |
| Event-scoped, hash-bound eligible cutoffs | 0 |
| Scientifically eligible events | 0 |

The four exact saved outputs are from Belgium and Hungary at pre-weekend and post-qualifying gates. Their output bytes are Git-timestamped before each race and bind exactly to the locker source hash, but their producer manifests point to season-wide source tables and record only mutable paths and row counts. This violates the required event-isolation and immutable-input gates.

## Diagnostic-only results

The four saved outputs were scored only to preserve all usable evidence. These figures are **not** a valid model-accuracy or calibration claim:

- Mean model finishing-order MAE: 3.340909; simple team-prior MAE: 4.772727.
- Mean model Spearman rho: 0.701299; team-prior rho: 0.517222.
- Mean podium overlap: 0.75; top-10 overlap: 0.775.
- Mean non-finish Brier score: 0.122061.
- Retrospective final-grid MAE: 2.681818; it is not cutoff-eligible because the official grids postdate the saved cutoffs and were first observed post-event.

## Weaknesses and smallest safe remedies

1. **Event scope and immutable provenance:** freeze every actual producer input by event/session/cutoff and hash it into the bundle.
2. **Participant contamination:** enforce the exact target-event entry before producing rows; 126 of 130 saved pre-race bundles fail this today.
3. **Probability persistence:** carry win, podium and top-10 probabilities through locking before calibration analysis.
4. **Feature attribution:** energy deployment, harvesting, battery and traffic currently affect readiness only; add numeric features only after prospective cutoff-safe evidence exists.
5. **Sample size:** accumulate independently locked prospective races before tuning or promotion.

No DRS assumption was introduced. No provider request, workflow dispatch, producer/model execution, stable-engine or workbook change, production archive mutation, prediction publication, DR-002 activation, merge or promotion occurred. Issue #309 remains unchanged.
