# F1 OpenF1 Post-Race Empty Feature Validator Hotfix Install Report

Generated: 2026-06-10T12:33:23.9554514-04:00
Mode: APPLY

Patched files:
- tests/validate_openf1_high_frequency_output.py
- .github/workflows/openf1-post-race-auto-reliability.yml
- docs/F1_OPENF1_POSTRACE_EMPTY_FEATURE_HOTFIX.md

Archived previous copies at:
C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher\_archive\postrace_empty_feature_validator_hotfix_20260610_123323

Expected behavior:
- Post-race race-mode runs with successful extraction but zero feature rows now return PASS_WITH_WARNINGS.
- Pre-race and full-historical runs remain strict.
- Zero-feature post-race runs are not valid forecast/fantasy/stable-rank signals.
