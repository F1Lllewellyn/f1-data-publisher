# DR-002 pre-2B-7K4R2 — OpenF1 source-closure provenance shadow integration

Date: 2026-10-07  
Work order: `F1-WO-DR002-PRE2B7K4R2-001` / Issue #210  
Status: implementation capability only

## Result

The accepted K4R1 hosted-OpenF1 historical REST capture contract is integrated into the existing lightweight source-closure publisher as a manual, non-default shadow path. No second ingestion architecture is introduced.

The workflow input `provenance_shadow_session_key` defaults to empty. Empty input, including scheduled execution, retains the existing legacy source-closure path. A non-empty manual input is restricted to `refs/heads/main`, runs only the historical provenance shadow, uploads only its run-scoped runtime package, and cannot execute the legacy commit/push step.

## Bounded shadow scope

K4R2 captures exactly one endpoint, `weather`, for exactly one uniquely selected historical session. Session discovery at `/sessions?year=<season>` is control metadata only and receives no `source_capture` receipt.

The selected discovery record must provide a matching unique `session_key`, `meeting_key`, `year`, `country_name`, `location`, `circuit_short_name`, and timezone-aware `date_end`. The weather request is prohibited until runtime UTC is at least 1,800 seconds after `date_end`.

Canonical event identity remains:

`<year>_<meeting_key>_<slug(country_name)>_<slug(location)>_<slug(circuit_short_name)>`

The fixed Baku regression is `2026_1295_azerbaijan_baku_baku`.

## Exact-byte sequence

1. Discover the exact selected session through hosted OpenF1 REST.
2. Confirm the historical-window boundary before the evidence request.
3. Request exactly `https://api.openf1.org/v1/weather?session_key=<selected>`.
4. Preserve `response.content` before any JSON/DataFrame reserialization.
5. Record `first_observed_utc` only after complete response bytes exist.
6. Persist and read back the exact response bytes; only then record `ingested_utc`.
7. Record `receipt_created_utc` and call the unchanged K4R1 contract with the exact bytes, HTTP status, scope, session end, request parameters, and timestamps.
8. Require `OPENF1_HISTORICAL_REST_CAPTURE_VALIDATED`.
9. Persist the returned canonical `source_capture_receipt_bytes` unchanged and verify its readback and SHA-256.
10. Publish parsed row facts only after K4R1 validation.

No HTTP Date header, row timestamp, or later retrieval is used to backdate first observation or historical availability.

## Runtime package

The manual shadow writes only beneath:

`_runtime/dr002_pre2b7k4r2_openf1_historical_rest_shadow/gha-<run_id>-<attempt>/`

Successful packages contain:

- `weather.response.json` — exact hosted REST response bytes;
- `source_capture_receipt.json` — exact K4R1 canonical receipt bytes;
- `historical_rest_capture_assessment.json` — JSON-safe K4R1 assessment without duplicated raw byte objects;
- `shadow_manifest.json` — repository/workflow/ref/head/run/attempt, event/meeting/session, canonical URI, byte/receipt hashes, timestamps, row count, historical-window result and K4R1 status;
- `shadow_report.md` — bounded status and claim ceiling.

HOLD diagnostics remain run-scoped. The shadow writes no `latest/**` or `history/**` content and performs no repository commit or push.

## Fail-closed behavior

The shadow returns nonzero/HOLD for an absent or ambiguous session, malformed metadata, a pre-window session, non-200 or malformed/foreign-scope response, exact-byte readback mismatch, K4R1 HOLD, receipt mismatch, or GitHub workflow identity mismatch. It does not fall back to a meeting-wide query, another session, another endpoint, legacy normalization, paid live access, MQTT/WebSocket, credentials, tokens, or self-hosted OpenF1.

## Verification boundary

The focused suite is offline/mocked. It covers legacy/default routing, schedule/manual input behavior, main-only enforcement, no shadow commit/push, exact session selection, the +1,800-second boundary, Baku identity, exact request/response bytes, observation ordering, unchanged K4R1 composition, HOLD propagation, exact receipt persistence, manifest hashes, existing receipt type, absence of fabricated verified bindings, absence of live/credential/self-hosted paths, runtime-only writes, policy ceilings, and dependency pins.

Only focused tests plus cheap Python syntax/import, JSON and YAML checks are authorized. No live OpenF1 request or workflow dispatch is part of K4R2.

Local verification completed before publication:

- 23 K4R2 integration tests passed;
- 26 unchanged K4R1 contract tests passed;
- Python syntax/import, JSON parsing, YAML parsing, and whitespace/diff checks passed;
- all tests used synthetic or mocked data and made no real OpenF1 request.

## Claim ceiling

K4R2 proves only that a bounded integration capability exists. It does not prove a live historical run, authenticated observation clock, earlier availability of later-retrieved bytes, publisher completeness or authenticity, official FIA/F1 authority, stable-engine execution, blind eligibility, production enforcement, model accuracy, DR-002 activation, or promotion.

OpenF1 remains an unofficial source and does not outrank official FIA/F1/team/Pirelli evidence.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion **NOT ALLOWED**.
