# F1 OpenF1 Autopilot Workflow Patch Report

Generated: 2026-06-10T12:08:58.7888678-04:00
Mode: APPLY

Installed dedicated automated workflows:
- OpenF1 Pre-Race Auto Ingest
- OpenF1 Full Historical Auto Ingest
- OpenF1 Post-Race Auto Reliability

Checkpoint architecture:
- extract_and_checkpoint job uploads extraction checkpoint immediately after the expensive pull.
- validate_report_and_upload job downloads the checkpoint and writes/validates reports without re-extracting.

Archived old workflows:
- .github/workflows/openf1-high-frequency-auto-ingest.yml
- .github/workflows/openf1-post-event-reliability-metric.yml

Archive root:
C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher\_archive\openf1_autopilot_workflow_patch_20260610_120858

Guardrails:
- Public/proxy OpenF1 data only.
- No automatic stable race P1-P20 rank changes.
- No automatic qualifying P1-P5 rank changes.
- DNF_ALL precursor-search policy preserved.
- 2026 no-DRS rule preserved.
