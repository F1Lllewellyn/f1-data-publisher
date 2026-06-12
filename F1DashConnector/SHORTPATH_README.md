# F1 Dashboard Connector Short-Path Package

This package is the short-path version of the Forecast/Fantasy Readiness Dashboard Connector.

It removes the long local validation sample folder that caused Windows error `0x80010135: Path too long`.

## Install

1. Extract this ZIP somewhere short, such as `C:\F1Patch`.
2. Run `F1DashConnector\install.bat`.
3. Press Enter when asked for the repo path.
4. Commit and push in GitHub Desktop.
5. Run `F1 Forecast/Fantasy Readiness Dashboard - Safe Test Button` in GitHub Actions.

## Safety

This package does not touch the canonical workbook, stable engine, or promotion logic.
