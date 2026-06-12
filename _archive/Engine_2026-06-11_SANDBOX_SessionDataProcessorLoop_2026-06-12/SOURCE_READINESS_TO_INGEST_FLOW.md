# Source-Readiness-to-Ingest Flow

```text
[Race Weekend Watcher]
        |
        v
[Gate Timing Detector]
        |  if session-ended window detected
        v
[Session Data Processor]
        |
        +--> OpenF1 sessions/drivers/laps/weather/race_control/position/pit/stints
        +--> FastF1 optional enrichment/cache layer
        +--> FIA/public side-loaded files
        +--> multimodal/manual note sidecars
        |
        v
[Validation Layer]
        |
        +--> session_key / meeting_key / round match
        +--> driver ID checks
        +--> timestamp freshness checks
        +--> lap count and row count checks
        +--> missing column scan
        +--> duplicate row/key scan
        +--> obvious anomaly scan
        |
        v
[Readiness Classifier]
        |
        +--> clean
        +--> partial
        +--> late
        +--> conflicting
        +--> needs_manual_review
        |
        v
[Artifact Writer]
        |
        +--> latest/session_data_processor/<event>/<session>/...
        +--> history/session_data_processor/<event>/<run_id>/...
        +--> latest/latest_manifest.json
        +--> latest/data_readiness.json
        +--> latest/combined_source_manifest.json
        |
        v
[Workbook/KPI Sandbox Update]
        |
        +--> KPI readiness JSON/CSV
        +--> optional sandbox workbook update plan
        +--> optional sandbox workbook copy only
        |
        v
[Forecast Bundle Ledger Snapshot]
        |
        v
[Race/Fantasy Readiness State]
        |
        v
[Notification Gate]
        |
        +--> notify only if readiness materially improves, forecast state changes, or manual review needed
```
