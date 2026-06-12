# F1 1A Cumulative GitHub Installer Validation Hotfix — 2026-06-11

## Verdict

Pass with warnings.

This hotfix repairs two validation issues exposed by the uploaded GitHub Action logs after the cumulative GitHub installer was pushed.

## Issues found

### 1. Forecast Bundle Locker failed before scheduler guard could run

The workflow constructed a shell string with embedded single quotes:

```text
--gate 'all'
```

When expanded into the Python command, the quotes were passed literally, so argparse received:

```text
'all'
```

instead of:

```text
all
```

Result:

```text
argument --gate: invalid choice: "'all'"
```

### 2. Forecast Gate Source Writer completed, but commit step emitted a pathspec fatal

The source writer correctly produced an audit artifact and did not fabricate forecast rows. However, the commit step attempted to `git add` a missing `latest/forecasts/<event_id>/` path. It was suppressed, but the log was noisy and the audit path was not reliably staged.

### 3. Post-event gate consistency

The Forecast Bundle Locker script is updated so its gate list includes `post_event`, matching the full five-gate validation convention.

## Files installed

- `.github/workflows/f1-forecast-bundle-locker-v1.yml`
- `.github/workflows/f1-forecast-gate-source-writer-v1.yml`
- `scripts/forecast_bundles/create_forecast_bundles_v1.py`

## Safety

- Stable engine is unchanged.
- Canonical workbook is unchanged.
- Promotion remains blocked.
- Stable exact P1-P20 outputs are not overwritten.
- No source files are deleted.

## Validation after install

Run:

```text
F1 Forecast Gate Source Writer v1
```

Manual inputs:

```text
event_id: manual_validation
gate: all
lane: all
commit_outputs: true
```

Expected result:

```text
Pass with warnings
```

It should upload/commit the audit cleanly and show no fatal pathspec message.

Then run:

```text
F1 Forecast Bundle Locker v1
```

Manual inputs:

```text
event_id: 2026_next_event
race_name: Next F1 Event
gate: all
commit_outputs: true
```

Expected result:

```text
Pass with warnings
```

If no forecast rows exist, it may create structurally complete missing-source bundles for a manual run. Scheduled runs should exit cleanly without placeholder churn unless real forecast rows are detected.

## Production note

The Node.js 20 deprecation warning remains a GitHub platform-maintenance warning and is not corrected by this hotfix.
