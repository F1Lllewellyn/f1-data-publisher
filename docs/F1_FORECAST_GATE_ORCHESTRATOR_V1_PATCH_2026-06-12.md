# F1 Automated Forecast Gate Orchestrator v1 Patch

Created: 2026-06-12

## Purpose

This patch automates the forecast-bundle process so the user does not have to remember a validation label or manually run the chain at each real gate.

The workflow runs the chain:

```text
OpenF1 Lightweight Source Closure
-> Actual Forecast Producer
-> Forecast Gate Source Writer
-> Forecast Chain Readiness Validator
-> Forecast Bundle Locker
```

## What is automated

- Detects real race-weekend gate windows using OpenF1 session schedule when available.
- Runs source closure before forecast production unless disabled.
- Produces actual forecast rows for the detected gate.
- Writes rows into the expected bundle source locations.
- Validates gate/lane readiness.
- Locks bundles only when actual forecast rows exist.
- Commits outputs back to GitHub when enabled.

## Safety rules

- No stable engine logic changes.
- No canonical workbook edits.
- No promotion.
- No structural placeholders by default.
- No manual event_id management required.
- Scheduled runs exit cleanly when no active gate is detected.

## Workflow installed

```text
F1 Automated Forecast Gate Orchestrator v1
```

## Manual use

Use `mode = auto` and leave the defaults.

For system testing only, use `mode = force_validation`.

## Status

This is an automation layer around the already validated source-to-bundle chain. It still requires true live gate timing to produce promotion-quality blind evidence.
