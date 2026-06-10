# F1 OpenF1 Autopilot Workflow Installer

This installer adds dedicated automated OpenF1 workflows and checkpoint protection.

## Use

1. Unzip this package.
2. Open the `installer` folder.
3. Double-click:

`RUN_OPENF1_AUTOPILOT_WORKFLOW_INSTALLER_WINDOWS.bat`

4. When asked for the repo path, paste only:

`C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher`

5. Commit and push the changed files in GitHub Desktop.

## What changes

Adds these workflows:

- OpenF1 Pre-Race Auto Ingest
- OpenF1 Full Historical Auto Ingest
- OpenF1 Post-Race Auto Reliability

Archives these older/manual-mode workflows if present:

- OpenF1 High-Frequency Auto Ingest
- OpenF1 Post-Event Reliability Metric

Each new workflow is split into:

- `extract_and_checkpoint`
- `validate_report_and_upload`

That means report/validation failures no longer force a full re-extraction.
