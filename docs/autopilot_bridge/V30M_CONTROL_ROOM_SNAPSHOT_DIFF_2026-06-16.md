# V30M Control Room Snapshot Diff Dry-Run

This PR adds previous-snapshot diffing for the v30L Control Room source-cache summary.

## Scope

- Reads the current v30L source-cache summary.
- Reads the previous source-cache summary snapshot if present.
- Writes whether the readiness state materially changed.
- Writes a refreshed previous snapshot for the next comparison.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook writes are not enabled.
- Notification sending is not enabled.
- Race prediction and fantasy readiness consumers remain closed.

## Kernel Routing Note

Current project kernel routing remains authoritative until the project-level kernel text is explicitly updated. If the project chooses the newer chat hierarchy, update the project kernel outside this PR so active engine work routes to the chosen active master chat consistently.

## Follow-up

After review, v30N can add sandbox workbook readiness reflection or a reviewed material-change notifier. Neither should activate production forecasts or write the canonical workbook without explicit approval.
