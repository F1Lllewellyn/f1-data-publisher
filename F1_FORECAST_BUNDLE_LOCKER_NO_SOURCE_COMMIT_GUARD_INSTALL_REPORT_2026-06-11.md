# F1 Forecast Bundle Locker No-Source Commit Guard Install Report

Installed UTC: 2026-06-12T00:33:15Z

Installed files:
- .github/workflows/f1-forecast-bundle-locker-v1.yml
- scripts/forecast_bundles/create_forecast_bundles_v1.py

Purpose:
- Prevent manual validation runs from committing structural placeholder bundles when actual forecast rows are missing.
- Add explicit allow_structural_placeholders control.
- Keep scheduled guard behaviour intact.

Stable engine touched: No
Canonical workbook touched: No
Promotion attempted: No
