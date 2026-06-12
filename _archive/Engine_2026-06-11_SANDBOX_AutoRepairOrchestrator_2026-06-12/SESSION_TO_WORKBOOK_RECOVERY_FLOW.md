# Session-to-Workbook Auto-Recovery Flow

```text
Workbook/KPI Refresh Run
        |
        v
Source-backed refresh?
  | yes                         | no
  v                             v
Commit sandbox outputs       Run Session Data Processor
                                |
                                v
                              Rerun Workbook/KPI Refresh
                                |
                                v
                         Source-backed now?
                           | yes            | no
                           v                v
                    Commit recovered      Stop safely;
                    sandbox outputs       write report only
```

## Report artifacts

- `_runtime/autorepair/session_workbook_recovery/autorepair_status.json`
- `_runtime/autorepair/session_workbook_recovery/autorepair_report.md`
- `latest/autorepair/session_workbook_recovery/autorepair_status.json`
- `history/autorepair/session_workbook_recovery/<run_id>/autorepair_report.md`
