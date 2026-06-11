# F1 Live Source Feed Capture FastF1 Python 3.9 Compatibility Hotfix

## Verdict

This hotfix fixes the latest validation failure from the live source-feed capture workflow.

## What failed

The workflow ran under Python 3.9, which is intentional for FastF1 live timing compatibility.

The dependency install step used:

`fastf1>=3.3,<4`

That allowed GitHub to install FastF1 3.7.0. During import, the live-capture script failed with:

`TypeError("unsupported operand type(s) for |: 'NoneType' and 'type'")`

That points to Python 3.10-style type-union syntax being evaluated under Python 3.9.

## Fix

The workflow now pins FastF1 to:

`fastf1>=3.3,<3.7`

The live-capture script also records:

- Python version
- installed FastF1 version
- diagnostic hint if FastF1 import fails

## What this hotfix does not change

- It does not touch the canonical workbook.
- It does not change the stable engine.
- It does not promote live source-feed evidence.
- It does not affect OpenF1 source-closure workflows.
- It does not run heavy data capture by itself.

## After installing

Run the workflow manually with:

- capture_mode: manual
- duration_minutes: 2
- session_label: manual_test
- commit_outputs: true

Expected next outcome:

- Pass with warnings if no live F1 stream is available, but FastF1 imports correctly.
- Pass if live source-feed bytes are captured.
- Fail only if FastF1 still cannot import or the capture start fails.
