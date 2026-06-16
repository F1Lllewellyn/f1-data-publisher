# V30Y R2 Material-Change Threshold and Notification Gating

This patch replaces the v30Y command payload with a clean ASCII-only dry-run material-change gate.

## Purpose

V30Y compares current Session Data Processor Loop readiness evidence with a previous snapshot and decides whether a material-change notification preview should be created.

## Scope

- Detects readiness status transitions.
- Detects blocking-source count changes.
- Detects failed-case count changes.
- Detects source row-count changes above policy threshold.
- Detects data-ready case changes.
- Treats live-fetch evidence as material manual-review signal.
- Keeps notification sending disabled.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine remains untouched.
- Canonical workbook remains untouched.
- Race Predictions and Fantasy refresh remain disabled.

## Next Step

After V30Y R2 is merged and reviewed, proceed to V30Z: Control Room operator dashboard packet.
