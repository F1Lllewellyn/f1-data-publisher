# Session Processor -> Auto-Repair Integrated Flow

```text
Existing watchers detect timing/readiness gate
  -> integrated scheduled workflow starts shortly after
  -> dependency preflight
  -> session processor pulls/validates OpenF1/FastF1/FIA/public-source artifacts where available
  -> writes latest/latest_manifest.json, latest/data_readiness.json, latest/combined_source_manifest.json
  -> Auto-Repair checks Workbook/KPI refresh source status
  -> if missing: rerun session processor + workbook refresh recovery
  -> if source-backed: commit session artifacts + sandbox workbook/KPI package + autorepair report
  -> if still missing: no commit, upload diagnostics only
```

## Commit gate

The integrated workflow commits only when:

```text
autorepair commit_allowed.txt == true
```

That value is only true when the final Workbook/KPI refresh is source-backed.
