# F1 Live Source Feed Capture Diagnostics Hardening Hotfix - 2026-06-10

## Purpose

This hotfix improves the experimental live source-feed capture workflow diagnostics after the first successful workflow execution completed too quickly for a requested manual capture window.

## What changed

- Prints `recording_status`, `recording_error`, raw byte count, and line count directly into the GitHub Actions log.
- Writes `live_source_feed_capture_diagnostics.json` into latest/history outputs and the workflow artifact.
- Classifies FastF1 import/start errors as `Fail` instead of a vague pass-with-warnings.
- Keeps zero-byte completed captures as `Pass with warnings`, because a manual test outside an active F1 live timing stream can legitimately produce no packets.

## Guardrails

- Does not touch canonical workbooks.
- Does not change stable engine logic.
- Does not promote live-source-feed signals.
- Does not alter OpenF1 source closure.

## Validation expectation

After installation, rerun a short manual workflow test. The log should clearly show whether the FastF1 client imported, whether recording started, whether an error occurred, and whether raw packets were written.
