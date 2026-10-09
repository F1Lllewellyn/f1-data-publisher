# DR-002 pre-2B-7K4R16 — Qualifying grid source / Race target correction

Date: 2026-10-09

Work order: Issue #250 / `F1-WO-DR002-PRE2B7K4R16-001`

Status: offline source-contract correction complete; not dispatched

## Result

The manual OpenF1 `starting_grid` provenance shadow now distinguishes two
different session identities:

- the exact OpenF1 `starting_grid` source session, narrowly required to be
  standard `Qualifying`; and
- the distinct, later same-meeting target session, narrowly required to be
  `Race`.

This corrects the K4R15 synthetic Race-scoped assumption before any live grid
capture occurred. The deterministic mock fixture reflects the retained
Australia pairing `1279/11230 Qualifying => 1279/11234 Race`, but does not claim
that K4R16 captured original historical raw bytes for those sessions. The
pairing was discovered in later repo-retained derivative source-closure CSVs
whose exact evidence and limits are documented in Issue #250.

No workflow was dispatched, no provider request was made, and no FIA or
Formula1.com content was accessed.

## Corrected evidence boundary

One future separately authorized manual run will still make only one bounded
`sessions?year=<season>` discovery request followed by at most one bounded
`starting_grid?session_key=<qualifying-source-key>` request. The existing final
URL, redirect, content-type, size, readback, clock, and main-only controls remain
unchanged.

Before the grid request, the captured discovery must prove exactly one selected
standard Qualifying source and exactly one distinct Race target in the same
year, meeting, country, location, and circuit. The Race must start after the
Qualifying source ends. Missing, duplicated, cancelled, malformed, Sprint,
Practice, Race-as-source, cross-event, or chronologically impossible records
HOLD before the grid request.

The unchanged K4R1 parentless `source_capture` receipt remains scoped exactly to
the Qualifying source session. The corrected K4R14 adapter likewise keeps its
frozen `UNBOUND` evidence and five-column derived CSV keyed to the Qualifying
source `session_id`. The target Race ID is an unauthenticated caller assertion
validated by the publisher against captured discovery bytes; it is not written
into receipt scope and is not an adapter-authenticated cross-session binding.

The six-file artifact layout and existing workflow/artifact name are unchanged:

- `sessions.response.json`
- `starting_grid.response.json`
- `source_capture_receipt.json`
- `historical_rest_capture_assessment.json`
- `shadow_manifest.json`
- `shadow_report.md`

No derived CSV is persisted.

## Claim ceiling

The manifest and adapter explicitly record:

- `grid_source_session_kind="Qualifying"`;
- `grid_target_race_session_kind="Race"`;
- `source_to_race_link_evidence_type="OPENF1_PROVIDER_DISCOVERY_CLAIM"`;
- `source_session_classification_authenticated=false`;
- `target_race_session_classification_authenticated=false`;
- `producer_input_csv_is_target_race_scoped=false`; and
- `cross_session_join_authorized=false`.

The existing thirteen K4R14 authentication, provenance, production, activation,
and promotion ceilings remain false. This is a post-event mechanics candidate,
not an FIA-authenticated final grid, complete penalty/revision audit, verified
pre-race source, approved Race-scoped prediction input, producer run, stable
engine execution, or forecast-accuracy result.

## Narrow legacy-sentinel maintenance

Issue #250 explicitly authorized only these previously recorded refinements:

- the drivers shadow test now expects the additive endpoint list
  `weather`, `drivers`, `starting_grid`, while all weather/drivers behavioural
  assertions remain intact; and
- the K4R14 dependency audit continues to require exact current hashes for
  untouched dependencies, while the historical publisher and workflow K4R14
  baseline blobs are required to remain present as immutable Git objects because
  later authorized K4R15/K4R16 work changed those paths.

No mismatch is blanket-ignored and no unrelated test was modified.

## Focused offline verification

Exactly the four authorized suites passed:

- corrected starting-grid shadow: 37 passed, 0 failed;
- corrected starting-grid adapter: 30 passed, 0 failed;
- unchanged weather shadow: 23 passed, 0 failed; and
- drivers shadow with the authorized endpoint-list refinement: 19 passed,
  0 failed.

Focused Python compilation, unchanged-workflow hash verification, policy JSON
parsing, exact seven-path scope, and diff checks also passed. All HTTP and clock
behaviour was exercised through injected offline seams.

Engineering progress remains **87/100 PROVISIONAL**, delta **+0**. DR-002
remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion
**NOT ALLOWED**.
