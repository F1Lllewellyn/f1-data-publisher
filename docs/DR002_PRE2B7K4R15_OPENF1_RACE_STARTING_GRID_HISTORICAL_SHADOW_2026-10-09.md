# DR-002 pre-2B-7K4R15 — OpenF1 Race starting-grid historical shadow

Date: 2026-10-09

Work order: Issue #247 / `F1-WO-DR002-PRE2B7K4R15-001`

Status: implementation and mock verification complete; not dispatched

## Result

The accepted manual OpenF1 historical REST provenance-shadow path now supports
an explicit third endpoint, `starting_grid`, for one uniquely selected completed
historical session whose provider discovery metadata declares both
`session_name == "Race"` and `session_type == "Race"`.

This is an additive refinement of the existing weather and drivers shadow. It
does not alter their request semantics or five-file artifacts, the empty-key and
scheduled legacy source-closure path, any producer or model, or the protected
stable engine.

No workflow was dispatched and no live OpenF1, FIA, or Formula1.com request was
made. No source receipt or live artifact was created by this work result.

## Bounded future execution contract

The manual workflow requires a nonempty explicit session key before checkout,
rejects unsupported endpoint values before checkout, and retains the existing
main-only, credential-free, no-commit/no-push shadow controls. The default
endpoint remains `weather`; schedules and legacy artifact routing are unchanged.

For `starting_grid` only, a future authorized run will:

1. issue one canonical `sessions?year=<season>` discovery GET with redirects
   disabled;
2. persist and read back the exact bounded discovery bytes as
   `sessions.response.json`;
3. select exactly one canonical positive session and meeting identity with
   completed, timezone-aware Race metadata;
4. enforce `session_end + 1800 seconds` and monotonic UTC observation times;
5. issue at most one exact
   `starting_grid?session_key=<selected-key>` GET, also with redirects disabled;
6. persist and read back the exact bounded grid bytes as
   `starting_grid.response.json`;
7. create the unchanged K4R1 canonical parentless `source_capture` receipt; and
8. pass the persisted receipt and grid readbacks to the unchanged K4R14 offline
   adapter with `session_kind="Race"`.

Both responses require HTTP 200, an exact final URL, no redirect, JSON content
type when exposed, and a maximum of 8 MiB. There is no retry, alias, meeting
fallback, mirror, range request, second grid request, or persisted normalized
CSV.

A successful grid shadow contains exactly these six logical files:

- `sessions.response.json`
- `starting_grid.response.json`
- `source_capture_receipt.json`
- `historical_rest_capture_assessment.json`
- `shadow_manifest.json`
- `shadow_report.md`

The uniquely named future artifact is
`dr002-pre2b7k4r15-openf1-starting-grid-historical-shadow`. Existing weather
and drivers artifact names remain unchanged. HOLD diagnostics remain run-scoped
and cannot assert a receipt or derived CSV that was not successfully created.

## Provenance and claim ceiling

The discovery record is labelled `OPENF1_PROVIDER_DISCOVERY_CLAIM`. It is
supplementary provider-reported session classification evidence, not a signed
FIA session listing and not a separate K4R1 capture receipt. The grid receipt
continues to bind only the exact raw `starting_grid` response.

The manifest records both raw response hashes and clocks, the K4R1/K4R14
statuses, source/receipt/frozen-manifest bindings, `UNBOUND` trust, row/driver/
slot counts, and only the hash and runtime identity of the derived CSV. The CSV
itself is not persisted.

All thirteen K4R14 scientific, authentication, production, activation and
promotion ceilings remain false. OpenF1 is an unofficial mechanics source. This
capability does not authenticate an FIA final grid, establish original/final
revision completeness, prove pre-race availability, join cross-session inputs,
run the producer or stable engine, generate a forecast, activate DR-002, or
permit promotion.

## Exact dependency basis

The implementation began from the independently specified Git blobs:

- publisher `f2e28d326255a48a48f873d101cd3e3e99955c1f`
- workflow `c32bd7bb2f8a84d1bb4e8995be246c389418f512`
- policy `f386d8b6dd7025b313a1ea082ef699c4b1bd2e7c`
- weather shadow tests `bbe623a48322d273990dd34d05fedf133f1af828`
- drivers shadow tests `97d3e8f2cfb8786410f13cb7fac40c11b1a91ee8`
- K4R1 capture contract `e68fa528cd73cd5c72afd97622a00d6e5b29be19`
- K4R14 grid adapter `6c435ccaa03515f3d8d9c6aa88bc9070cfe824be`
- K4R6 drivers adapter `357ac56a6cfe317e21d9ce71d78c58683e444a5a`
- receipt machinery `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae`
- handoff contract `85ce44807ef159b5ba5d3bfd543ea1f945097f77`

The seven dependencies outside the three authorized modified paths remain
byte-identical. The three prior publisher/workflow/policy blobs remain present
in Git as the reviewed implementation bases.

## Focused offline verification

Only the work-order-specified mock/offline suites and static checks were run:

- K4R15 starting-grid shadow: 34 tests passed, 0 failed.
- Existing weather shadow: 23 tests passed, 0 failed.
- Existing drivers shadow: 18 tests passed; its one pre-K4R15 exact-policy-list
  sentinel failed solely because the authorized policy now adds
  `starting_grid`. The old test was not patched, as ordered; all drivers
  behavioral tests passed.
- Unchanged K4R14 adapter: 28 test methods passed and one dependency-pin method
  reported two failing subcases solely for the authorized publisher and
  workflow modifications. All adapter behavior tests passed, and the old test
  was not patched.

Python syntax compilation, JSON parsing, YAML parsing, exact five-path status,
and whitespace/error diff checks also passed. All verification was local and
offline with injected HTTP, clock, writer, and reader seams.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion
**NOT ALLOWED**.
