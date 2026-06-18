# V33I — Material-Change Notification Rehearsal

Roadmap Step 9 of 10.

## Purpose

v33I consumes the v33H sandbox Race/Fantasy readiness metadata and writes a sandbox notification preview artifact only.

It rehearses what a material-change notification would say without sending any notification.

## Inputs

- v33H Race/Fantasy readiness metadata refresh status artifact
- v33H Race/Fantasy readiness metadata artifact

## Outputs

- `health/session_processor_material_change_notification_rehearsal_v33i_status.json`
- `sandbox/notification_previews/v33i/material_change_notification_preview_*.json`

## Guardrails

- Production automation remains OFF.
- Forecast gate remains OFF.
- Stable engine remains protected.
- Canonical workbook write remains blocked.
- Production Forecast Bundle Ledger write remains blocked.
- Race Predictions refresh remains blocked.
- Fantasy Predictions refresh remains blocked.
- Notification send remains blocked.
- Model promotion remains blocked.
- No live fetch is performed.

## Operator meaning

If v33I reports `MATERIAL_CHANGE_NOTIFICATION_PREVIEW_READY_SANDBOX_ONLY`, the engine has produced an operator-review notification preview from sandbox readiness evidence.

This is not a sent notification and does not authorize production activation. The next roadmap step remains v33J: final activation decision packet.
