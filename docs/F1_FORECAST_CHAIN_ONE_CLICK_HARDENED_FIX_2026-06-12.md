# F1 Forecast Chain One-Click Validation Hardened Fix - 2026-06-12

## Purpose

This patch hardens the one-click forecast-chain workflow after validation showed the workflow called the Source Writer with an unsupported `--commit-outputs` argument.

## What changed

- The Source Writer is now called only with arguments it accepts.
- The one-click workflow uses one shared validation label across all chain steps.
- The workflow performs a preflight check before running the chain.
- The workflow commits outputs once at the end, instead of assuming each script has the same commit flag.
- The Bundle Locker still blocks structural placeholder bundles unless explicitly allowed.
- The workflow uses Node 24-era GitHub actions versions.

## Safety

This patch does not change stable engine logic, the canonical workbook, prediction outputs, or promotion status.

## Default local repo path

The installer defaults to:

`C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher`

Press Enter to use the default path.

## After install

Run this workflow:

`F1 Forecast Chain One-Click Validation v1`

Leave the defaults as-is.
