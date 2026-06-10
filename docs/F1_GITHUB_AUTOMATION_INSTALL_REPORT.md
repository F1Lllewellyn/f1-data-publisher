# F1 GitHub Automation Install Report

Generated: 2026-06-10T09:19:33.7267269-04:00
Mode: APPLY
Result: PASS

Existing old/conflicting paths found: 6
Archive location: C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher\_archive\f1_github_automation_preinstall_cleanup_20260610_091933
Gitignore: appended

Validation:
- .github/workflows/openf1-high-frequency-auto-ingest.yml = True
- .github/workflows/openf1-post-event-reliability-metric.yml = True
- .github/workflows/elite-weekend-engine-run.yml = True
- scripts/openf1/openf1_high_frequency_auto_ingest.py = True
- scripts/weekend_run_orchestrator.py = True
- tests/validate_openf1_high_frequency_output.py = True
- configs/openf1/openf1_high_frequency_ingest_policy.json = True
- configs/elite/elite_operational_proof_pattern_control_full7_policy.json = True
- schemas/locked_forecast_ledger_v2_schema.json = True
- templates/dnf_all_precursor_board_template.csv = True
- workbook_bridge/elite_control_room_export_manifest.csv = True

Guardrails:
- Generated high-frequency outputs are ignored by Git.
- No raw telemetry should be committed by default.
- No automatic stable race P1-P20 rank changes are enabled.
- No automatic qualifying P1-P5 rank changes are enabled.
