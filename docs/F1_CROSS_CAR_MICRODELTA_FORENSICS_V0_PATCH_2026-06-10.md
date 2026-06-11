# F1 Cross-Car Microdelta Forensics + Pattern Discovery v0 Patch

Date: 2026-06-10

This experimental GitHub patch installs a post-race forensic layer that runs all structurally valid cross-car comparisons available from completed datasets. It is designed to improve race reports and create tagged challenger inputs for specialist engines.

It does not change the stable engine, canonical workbook, or prediction outputs directly.

Installed files:

- `.github/workflows/f1-cross-car-microdelta-forensics-v0-experimental.yml`
- `scripts/microdelta/run_cross_car_microdelta_forensics_v0.py`
- `configs/microdelta/cross_car_microdelta_forensics_policy_v0.json`

Outputs:

- `latest/cross_car_microdelta_forensics/`
- `history/cross_car_microdelta_forensics/<timestamp>/`

Operating principle:

> User examples are not limits. The module runs every structurally valid comparison, then gates what is safe to use.
