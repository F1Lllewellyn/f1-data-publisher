# F1 Prediction Engine — Automation Operational Baseline

Date: 2026-06-10

## Locked baseline

GitHub OpenF1 Autopilot + Elite Weekend Engine v2 artifact wiring is the current operational automation baseline.

## Validated state before this patch

- OpenF1 Pre-Race Auto Ingest: PASS
- OpenF1 Full Historical Auto Ingest: PASS
- OpenF1 Post-Race Auto Reliability: PASS_WITH_WARNINGS due to zero post-race feature rows
- Elite Weekend Engine Run: PASS / READY_WITH_POSTRACE_SIGNAL_WARNING

## Current patch intent

This patch completes the five operational items:

1. Lock the automation baseline.
2. Repair the post-race zero-feature issue using a public-data fallback feature builder.
3. Export Elite v2 outputs into workbook/control-room bridge files.
4. Improve GitHub summary reporting.
5. Add a next forecast cycle runbook.

## Guardrails

- Public/proxy OpenF1 data only.
- No private/internal team sensor assumptions.
- No automatic stable race P1-P20 rank changes.
- No automatic qualifying P1-P5 rank changes.
- DNF_ALL remains broad precursor-search target; visible outcome labels are metadata only.
- 2026 no-DRS rule preserved.
