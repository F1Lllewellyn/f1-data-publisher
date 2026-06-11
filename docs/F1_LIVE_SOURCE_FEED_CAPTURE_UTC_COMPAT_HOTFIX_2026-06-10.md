# F1 Live Source Feed Capture — UTC Compatibility Hotfix

## Verdict

Fail on the previous live-capture validation run; this hotfix corrects the cause.

## What failed

The GitHub workflow was correctly recognized after the cron hotfix, and Python 3.9 was installed as intended for FastF1 live timing compatibility.

The live-capture script then failed immediately with:

`AttributeError: module 'datetime' has no attribute 'UTC'`

## Why it failed

`datetime.UTC` is available in newer Python versions, but the workflow deliberately uses Python 3.9 for FastF1 live timing compatibility. Python 3.9 does not expose `datetime.UTC`.

The correct compatibility pattern is:

`getattr(datetime, "UTC", datetime.timezone.utc)`

That uses `datetime.UTC` when present, and safely falls back to `datetime.timezone.utc` on Python 3.9.

## What this hotfix changes

This hotfix replaces:

`scripts/live_capture/run_live_source_feed_capture.py`

It does not change the workflow schedule, canonical workbook, stable engine, automations, prediction logic, source data, or Method E workbook.

## After install

Run the workflow manually again with:

- capture mode: manual
- duration: 2 to 5 minutes for validation
- session label: manual_test
- commit outputs: true

Expected result:

- the script should no longer fail at import/startup
- if there is no live F1 timing stream at the moment, the output may still be Pass with warnings
- the workflow should still produce manifest/readiness/report artifacts
