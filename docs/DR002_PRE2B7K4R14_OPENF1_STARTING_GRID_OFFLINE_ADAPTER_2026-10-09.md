# DR-002 pre-2B-7K4R14 — offline provenance-backed OpenF1 starting-grid adapter

**Date:** 2026-10-09

**Work order:** `F1-WO-DR002-PRE2B7K4R14-001` / Issue #244

**Status:** offline adapter capability only

**DR-002:** PROPOSED — NOT ACTIVATED

**Forecast gate:** OFF

**Promotion:** NOT ALLOWED

## Purpose

This checkpoint adds one pure in-memory adapter from an already captured OpenF1
`starting_grid` JSON response into the existing producer's `starting_grid.csv`
shape. It validates provenance before deriving bytes. It does not capture a
source, execute the producer or model, authenticate an FIA grid, establish a
historical as-of fact, or activate DR-002.

The exact raw JSON bytes and their existing parentless Gate 2B-1
`source_capture` receipt remain the evidence. The CSV is a deterministic,
separately hashed runtime representation and is never substituted for the raw
source evidence.

## Provider contract and authority ceiling

The accepted Adviser research used OpenF1's documented **Starting grid** REST
contract:

- request: `GET /v1/starting_grid?session_key=<explicit race session key>`;
- exact documented response columns: `position`, `driver_number`,
  `lap_duration`, `meeting_key`, and `session_key`;
- provider timing statement: data becomes available after official F1 results.

OpenF1 is a provider-documented but unofficial source. Its historical,
personal/non-commercial access statement is not an authorization to redistribute
underlying F1 data or use it commercially. This adapter records the provider
category as `UNOFFICIAL_OPENF1_DOCUMENTED_REST` and makes no commercial or
redistribution permission claim.

The official Formula1.com Australia 2026 grid was a human-reviewed contextual
reference only. Formula1.com is not integrated or scraped here because its
results/timing data and site terms restrict automated extraction and AI use.

## FIA 403 containment

The accepted K4R12 manual FIA capture capability remains unchanged and
quarantined. Its single authorized K4R13 run received HTTP 403 with HTML rather
than a PDF and correctly produced HOLD diagnostics without a receipt or
attestation.

That access denial must not be evaded. This checkpoint does not retry it, alter
headers, rotate network origins, probe alternate FIA hosts, or weaken the
capture contract. Choosing a documented provider API for a separate offline
adapter is not a bypass and does not upgrade OpenF1 to FIA authority.

## Pure adapter interface

`adapt_openf1_starting_grid_to_producer_input` accepts keyword-only values:

- exact canonical parentless `source_capture` receipt bytes;
- exact raw OpenF1 `starting_grid` response bytes;
- explicit `event_id`, `meeting_id`, and `session_id`;
- literal `session_kind="Race"`.

The function has no filesystem, network, clock, environment, subprocess,
workflow, PDF, browser, discovery, producer, or model access. Missing required
keyword arguments remain programming errors. Invalid supplied values return a
deterministic `HOLD` without partial evidence or derived output.

## Provenance validation

Before parsing grid rows, the adapter:

1. requires exact nonempty `bytes` for both receipt and raw response;
2. rejects duplicate JSON keys, malformed JSON, nonfinite values, foreign
   envelope shapes, and noncanonical receipt serialization;
3. calls the unchanged Gate 2B-1 `validate_receipt_envelope` and
   `verify_temporal_bindings` functions;
4. requires a parentless `source_capture` receipt and an exact supplied scope;
5. independently recomputes the deterministic receipt identity;
6. binds the exact raw-byte SHA-256 to `payload.source_sha256`;
7. requires the exact canonical OpenF1 request URI for
   `starting_grid?session_key=<session_id>` and the corresponding
   `openf1:starting_grid:<canonical-URI-SHA256>` source ID; and
8. calls the unchanged `dr002-frozen-evidence` builder with an explicit
   in-memory reader, then independently validates its `UNBOUND` manifest.

No arbitrary URL, query alias, alternate provider, misleading source ID,
unknown receipt, parented receipt, or newly asserted binding is accepted.

## Grid validation

The raw response must be a nonempty JSON array of no more than 26 objects. Each
object must contain exactly the five documented fields.

- `position` and `driver_number` must be positive integers, never booleans;
- positions and driver numbers must each be unique;
- positions must be exactly contiguous `1..N`;
- `lap_duration` must be `null` or a finite nonnegative integer/float;
- `meeting_key` and `session_key` must be positive integers or canonical decimal
  strings matching the explicit scope; and
- the driver universe is dynamic rather than fixed at 22.

Pit-lane starts, holes, withdrawals, null slots, dual grid documents, and mixed
source revisions cannot be represented by this five-column contract without
additional semantics. They therefore HOLD rather than being normalized,
filled, reordered into invented slots, or silently discarded.

## Derived producer input

On validation, the adapter returns UTF-8/LF CSV bytes with the exact header:

```text
driver_number,position,event_id,meeting_id,session_id
```

Rows are sorted by numeric grid position. The CSV has its own SHA-256 and the
identity `derived:openf1-starting-grid-csv:<sha256>`. Raw JSON row ordering may
change the raw source and receipt hashes without changing the position-sorted
derived CSV. The frozen evidence manifest binds only the raw receipt and exact
raw response bytes, never the derived CSV.

## Temporal and session barrier

OpenF1 makes starting-grid rows available after official results. A later
historical capture cannot prove that the same bytes or revision existed before
a forecast cutoff. The adapter therefore makes no earliest-availability,
pre-race, blind-validation, or revision-completeness claim.

The explicit `session_kind="Race"` is a caller assertion, not authenticated
session discovery. Practice, Sprint, and Qualifying classifications are
rejected. Most importantly, K4R10's archived weather and drivers evidence is
Baku Practice 2 (`meeting_id=1295`, `session_id=11371`). A race-session starting
grid necessarily has another session ID. These scopes must not be joined as if
they match. This checkpoint does not compose any sources or approve a
cross-session event-feature contract.

## Claim ceilings

Every successful result explicitly keeps these claims false:

- official FIA grid authenticated;
- official final grid verified;
- source earliest availability verified;
- historical pre-race availability proven;
- race-session authority authenticated;
- derived CSV is source evidence;
- verified receipt bindings created;
- new scientific receipt created;
- blind validation eligible;
- stable-engine execution proven;
- production forecast generated;
- DR-002 activated; and
- promotion allowed.

## Verification

Focused offline mock tests cover the valid documented shape, exact derived CSV
and identities, raw-row order invariance, canonical receipt and URI/source-ID
binding, frozen-manifest reuse, dynamic contiguous slots, nullable
`lap_duration`, malformed and adversarial JSON/receipt cases, scope and session
barriers, trust ceilings, immutable dependency fingerprints, and static absence
of live I/O or execution capabilities.

No OpenF1/FIA/Formula1.com request, FIA PDF download, GitHub Actions dispatch,
producer/model/stable-engine execution, workbook mutation, or `latest/**` or
`history/**` change occurred in this checkpoint.

## Future authorization required

A genuine historical OpenF1 `starting_grid` capture, authenticated compatible
race-session discovery, independent evidence review, any cross-source
composition, producer replay, temporal eligibility decision, or promotion
requires a separate explicit authorized work order.
