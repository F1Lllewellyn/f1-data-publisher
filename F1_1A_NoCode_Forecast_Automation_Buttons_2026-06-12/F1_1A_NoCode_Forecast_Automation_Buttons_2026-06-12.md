# F1 1A No-Code Forecast Automation Buttons - 2026-06-12

## Verdict

Pass with warnings.

## Reason for patch

The previous orchestrator workflow exposed coding-oriented terms in the GitHub manual run form. That is not appropriate for the desired operating model. The user should not need to understand event_id, gate, dry_run, or force_validation to operate the system.

## Changes

Added two wrapper workflows with no manual inputs:

1. F1 Forecast Automation - Safe Test Button
   - Runs the orchestrator in safe test mode.
   - Does not commit outputs.
   - Requires no typed settings.

2. F1 Forecast Automation - Run Now Button
   - Runs the real automatic gate-detection path.
   - Requires no typed settings.
   - Commits outputs only if the underlying chain creates valid outputs.

## Governance

- Stable engine unchanged.
- Canonical workbook unchanged.
- Promotion blocked.
- Existing scheduled orchestrator remains primary automation.
- One-click/manual workflows remain fallback tools.

## Operator model

The operator now has three plain-English choices:

- Do nothing: scheduled automation runs on its own.
- Click Safe Test Button: verify the automation shell without creating forecast bundles.
- Click Run Now Button: run the auto-detection process immediately.
