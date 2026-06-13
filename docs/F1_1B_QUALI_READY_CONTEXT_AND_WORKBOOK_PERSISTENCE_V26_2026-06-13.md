# F1 1B v26 — Qualifying-Ready Consumer Context + Workbook Persistence Bridge

Date: 2026-06-13

## Purpose

This package supersedes the previously prepared v25 installer. It keeps the v25 consumer context / trigger-governor work, but also ports the safe part of the Workbook KPI Persistence Handoff into the active 1B workflow path.

## Why this was needed

The inspected handoff showed that Barcelona FP3 data and the workbook KPI sandbox refresh were being generated cleanly, but the refreshed sandbox workbook was not durable because the Control Room upload/commit paths did not preserve `latest/workbook_kpi_refresh_applier/**` and `history/workbook_kpi_refresh_applier/**`.

## What changes

- Adds durable persistence for `latest/session_data_processor/**` and `history/session_data_processor/**`.
- Adds durable persistence for `latest/workbook_kpi_refresh_applier/**` and `history/workbook_kpi_refresh_applier/**`.
- Force-adds only `F1_Workbook_KPI_SANDBOX_*.xlsx` files from the dedicated workbook refresh paths.
- Keeps protected canonical workbooks and `Engine_2026-06-07_STABLE` blocked.
- Keeps v25 chat-context, trigger-governor, notification-decision, and read-only consumer bootstrap outputs.

## Explicit non-goals

- No forecast gate activation.
- No promotion.
- No canonical workbook overwrite.
- No stable engine modification.
- No broad cleanup, deletion, or `.git` access.

## Install sequence

Run the v26 installer, commit/push, then run `F1 Peak Elite Control Room - One Click v1` with:

- `operation = full_run_chain`
- `commit_outputs = true`
- `run_forecast_gate = false`

Expected proof after success:

- `latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_*.xlsx` exists in the repo.
- `history/workbook_kpi_refresh_applier/**` exists in the repo.
- v25/v26 chat context and trigger-governor outputs are committed.
