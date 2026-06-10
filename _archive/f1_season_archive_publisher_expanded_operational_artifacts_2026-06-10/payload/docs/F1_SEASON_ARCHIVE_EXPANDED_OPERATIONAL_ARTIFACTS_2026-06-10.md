# F1 Season Archive Publisher Expanded Operational Artifacts Patch

## Purpose

This patch expands the compact season archive release to include the three operational artifacts created after the first archive release:

- `f1-forecast-use-dry-review`
- `f1-race-weekend-operating-rhythm`
- `f1-post-race-scoring-loop`

It preserves the existing archive behavior:

- no OpenF1 extraction is run,
- raw high-frequency data is not archived by default,
- compact derived outputs are published as GitHub Release assets,
- GitHub Actions artifact retention is no longer the long-term record.

## Expected result

After installing and rerunning `F1 Season Archive Publisher`, the release archive should include seven compact source profiles:

1. Elite Weekend Engine v2
2. Workbook Control Room Bridge
3. Dry Forecast Cycle
4. Forecast Use Dry Review
5. Race Weekend Operating Rhythm
6. Post-Race Scoring Loop
7. Automation Baseline Snapshot
