# F1 Forecast Chain One-Click Boolean Flag Final Fix - 2026-06-12

## Purpose

This patch fixes the one-click forecast chain workflow after validation showed the Readiness Validator failed because the workflow passed `--strict false` to a script where `--strict` is a boolean flag.

## Changes

- Replaces `.github/workflows/f1-forecast-chain-one-click-validation-v1.yml`.
- Runs Source Writer, Readiness Validator, and Bundle Locker with one shared validation label.
- Omits `--strict` for non-strict validation instead of passing `false`.
- Omits `--allow-structural-placeholders` unless explicitly set to true.
- Commits outputs once at the end instead of assuming each script accepts identical commit flags.
- Uses `actions/checkout@v6`, `actions/setup-python@v6`, and `actions/upload-artifact@v6`.

## Safety

- Does not change stable engine logic.
- Does not touch the canonical workbook.
- Does not promote any model.
- Does not overwrite stable exact P1-P20 outputs.
- Keeps no-placeholder behavior by default.

## Expected validation result

Run `F1 Forecast Chain One-Click Validation v1` with defaults.

Expected if forecast rows exist:

- Source Writer writes/normalizes 15 files.
- Readiness Validator finds 15 / 15 actual forecast sources.
- Bundle Locker creates 15 saved bundles.

