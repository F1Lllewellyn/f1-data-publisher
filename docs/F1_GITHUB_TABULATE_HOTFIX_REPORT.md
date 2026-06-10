# F1 GitHub Tabulate Hotfix Report

Generated: 2026-06-10T10:34:59.3303916-04:00
Mode: APPLY

Purpose: add missing tabulate dependency so pandas DataFrame.to_markdown() works during OpenF1 report generation.

Patched files:
- .github/workflows/openf1-high-frequency-auto-ingest.yml :: patched
- .github/workflows/openf1-post-event-reliability-metric.yml :: patched
- .github/workflows/elite-weekend-engine-run.yml :: patched
- requirements-openf1-ingest.txt :: patched
- requirements-f1-engine-automation.txt :: patched
