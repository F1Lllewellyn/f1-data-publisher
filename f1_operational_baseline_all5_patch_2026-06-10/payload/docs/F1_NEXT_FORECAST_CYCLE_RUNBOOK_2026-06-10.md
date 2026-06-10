# F1 Prediction Engine — Next Forecast Cycle Runbook

## Normal hands-off sequence

1. `OpenF1 Pre-Race Auto Ingest` runs automatically.
2. `Elite Weekend Engine Run` consumes latest validated artifacts.
3. Workbook/control-room bridge files are generated in the Elite artifact.
4. Forecast/fantasy/report work uses locked control-room outputs.

## Do not manually rerun large extraction unless needed

Do not rerun `OpenF1 Full Historical Auto Ingest` unless:
- the workflow failed,
- a major historical backfill is required,
- the data schema changed,
- or an explicit full rebuild is requested.

## Manual validation after this patch

Run only:

1. `OpenF1 Post-Race Auto Reliability`
2. `Elite Weekend Engine Run`

This tests the post-race fallback and workbook bridge without repeating the large full-historical extraction.

## Expected healthy statuses

- Post-race should move from `PASS_WITH_WARNINGS` toward `PASS` when fallback features are generated.
- Elite should move from `READY_WITH_POSTRACE_SIGNAL_WARNING` toward `READY`.
- Promotion gate should remain non-automatic until audited.

## Consumption rules

- Reliability and DNF_ALL boards are advisory risk boards.
- Fantasy board can inform risk flags and avoid/hold decisions.
- No automatic transfer, qualifying top-five, or race P1-P20 change is allowed from these boards alone.
