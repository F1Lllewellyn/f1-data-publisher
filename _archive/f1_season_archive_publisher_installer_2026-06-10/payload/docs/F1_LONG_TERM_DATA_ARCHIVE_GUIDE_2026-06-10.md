# F1 Long-Term Data Archive Guide

## Archive layers

1. Actions artifacts — short-term handoff/debug
2. GitHub Releases — compact long-term season archive
3. Explicit raw snapshots — only when needed

## Compact archive contents

The release archive contains derived outputs and manifests, not raw high-frequency data.

## Future seasons

For 2027 and beyond, the archive publisher can be run with the `season_year` workflow input changed to the target year. The workflow default can be updated at season rollover.
