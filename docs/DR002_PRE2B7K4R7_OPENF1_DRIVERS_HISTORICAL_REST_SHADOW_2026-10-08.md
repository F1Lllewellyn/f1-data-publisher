# DR-002 pre-2B-7K4R7 — OpenF1 drivers historical REST provenance shadow

**Date:** 2026-10-08

**Work order:** `F1-WO-DR002-PRE2B7K4R7-001` / Issue #225

**Observed main:** `82dfec977791bc2ea9363277f8e839e97012d179`

**Status:** bounded implementation; Adviser acceptance pending

## Delivered boundary

The accepted K4R2 manual historical REST provenance-shadow seam now permits an
explicit `weather` or `drivers` choice. `weather` remains the default. Scheduled
runs and manual runs with an empty session key retain the existing legacy source
closure path. Selecting `drivers` without an explicit session key fails before
checkout, OpenF1 access, or legacy output generation.

The drivers path reuses the existing main-only run identity, one exact session
selection, completed-session metadata, session-end plus 1,800-second historical
window, response-byte observation chronology, run-scoped artifact directory,
and unchanged K4R1 parentless `source_capture` contract. It performs exactly one
scientific drivers request after session discovery:

```text
https://api.openf1.org/v1/drivers?session_key=<positive_session_id>
```

No driver-number or alternate-session fallback is available in shadow mode.

## Exact-byte and derived-runtime handling

After the complete HTTP response bytes exist, the shadow observes
`first_observed_utc`, writes `drivers.response.json` unchanged, reads it back,
and verifies its exact bytes and SHA-256. The unchanged K4R1 assessor receives
those bytes and explicit event/meeting/session scope. Its canonical, parentless
receipt is verified for URI, deterministic source identity, raw hash, scope and
exact canonical bytes, then persisted unchanged.

Drivers mode passes the exact persisted raw and receipt bytes to the unchanged
K4R6 adapter. Shadow success requires
`OPENF1_DRIVERS_PRODUCER_ADAPTER_VALIDATED`. Only K4R6 status, driver row and
unique counts, derived CSV SHA-256, and
`derived:openf1-drivers-csv:<sha256>` identity enter the manifest/report.
Derived CSV bytes are never written and are not scientific evidence.

The successful artifact remains exactly five files:

- `drivers.response.json` (or unchanged `weather.response.json` in weather mode)
- `source_capture_receipt.json`
- `historical_rest_capture_assessment.json`
- `shadow_manifest.json`
- `shadow_report.md`

All files remain under the existing run-scoped
`_runtime/dr002_pre2b7k4r2_openf1_historical_rest_shadow/gha-<run>-<attempt>`
directory. Shadow mode writes neither `latest/**` nor `history/**`, persists no
checkout credentials, and cannot commit or push.

## Workflow and policy controls

The existing workflow has one optional choice input,
`provenance_shadow_endpoint`, restricted to `weather` and `drivers` with
`weather` as default. The value is passed through a quoted environment variable,
not interpolated directly into the shell command. Main-only and nonempty-session
guards remain. Weather retains the accepted K4R2 artifact name; drivers uses the
K4R7-specific artifact name. Exactly one run-scoped package is uploaded for a
valid shadow run.

The policy preserves `endpoint: weather` and adds only the bounded endpoint
choice and drivers-mode constraints: session-key-only request, mandatory K4R6
validation, no derived CSV persistence/evidence claim, no new receipt, no
official roster-authority claim, and no pre-observation availability claim.

## Dependency verification

Relevant-path/blob comparison on observed main matched every Issue #225 pin
before mutation:

| Dependency | Git blob SHA | K4R7 treatment |
|---|---|---|
| Source-closure publisher | `6e29dac3587c4f1b06734edd75b0d2c429aec04a` | Authorized modification |
| Existing workflow | `506efa4098d3879fcd7374ae755c1daa4bb7f1d3` | Authorized modification |
| Existing K4R2 tests | `bbe623a48322d273990dd34d05fedf133f1af828` | Unchanged |
| Source-closure policy | `8c3a4a52f37aa39b761a45bebfafa1dda7b2e252` | Authorized modification |
| K4R1 capture | `e68fa528cd73cd5c72afd97622a00d6e5b29be19` | Unchanged |
| K4R6 drivers adapter | `357ac56a6cfe317e21d9ce71d78c58683e444a5a` | Unchanged |
| K4R5 composition | `090c61af27ef932aae51a8fb83fe828c20c13a68` | Unchanged |
| Current producer | `af27586668c767de126af829c1131c6bae4634ad` | Unchanged |
| Handoff contract | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` | Unchanged |

The two authorized new paths were absent. No other path changed.

## Focused verification

Executed offline/mock checks only:

- unchanged K4R2 weather shadow module — **23 tests passed**;
- new K4R7 drivers shadow module — **19 tests passed**;
- combined focused result — **42 tests passed**;
- publisher and new test syntax compilation — **passed**;
- direct publisher import — **passed**;
- policy JSON validation — **passed**;
- workflow structural/control validation through focused tests — **passed**;
- `git diff --check` — **passed**.

No live OpenF1 request was made and no workflow was dispatched.

## Claim ceiling

K4R7 proves an inactive manual capability for source-preserving historical
drivers shadow capture. It does not prove a real drivers request ran,
authenticated publisher truth, historical availability before observation,
revision completeness, official FIA/F1 roster authority, a trustworthy final
grid, a real forecast, blind eligibility, stable-engine execution, production
enforcement, DR-002 activation, promotion, or accuracy improvement.

OpenF1 remains unofficial. Official FIA/F1/team facts override conflicting
driver or roster facts. DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast
gate remains **OFF**. Promotion remains **NOT ALLOWED**.
