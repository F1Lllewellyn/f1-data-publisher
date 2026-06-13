# F1 Peak-Elite System Installer v1

## What this is

A Windows one-click installer for the F1 Prediction Engine GitHub repository.

Default repository path:

```text
C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher
```

## What it installs

- Repairs the 13 workflow Bash commit-block failures that were blocking `workflow-meta-health`.
- Adds `F1 Peak Elite Control Room - One Click v1`.
- Adds no-dependency workflow validation using `bash -n` in GitHub Actions.
- Adds peak-elite health reports for workflow, source-readiness, workbook/KPI, dashboard, and governance state.
- Adds a cleanup inventory report, but does not delete files.
- Writes ChatGPT-facing system status briefs into `latest/chat_context/`.

## What it does not do

- Does not modify `Engine_2026-06-07_STABLE`.
- Does not overwrite canonical workbook files.
- Does not promote experimental/challenger logic.
- Does not change stable prediction logic.
- Does not force push.
- Does not delete old files.
- Does not require local Python.

## How to run

1. Unzip this package.
2. Double-click:

```text
INSTALL_F1_PEAK_ELITE_SYSTEM.cmd
```

3. The installer copies the payload into your local repo, backs up overwritten files, commits/pushes if Git is available, and opens/triggers the GitHub workflow.
4. In GitHub Actions, run:

```text
F1 Peak Elite Control Room - One Click v1
```

Recommended first run:

```text
operation = full_safe_chain
commit_outputs = true
run_forecast_gate = false
```

After that passes, run:

```text
operation = full_run_chain
commit_outputs = true
run_forecast_gate = false
```

Only enable `run_forecast_gate=true` after source-readiness and workbook/KPI refresh are green.

## Why this is safer than another narrow hotfix

The previous failure was not model logic; it was workflow shell syntax. This installer repairs that class of failure, then adds a control-room layer to prevent the same kind of failure from silently blocking the processor chain again.

## Cleanup posture

This installer does not delete. It backs up overwritten files to:

```text
_archive\F1_PEAK_ELITE_PREINSTALL_BACKUP_<timestamp>
```

The new cleanup script produces an inventory of files that can later be archived or consolidated after review.
