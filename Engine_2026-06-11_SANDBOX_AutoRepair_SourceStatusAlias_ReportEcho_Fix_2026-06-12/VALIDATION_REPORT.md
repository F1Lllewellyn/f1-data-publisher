# Validation Report - Engine_2026-06-11_SANDBOX_AutoRepair_SourceStatusAlias_ReportEcho_Fix_2026-06-12

## Verdict

Pass with warnings.

## What was validated

- `overall_status` from the Session Data Processor is now accepted by the Workbook/KPI Refresh Applier.
- A source-backed FP2-style sample classified as `needs_manual_review` becomes commit-eligible.
- Missing source remains blocked.
- Auto-Repair Run Now now prints the plain-English repair report into the GitHub log.

## Local test result

```json
{
  "package": "Engine_2026-06-11_SANDBOX_AutoRepair_SourceStatusAlias_ReportEcho_Fix_2026-06-12",
  "created_utc": "2026-06-12T22:32:29.701487+00:00",
  "local_tests": [
    {
      "name": "overall_status_alias_commit_eligible",
      "returncode": 0,
      "stdout": "{\n  \"status\": \"refresh_applied\",\n  \"commit_allowed\": true,\n  \"source_status\": \"needs_manual_review\",\n  \"material_change\": true,\n  \"warnings\": [\n    \"source_classification=needs_manual_review\"\n  ],\n  \"latest_output_root\": \"latest/workbook_kpi_refresh_applier\",\n  \"history_output_root\": \"history/workbook_kpi_refresh_applier/20260612T223237Z\",\n  \"sandbox_workbook\": \"latest/workbook_kpi_refresh_applier/F1_Workbook_KPI_SANDBOX_Refresh_Test_GP_session_20260612T223237Z.xlsx\",\n  \"canonical_workbook_overwrite\": false,\n  \"stable_engine_modified\": false,\n  \"promotion_allowed\": false\n}\n",
      "stderr": "st recent call last):\n  File \"/tmp/tmp.9eeVjt35CN/artifact_tool_v2-2.7.5/artifact_tool/patches/warm_spreadsheet_runtime_on_startup.py\", line 26, in warm_spreadsheet_runtime_on_startup\n  File \"/tmp/tmp.9eeVjt35CN/artifact_tool_v2-2.7.5/artifact_tool/spreadsheet_warmup.py\", line 785, in warm_spreadsheet_runtime\n  File \"/tmp/tmp.9eeVjt35CN/artifact_tool_v2-2.7.5/artifact_tool/spreadsheet_warmup.py\", line 720, in _warm_feature_flows\n  File \"/tmp/tmp.9eeVjt35CN/artifact_tool_v2-2.7.5/artifact_tool/spreadsheet_warmup.py\", line 704, in _warm_collaboration_flows\n  File \"/tmp/tmp.9eeVjt35CN/artifact_tool_v2-2.7.5/artifact_tool/generated/interface/models.py\", line 48821, in hydrate_crdt_from_proto\n  File \"/tmp/tmp.9eeVjt35CN/artifact_tool_v2-2.7.5/artifact_tool/rpc/remote.py\", line 747, in __call__\n  File \"/tmp/tmp.9eeVjt35CN/artifact_tool_v2-2.7.5/artifact_tool/rpc/client.py\", line 150, in call\nartifact_tool.rpc.client.RemoteError: hydrateCrdtFromProto requires an empty collaborative document.\n"
    },
    {
      "name": "runtime_status",
      "status": "refresh_applied",
      "source_status": "needs_manual_review",
      "commit_allowed": true
    },
    {
      "name": "missing_source_blocked",
      "returncode": 0,
      "status": "no_action",
      "reason": "session_processor_sources_missing_or_incomplete",
      "commit_allowed": false
    }
  ],
  "promotion": "NOT_PROMOTED",
  "protected_assets": {
    "canonical_workbook_touched": false,
    "stable_engine_touched": false,
    "promotion_allowed": false
  }
}
```

## Promotion decision

NOT PROMOTED.

This is automation infrastructure only. It does not promote any prediction layer.
