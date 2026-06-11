# F1 Black-Box Temporal Validation Harness v1 Patch

Installs a GitHub workflow and script that create black-box temporal replay containers, leakage audits and promotion-gate records.

This patch does not fabricate actual saved forecast bundles. It labels all historical reconstructions as black-box temporal replay unless rows were locked before outcome.

## Workflow

`F1 Black-Box Temporal Validation Harness v1`

## Installed files

- `.github/workflows/f1-black-box-temporal-validation-harness-v1.yml`
- `scripts/validation/run_black_box_temporal_validation_v1.py`
- `configs/validation/black_box_temporal_validation_policy_v1.json`
- `docs/F1_BLACK_BOX_TEMPORAL_VALIDATION_HARNESS_V1_PATCH_2026-06-11.md`

## Promotion rule

No promotion from black-box replay alone. Actual gate-locked live forecast bundles remain required.
