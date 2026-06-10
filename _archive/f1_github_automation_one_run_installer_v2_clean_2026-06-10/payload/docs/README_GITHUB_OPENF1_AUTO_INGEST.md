# GitHub OpenF1 Auto-Ingest Process for F1 Prediction Engine

Generated: 2026-06-09

## Goal

Make the OpenF1 `car_data` + `location` reliability/fantasy/reporting data pull automatic instead of manual.

This pack adds:

```text
.github/workflows/openf1-high-frequency-auto-ingest.yml
.github/workflows/openf1-post-event-reliability-metric.yml
scripts/openf1/openf1_high_frequency_auto_ingest.py
tests/validate_openf1_high_frequency_output.py
configs/openf1/openf1_high_frequency_ingest_policy.json
requirements-openf1-ingest.txt
.gitignore.openf1_high_frequency
```

## Recommended GitHub process

1. Add these files to the repository.
2. Copy `.gitignore.openf1_high_frequency` into your real `.gitignore`.
3. Add repository secret `OPENF1_TOKEN` only if you have an OpenF1 token. Historical data can often run without it, but a token helps rate limits.
4. Run the workflow manually first:
   - Actions → OpenF1 High-Frequency Auto Ingest → Run workflow
   - `mode = prerace`
   - `fetch_mode = driver_full_session`
5. After it passes, leave the daily schedule active.
6. After each race weekend, manually trigger `OpenF1 Post-Event Reliability Metric`, or let the daily workflow pick up newly completed sessions.

## Why artifact storage, not normal Git commits?

The high-frequency telemetry is large. GitHub blocks files larger than 100 MiB in normal repos, and recommends Git LFS for larger files. For this engine, the clean default is:

```text
commit scripts/configs/reports
store high-frequency outputs as GitHub Actions artifacts or external object storage
```

Do not commit raw Parquet telemetry into the normal repo.

## Workflow outputs

The Actions artifact will include:

```text
raw/car_data/
raw/location/
features/openf1_high_frequency_reliability_features_30s.parquet
metrics/pre_race_first_warning_to_dnf_aggregate.csv
metrics/pre_race_first_warning_to_dnf_driver_summary.csv
manifests/high_frequency_extraction_manifest.csv
reports/openf1_high_frequency_auto_ingest_report.md
```

## Authority guardrail

This pipeline is for:

```text
fantasy risk
reporting reliability sections
race-specialist risk monitoring
main-engine confidence/risk overlays
```

It is **not** allowed to automatically reorder stable race P1-P20 or qualifying P1-P5.
