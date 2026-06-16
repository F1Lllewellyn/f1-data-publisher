# V30Q Live Source Hardening + Failure Taxonomy

This patch adds a dry-run live-source hardening layer for the Session Data Processor Loop.

## Purpose

V30Q classifies source, adapter, probe, validation, and cache artifacts into a deterministic failure taxonomy before any live-source activation, workbook reflection, forecast bundle writing, Race Predictions refresh, Fantasy refresh, or notification sending is allowed.

## What It Does

- Reads optional v30H/v30I/v30J/v30K source artifacts.
- Classifies network, provider, schema, stale, empty, partial, and fallback states.
- Emits a machine-readable taxonomy status.
- Keeps downstream consumer gates closed.

## What It Does Not Do

- Does not fetch live data.
- Does not write to the canonical workbook.
- Does not modify the stable engine.
- Does not activate the forecast gate.
- Does not promote model logic.
- Does not send notifications.

## Next Step

After V30Q is merged and reviewed, the next safe layer is V30R: Forecast Bundle Ledger snapshot writer, still dry-run or sandbox-only unless explicitly approved.
