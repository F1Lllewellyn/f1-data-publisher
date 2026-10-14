# DR-002 pre-2B-7K4R21 Baku three-source temporal compatibility

**Status:** offline event-compatibility contract only

**DR-002:** PROPOSED — NOT ACTIVATED

**Forecast gate:** OFF

**Promotion:** NOT ALLOWED

## Purpose

K4R21 adds a pure, in-memory gate that can assess whether separately captured
OpenF1 weather, drivers and starting-grid evidence is mechanically compatible
at the same event. It does not compose producer inputs or run a producer. It
preserves the original source identities:

- weather and drivers: Practice 2 source session;
- starting grid: distinct Qualifying source session; and
- target: distinct later Race session linked only by provider discovery.

The only successful classification is
`POST_EVENT_MECHANICS_ONLY_NOT_A_PREDICTION`. It requires every source to have
been first observed after the Race ended. It therefore cannot establish
prospective availability, blind eligibility, a valid forecast freeze, or an
accuracy improvement.

## Validation boundary

The contract accepts only explicit immutable bytes and canonical identifiers.
It invokes the unchanged accepted weather, drivers and Qualifying-grid adapters
and requires all three to validate their parentless source-capture receipts,
exact raw hashes, canonical OpenF1 request identities, deterministic derived
CSV identities and `UNBOUND` frozen-evidence trust.

It separately validates the exact grid-run session-discovery bytes against the
supplied shadow manifest. The discovery must contain one non-cancelled
`Practice/Practice 2`, one `Qualifying/Qualifying` and one `Race/Race` for the
same meeting, year, country, location and circuit, with strict chronology:

`Practice 2 end < Qualifying start < Qualifying end < Race start < Race end`.

Sprint or multi-qualifying structures, ambiguous/missing sessions, malformed
UTC times, altered manifest hashes, source/receipt mismatches and claim-ceiling
changes all HOLD. Driver numbers come only from validated adapter CSVs. The
drivers and grid sets must match exactly, and grid positions must be contiguous
without padding, filler or backfill.

## Result semantics

A validated result contains bounded, JSON-serializable metadata only: explicit
session roles and IDs, provider-only event link, separate receipt/source/raw and
derived hashes, row/driver counts, first-observation timestamps and inherited
false claim flags. It returns no original or derived bytes, no driver names, no
combined frozen producer manifest and no new receipt or binding.

Every HOLD result is deliberately minimal: status, one reason, and false
scientific/operational flags. It discloses no partial source identity, receipt,
hash, driver name, CSV or frozen evidence from rejected input.

## Scientific and execution limits

The gate does not authenticate an official FIA final grid, prove a provider's
revision history or pre-race availability, authorize a cross-session producer
join, alter the K4R9 same-session contract, or claim that a three-source replay
occurred. It performs no filesystem discovery, network access, GitHub/API call,
clock observation, subprocess, workflow dispatch, producer, model, forecaster,
stable-engine or repository-output operation.

All committed tests use small synthetic mock receipts and provider-shaped JSON.
No original OpenF1 artifact or raw provider byte is published by K4R21.

## Control-board interpretation

Engineering readiness remains **89/100 PROVISIONAL**. K4R21 is a mock/offline
compatibility gate and earns no additional readiness point. The protected
`Engine_2026-06-07_STABLE` remains unchanged.
