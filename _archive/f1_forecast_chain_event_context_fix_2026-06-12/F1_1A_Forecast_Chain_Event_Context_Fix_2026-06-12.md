# F1 1A Forecast Chain Event Context Fix - 2026-06-12

Verdict: Pass with warnings.

This package fixes the forecast chain validation confusion by making the Source Writer, Readiness Validator, and Bundle Locker default to the same forecast event label.

It also adds a new one-click validation workflow:

- F1 Forecast Chain One-Click Validation v1

This workflow runs the source writer, readiness validator, and bundle locker in one sequence using one shared label, so the user does not need to manually manage the event_id field.

Default local repo path:

C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher

No stable engine logic, canonical workbook files, prediction outputs, or promotion status are changed.
