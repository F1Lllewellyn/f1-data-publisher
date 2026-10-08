# DR-002 pre-2B-7K4R3 — one historical OpenF1 REST provenance shadow run

Date: 2026-10-08  
Work order: `F1-WO-DR002-PRE2B7K4R3-001` / Issue #213  
Accepted predecessor: PR #211, merged as `4ac47b9b5d4439659fa2999ab611e85ec1564b41`  
Result: **K4R3 LIVE EXECUTION EVIDENCE — PASS**

## Evidence basis

This Work Result records the Adviser K4R3 independent live-run verification checkpoint attached to Issue #213. The Adviser independently inspected the qualifying GitHub Actions run, downloaded and checked its exact artifact, recomputed the relevant hashes and receipt identity, and verified the package semantics. Under the handoff contract's accepted-evidence and work-credit controls, this docs-only result uses that checkpoint without repeating broad run discovery, downloading or recomputing the accepted artifact evidence, or rerunning the workflow.

Exactly one qualifying human-dispatched run existed after K4R2 merge and Issue #213 authorization. The run used the authorized workflow on `main`, attempt 1, with the required K4R3 inputs: season `2026`, `completed_only=true`, and `provenance_shadow_session_key=11371`.

## Qualifying GitHub Actions run

| Fact | Observed value |
|---|---|
| Workflow | `.github/workflows/f1-openf1-lightweight-source-closure.yml` |
| Display name | `F1 OpenF1 Lightweight Source Closure` |
| Run ID | `37775058587` |
| Run number | `87` |
| Attempt | `1` |
| Event | `workflow_dispatch` |
| Branch / ref | `main` / `refs/heads/main` |
| Head SHA | `4ac47b9b5d4439659fa2999ab611e85ec1564b41` |
| Created / started | `2026-10-08T12:10:53Z` |
| Completed / updated | `2026-10-08T12:12:13Z` |
| Conclusion | `success` |
| Job ID | `113303717386` |
| Job name | `openf1-lightweight-source-closure` |
| Job started | `2026-10-08T12:10:57Z` |
| Job completed | `2026-10-08T12:12:12Z` |
| Job conclusion | `success` |

The actual run head contained every required landed dependency at its pinned blob:

| Relevant path | Blob SHA |
|---|---|
| `.github/workflows/f1-openf1-lightweight-source-closure.yml` | `506efa4098d3879fcd7374ae755c1daa4bb7f1d3` |
| `scripts/openf1/publish_openf1_lightweight_source_closure.py` | `6e29dac3587c4f1b06734edd75b0d2c429aec04a` |
| `configs/openf1/openf1_lightweight_source_closure_policy.json` | `8c3a4a52f37aa39b761a45bebfafa1dda7b2e252` |
| `tests/test_openf1_lightweight_source_closure_provenance_shadow_v1.py` | `bbe623a48322d273990dd34d05fedf133f1af828` |
| `scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py` | `e68fa528cd73cd5c72afd97622a00d6e5b29be19` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

Fresh `main` observed for this documentation change was `0d16e49e20f4547ee767bdfb5b11aaabbbc0d1d8`. Its only movement after the run head was unrelated scheduled `latest/cross_car_microdelta_forensics/**` and `history/cross_car_microdelta_forensics/**` output; it did not alter the run evidence or any declared relevant dependency.

## Job and shadow-path behavior

| Step | Conclusion | Interpretation |
|---|---|---|
| Set up job | success | Runner initialized. |
| Checkout repository | success | Run-head repository content checked out. |
| Set up Python | success | Python environment prepared. |
| Install dependencies | success | Required dependencies installed. |
| Enforce main-only provenance shadow | skipped | Correct for a run already executing on `main`; no rejection path was needed. |
| Run lightweight OpenF1 source closure publisher | success | The authorized historical provenance shadow executed. |
| Upload legacy source closure artifact | skipped | Legacy artifact path did not execute in shadow mode. |
| Upload historical REST provenance shadow artifact | success | The run-scoped K4R3 evidence package was uploaded. |
| Commit source closure outputs | skipped | The shadow path did not mutate the repository. |
| Post/complete steps | success | Job completed normally. |

No rerun, retry, or second dispatch was used.

## Artifact and archive verification

| Fact | Verified value |
|---|---|
| Artifact ID | `11549846922` |
| Name | `dr002-pre2b7k4r2-openf1-historical-rest-shadow` |
| GitHub-reported size | `4,620` bytes |
| GitHub digest | `sha256:11d756f5c8960298ec65fd628f7cf5129ca17e6e3c9e2091c09d8e21897ad332` |
| Independently downloaded ZIP SHA-256 | `11d756f5c8960298ec65fd628f7cf5129ca17e6e3c9e2091c09d8e21897ad332` |
| Digest comparison | Exact match |
| Run-scoped package | `_runtime/dr002_pre2b7k4r2_openf1_historical_rest_shadow/gha-37775058587-1/` |

The archive contained exactly five regular logical evidence files:

- `weather.response.json`
- `source_capture_receipt.json`
- `historical_rest_capture_assessment.json`
- `shadow_manifest.json`
- `shadow_report.md`

Independent archive inspection found no path traversal, duplicate-path, or symlink surprise.

## Exact weather/source evidence

| Fact | Verified value |
|---|---|
| Canonical request URI | `https://api.openf1.org/v1/weather?session_key=11371` |
| Event ID | `2026_1295_azerbaijan_baku_baku` |
| Meeting ID | `1295` |
| Session ID | `11371` |
| Exact response size | `18,359` bytes |
| Parsed weather rows | `85` |
| Exact response SHA-256 | `bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6` |

The exact response bytes formed valid, nonempty JSON weather data. Every exposed `session_key` was `11371`, and every exposed `meeting_key` was `1295`. The manifest's raw-response hash matched the exact persisted/read-back `weather.response.json` bytes.

The raw SHA and byte count match the payload observed in prior Baku provenance work. K4R3 proves only this new local historical REST observation; that match does not prove the bytes were available earlier.

## Temporal interpretation

| Fact | Verified value |
|---|---|
| Session end | `2026-09-24T13:00:00Z` |
| Historical-window eligibility | `2026-09-24T13:30:00Z` |
| First observed | `2026-10-08T12:12:09.784033Z` |
| Ingested | `2026-10-08T12:12:09.784372Z` |
| Receipt created | `2026-10-08T12:12:09.784388Z` |
| Documented historical-window condition | `true` |

The eligibility boundary is exactly session end plus 1,800 seconds. The chronology is valid:

`historical_window_eligible_utc <= first_observed_utc <= ingested_utc <= receipt_created_utc`

These are local execution observations. The observation clock is not authenticated, and no timestamp or payload match is used to backdate observation or claim earlier availability.

## K4R1 assessment and receipt

| Fact | Verified value |
|---|---|
| Assessment status | `OPENF1_HISTORICAL_REST_CAPTURE_VALIDATED` |
| Manifest status | `OPENF1_HISTORICAL_REST_CAPTURE_VALIDATED` |
| Manifest `k4r1_status` | `OPENF1_HISTORICAL_REST_CAPTURE_VALIDATED` |
| Receipt type | existing `source_capture` |
| Parent receipt IDs | `[]` |
| Exact receipt-file SHA-256 | `02313f69842b30c1a8a3e2d682c474e0474dc581cb67f2305937dc9b8111e431` |
| Canonical vs exact receipt bytes | Identical; canonical SHA equals exact file SHA |
| Recomputed receipt ID | `source_capture:0bdb0098ea88ea420f70d7e71630c90091513476c91746365b2a9c2d168a748f` |
| Receipt ID comparison | Exact match |

The receipt source URI, source SHA, event/session scope, capture reference, and implementation identification matched the exact run evidence. The receipt source SHA matched the exact raw weather bytes, and `capture_ref` identified the run-scoped raw response file. The stored receipt remained parentless and used the existing Gate 2B-1 receipt schema.

No `verified_receipt_bindings` object was created; the manifest explicitly records `verified_receipt_bindings_created=false`. No new scientific receipt type was introduced.

## Negative and safety findings

- No shadow `latest/**` or `history/**` output was created or committed.
- The repository commit/push step was skipped; the shadow path caused no repository mutation.
- The evidence package contained no OpenF1 credential, password/token material, MQTT, WebSocket, self-hosted OpenF1, or paid/live dependency.
- No GitHub or Sigstore attestation claim is made.
- No implementation, workflow, policy, stable-engine, model, or protected logic changed in this Work Result.

## Result and claim ceiling

K4R3 proves only that:

- the accepted K4R2 integration executed once in GitHub Actions;
- one exact historical OpenF1 weather response for session `11371` was observed after the documented historical-window boundary;
- those exact response bytes were persisted, read back, and hash-bound;
- the unchanged K4R1 contract accepted those exact bytes and emitted the exact stored parentless `source_capture` receipt; and
- the runtime manifest, assessment, and receipt were internally consistent with the observed run and artifact.

K4R3 does **not** prove an authenticated observation clock, availability before the recorded local observation, OpenF1 publisher cryptographic authenticity, publisher/global revision completeness, official FIA/F1 source authority, stable-engine execution, blind predictive eligibility, production source-closure rollout, production forecast-lock/outcome/revision enforcement, DR-002 activation, model promotion, or accuracy improvement.

OpenF1 remains an unofficial source and does not outrank official FIA/F1/team/Pirelli evidence.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion **NOT ALLOWED**.
