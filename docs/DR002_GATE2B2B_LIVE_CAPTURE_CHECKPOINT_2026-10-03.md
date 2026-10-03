# DR-002 Gate 2B-2B — one live capture checkpoint

Classification: **CAPTURED_UNBOUND**. DR-002 remains **PROPOSED — NOT ACTIVATED**.

## Evidence attribution

The following GitHub runtime and independently inspected artifact facts were
supplied in the user's verified Gate 2B-2B handoff. This Gate 2B-3A PR records that
handoff; it did not dispatch, retrieve or independently re-audit the live artifact.
The sole observation was made by the GitHub Actions runner, not a local substitute.

| GitHub runtime fact | Value |
|---|---|
| Workflow run | `37133694090` |
| Run attempt | `1` |
| Run head SHA | `5f25e048edeb6e46a5a77e70c5c97857a59f6bb6` |
| Artifact | `dr002-weather-capture-37133694090-1` |
| Artifact ID | `11277594100` |
| Dispatch count | Exactly one |
| Repository mutation by provenance workflow | None |

Run: https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37133694090

## Independently inspected artifact facts in supplied handoff

| Scope/content fact | Value |
|---|---|
| Source | OpenF1 weather |
| Request | `https://api.openf1.org/v1/weather?session_key=11371` |
| event_id | `2026_1295_azerbaijan_baku_baku` |
| meeting_id | `1295` |
| session_id | `11371` |
| Raw byte count | `18359` |
| Row count | `85` |
| Exact raw source SHA-256 | `bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6` |
| Normalized SHA-256 | `0bcdab4dcb6ce16e96bbb6bef6f6bc15e7e04ded360466b8aa7e692947ec764c` |
| Canonical receipt SHA-256 | `1cae5a9cf6a10491b88cc05221db65d5790fdc1128cd5c58909cd097a389e42d` |
| Receipt ID | `source_capture:5b0c88919ac0fa608e4b6f00ab801742e36c0e6c00acaeee183a30576e5ec9d9` |

| Observation timestamp | Exact UTC value |
|---|---|
| request_started_utc | `2026-10-03T15:36:42.865228Z` |
| response_completed_utc | `2026-10-03T15:36:43.566557Z` |
| first_observed_utc | `2026-10-03T15:36:43.566557Z` |
| ingested_utc | `2026-10-03T15:36:43.566993Z` |
| receipt_created_utc | `2026-10-03T15:36:43.567917Z` |

The supplied values satisfy request start <= response completion = first
observation <= ingestion <= receipt creation. Raw and normalized hashes refer to
different representations; normalized bytes cannot replace exact HTTP body bytes.

## Claims not proven

- binding_status = `UNBOUND`
- production_authenticated = `false`
- historical_availability_proven = `false`
- dr002_activated = `false`

This establishes the supplied observation/persistence mechanics only. Historical
weather row dates do not prove earlier availability. Authentication, future
forecast eligibility, durable authenticated storage, production readiness,
accuracy and stable-engine execution are NOT proven. GitHub artifact storage is
not asserted to be the future durable authenticated store. No raw payload is
copied into this repository. No verified_receipt_bindings are created.

No provenance-workflow commit/push, latest/history/ledger/workbook mutation,
forecast or downstream consumer execution occurred according to the verified
handoff. Unrelated scheduled output activity is separate. Stable engine and
canonical workbook remain protected; forecast gate OFF; promotion NOT ALLOWED.
