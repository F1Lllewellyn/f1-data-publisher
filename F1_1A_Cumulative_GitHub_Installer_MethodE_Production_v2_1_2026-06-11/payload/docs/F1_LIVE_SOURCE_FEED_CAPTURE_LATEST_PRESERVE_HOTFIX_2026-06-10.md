# F1 Live Source Feed Capture Consolidated Validation Patch — 2026-06-10

## Purpose

This is the cumulative stabilized patch for the experimental GitHub-led Live Source Feed Capture Layer. It rolls the validation fixes into one install package so the user does not need to apply multiple incremental hotfixes.

## Cumulative fixes included

- Valid GitHub Actions cron syntax.
- Python 3.9 UTC compatibility fallback.
- FastF1 pinned below the Python 3.9 import-breaking range.
- Diagnostics hardening with clear status, raw byte count, packet line count, and installed FastF1 version.
- Manual validation split between infrastructure-only mode and force-source-feed mode.
- Latest evidence preservation: non-evidence validation runs write history and status, but do not overwrite/delete the latest evidence-bearing capture.

## Expected validation plan

1. Run one infrastructure-only validation after install. Expected: Pass with warnings, artifact upload, commit/push, latest evidence preserved.
2. Run one force-source-feed validation during an actual live F1 session. Expected: raw bytes greater than zero and packet line count greater than zero.

## Guardrails

This patch does not touch the canonical workbook, stable engine, Method E workbook, prediction logic, or OpenF1 source-closure workflow. It remains experimental and evidence from this layer must pass post-session reconciliation before promotion.
