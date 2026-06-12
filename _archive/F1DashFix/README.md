# F1 Dashboard Connector Missing-Scripts Repair

This is a short-path rescue package for the Forecast/Fantasy Readiness Dashboard Connector.

The previous Safe Test failed because GitHub could not find:

```text
scripts/dashboard_connector/health_check_dashboard_connector_v1.py
```

That means the workflow file made it into the repo, but the required dashboard connector scripts did not. This package recopies the workflows, scripts, config, schema, and docs, then verifies the required files exist locally before you commit.

## Install

1. Extract this ZIP to a short folder such as `C:\F1Patch`.
2. Open `F1DashFix`.
3. Double-click `install.bat`.
4. Press Enter when it asks for the repo path.
5. Wait for `INSTALL CHECK PASSED`.
6. Open GitHub Desktop, commit, and push.
7. Run `F1 Forecast/Fantasy Readiness Dashboard - Safe Test Button`.

## Safety

This does not change the stable engine, canonical workbook, model predictions, or promotion state.
