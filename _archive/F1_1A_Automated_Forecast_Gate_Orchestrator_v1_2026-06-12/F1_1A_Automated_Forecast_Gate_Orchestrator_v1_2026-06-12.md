# Automated Forecast Gate Orchestrator v1

## Executive summary

Verdict: Pass with warnings.

This package adds the missing automation layer so the forecast chain can run at real race-weekend gates without manual event-label coordination.

## Why this was needed

The prior one-click workflow validated the chain, but it still required manual triggering. Peak operation should automate ingest, forecast production, validation, and bundle locking at the correct forecast gates.

## Installed workflow

```text
F1 Automated Forecast Gate Orchestrator v1
```

## Automation behavior

Scheduled runs occur on Friday, Saturday, and Sunday at an offset 15-minute cadence. The orchestrator checks the OpenF1 session schedule and exits without changes unless a real gate window is detected.

If a gate is detected, it runs:

```text
OpenF1 Lightweight Source Closure
-> Actual Forecast Producer
-> Forecast Gate Source Writer
-> Forecast Chain Readiness Validator
-> Forecast Bundle Locker
```

## Safety

- Stable engine unchanged.
- Canonical workbook unchanged.
- No promotion.
- No structural placeholders by default.
- Existing no-source bundle guard remains active.
- Manual `event_id` coordination is no longer required.

## Validation classification

This enables automatic gate locking. It does not retroactively convert old manual validation bundles into live blind evidence. Promotion remains blocked until actual scheduled gate bundles are created before outcomes are known and then scored.

## Recommendations

1. Install this patch.
2. Commit and push with GitHub Desktop.
3. Run the workflow once manually in `dry_run` mode to verify install.
4. Leave the scheduled automation enabled for the next race weekend.
5. Continue to block promotion until actual live gate-locked bundles are scored.
