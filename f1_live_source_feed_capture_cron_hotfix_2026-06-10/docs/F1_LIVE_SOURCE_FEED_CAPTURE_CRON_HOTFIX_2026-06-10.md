# F1 Live Source Feed Capture Cron Hotfix — 2026-06-10

## Verdict
Pass with warnings.

## What this fixes
The original experimental live source-feed capture workflow used an invalid GitHub Actions cron expression:

```text
*/15 * * 5,6,0
```

That expression has only four cron fields. GitHub Actions requires five fields:

```text
minute hour day-of-month month day-of-week
```

This hotfix replaces it with:

```text
*/15 * * * 5,6,0
```

Meaning: run every 15 minutes on Friday, Saturday, and Sunday.

## Why this happened
The missing `*` for the month field made GitHub treat `5,6,0` as the month field instead of the day-of-week field. That is why GitHub rejected the workflow before it could run.

## What this hotfix changes
Only this file is replaced:

```text
.github/workflows/f1-live-source-feed-capture-experimental.yml
```

## What this hotfix does not change
- It does not touch the canonical workbook.
- It does not change the stable engine baseline.
- It does not change automations.
- It does not promote the live source-feed layer.
- It does not change prediction logic.

## Validation after install
After installing and pushing this hotfix, the workflow should no longer show the invalid cron annotation. The workflow graph may still say it will be generated after the next run. That is normal until the first successful run.

Recommended first validation remains a manual short capture test, not a full scheduled race capture.
