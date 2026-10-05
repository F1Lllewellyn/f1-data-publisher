# DR-002 pre-2B-7G3 — Stable-lane metadata truth

Work order: [Issue #168](https://github.com/F1Lllewellyn/f1-data-publisher/issues/168), `F1-WO-DR002-PRE2B7G3-001`.

Implementation baseline: `cc46daa45824444524c3f580bb3b95dfc2f99754`.
Accepted scientific basis: [pre-2B-7G2 historical-artifact custody](DR002_PRE2B7G2_STABLE_HISTORICAL_ARTIFACT_CUSTODY_2026-10-05.md), Git blob `a9cc4718f4a58e211b6bcaf14cfc17dd78b03f6b`.
Handoff contract Git blob: `85ce44807ef159b5ba5d3bfd543ea1f945097f77`.

## Result

The live `stable_baseline` lane now carries the configuration label `StableBaseline_LanePolicy_v1`. The writer and locker no longer map that lane to the protected historical identity `Engine_2026-06-07_STABLE`.

The new label identifies the current lane policy only. It does not assert a historical engine implementation, invocation, or execution proof. The current generic producer retains its own implementation identity. The protected v17/v24 workbook remains historical evidence under the accepted pre-2B-7G2 classification.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate OFF. Promotion NOT ALLOWED.

## Exact behavior

### Source-row writer

`write_gate_forecast_rows_v1.py` keeps the lane name `stable_baseline` and always writes `StableBaseline_LanePolicy_v1` for its `engine_lane_config`. This fail-closed assignment replaces an incoming stale `Engine_2026-06-07_STABLE` value rather than propagating it.

Each normalized stable row appends:

> stable_baseline is a lane/policy label; no separate protected stable-engine execution is claimed.

The existing normalization note and `promotion_gate_eligible=False` behavior remain. Control-room and experimental writer mappings are unchanged, including the existing rule that a non-empty incoming non-stable configuration is preserved.

### Bundle locker

`create_forecast_bundles_v1.py` writes `StableBaseline_LanePolicy_v1` into stable bundle rows, the bundle lock manifest, and `engine_lane_config.json`.

`engine_lane_config.json` preserves its existing fields and now records:

```json
{
  "stable_engine_execution_proven": false,
  "historical_stable_engine_execution_claimed": false
}
```

These fields are false for every lane under this implementation. The existing `stable_engine_touched=false` field remains a touch/control assertion and does not become execution proof.

Control-room and experimental locker mappings are unchanged.

## Scientific and operational boundary

The correction changes metadata identity only. It does not change ranks, probabilities, confidence, weights, scoring, source discovery, timestamps, gate logic, lock paths, promotion behavior, or output paths.

The producer file remains byte-for-byte at Git blob `af27586668c767de126af829c1131c6bae4634ad`. No historical engine was reconstructed or invoked. No `engine_execution` receipt is created. Any future implementation of the v17 reasoning requires a new identity and separate replay/backtest evidence.

This checkpoint does not prove historical blind eligibility, current producer accuracy, or execution of the protected historical stable engine.

## Verification

Focused test:

```text
python3 -m unittest -v tests/test_dr002_stable_lane_metadata_truth_v1.py
Ran 6 tests
OK
```

The test proves:

1. Writer and locker stable mappings equal `StableBaseline_LanePolicy_v1`.
2. The writer overwrites a stale protected-engine value on stable rows.
3. The stable-row note explicitly disclaims separate protected-engine execution.
4. Writer and locker preserve all supplied prediction fields in the synthetic path.
5. Both locker execution-claim fields are false, promotion remains blocked, and no receipt artifact is created.
6. Control-room and experimental mappings retain their prior exact values.
7. The current producer matches its accepted Git blob.
8. The protected historical string is absent from both live operational mappings.

No prediction was generated, no workflow was dispatched, and no unrelated accepted suite was rerun.

## Final checkpoint

```text
stable_lane_name_preserved: true
stable_lane_config_protected_engine_claim_removed: true
stable_engine_execution_proven: false
historical_stable_engine_execution_claimed: false
current_producer_modified: false
forecast_logic_modified: false
dr002_activated: false
promotion_allowed: false
```
