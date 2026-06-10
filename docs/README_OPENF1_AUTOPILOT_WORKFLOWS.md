# OpenF1 Autopilot Workflows with Checkpoint/Resume Protection

This patch replaces the confusing flexible OpenF1 workflows with dedicated automated workflows.

## New workflows

| Workflow | Human mode selection | Mode | Schedule |
|---|---:|---|---|
| OpenF1 Pre-Race Auto Ingest | None | `prerace` | Daily 09:15 UTC |
| OpenF1 Full Historical Auto Ingest | None | `all` | Weekly Wednesday 10:10 UTC |
| OpenF1 Post-Race Auto Reliability | None | `race`, latest completed meeting, last 14 days | Weekly Monday 10:35 UTC |

Each workflow can still be run manually with one click, but there are no mode/fetch fields to tune.

## Checkpoint protection

Each workflow is split into two jobs:

1. `extract_and_checkpoint`
   - Performs the expensive OpenF1 pull.
   - Builds feature marts/metrics.
   - Uploads a checkpoint artifact immediately.

2. `validate_report_and_upload`
   - Downloads the checkpoint artifact.
   - Writes reports without re-extracting data.
   - Validates output.
   - Uploads the final validated artifact.

If the report/validation job fails, rerun the failed job. The extraction checkpoint remains available and the expensive OpenF1 pull does not need to be repeated.

## Archived old workflows

The installer archives these older/confusing workflows if present:

- `.github/workflows/openf1-high-frequency-auto-ingest.yml`
- `.github/workflows/openf1-post-event-reliability-metric.yml`

They are moved to:

`_archive/openf1_autopilot_workflow_patch_<timestamp>/`

Nothing is permanently deleted.
