# Engine_2026-06-11_SANDBOX_ForecastFantasyReadinessDashboardConnector_2026-06-12

Sandbox-only Forecast/Fantasy Readiness Dashboard Connector.

## Purpose

Connect refreshed Session Data Processor and Workbook/KPI Refresh artifacts into simple dashboard files that Race Predictions and Fantasy chats can read without manually inspecting workbook files.

This closes the next production-readiness gap:

```text
session ingest -> workbook/KPI refresh -> dashboard state -> Race/Fantasy chat readiness context
```

## No protected assets modified

- Canonical workbook: not overwritten
- Engine_2026-06-07_STABLE: not changed
- Stable exact P1-P20: not overwritten
- Promotion: blocked
- Old files: not deleted

## New no-code workflows

- F1 Forecast/Fantasy Readiness Dashboard - Safe Test Button
- F1 Forecast/Fantasy Readiness Dashboard - Run Now Button
- F1 Forecast/Fantasy Readiness Dashboard Integrated Loop v1

## Outputs

The connector writes:

- latest/readiness_dashboards/combined_readiness_dashboard.json
- latest/readiness_dashboards/combined_readiness_dashboard.md
- latest/readiness_dashboards/race_predictions_readiness_state.json
- latest/readiness_dashboards/fantasy_readiness_state.json
- latest/readiness_dashboards/race_predictions_latest_session_brief.md
- latest/readiness_dashboards/fantasy_latest_session_brief.md
- latest/chat_context/RACE_PREDICTIONS_LATEST_SESSION_BRIEF.md
- latest/chat_context/FANTASY_PREDICTIONS_LATEST_SESSION_BRIEF.md
- history/readiness_dashboards/<timestamp>/...

## Install

Run:

```text
installer/RUN_F1_FORECAST_FANTASY_READINESS_DASHBOARD_CONNECTOR_WINDOWS.bat
```

Press Enter for the default repo path.

Then commit and push in GitHub Desktop.

## Validate

First run:

```text
F1 Forecast/Fantasy Readiness Dashboard - Safe Test Button
```

Then run:

```text
F1 Forecast/Fantasy Readiness Dashboard - Run Now Button
```

Send logs for review.
