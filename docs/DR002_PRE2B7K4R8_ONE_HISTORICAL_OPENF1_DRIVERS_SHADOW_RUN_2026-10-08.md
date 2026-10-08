# DR-002 pre-2B-7K4R8 — one historical OpenF1 drivers provenance-shadow run

**Work order:** #228 / `F1-WO-DR002-PRE2B7K4R8-001`  
**Evidence verdict:** `OPENF1_HISTORICAL_REST_CAPTURE_VALIDATED` within the narrow K4R8 shadow-evidence boundary  
**DR-002:** **PROPOSED — NOT ACTIVATED**  
**Forecast gate:** **OFF**  
**Promotion:** **NOT ALLOWED**

## Authorized action and exactly-one control

Issue #228 was created at `2026-10-08T21:09:36Z` and authorized exactly one browser-interface `workflow_dispatch` of `.github/workflows/f1-openf1-lightweight-source-closure.yml` on `main`.

Before dispatch:

- the latest manual run visible in the GitHub Actions interface was run #87 / `37775058587`, created earlier on 2026-10-08;
- no run of this workflow existed after Issue #228 authorization;
- the browser dispatch form explicitly showed branch `main`;
- the four submitted inputs were explicitly set to:
  - `season=2026`
  - `completed_only=true`
  - `provenance_shadow_session_key=11371`
  - `provenance_shadow_endpoint=drivers`.

The Run workflow submission control was clicked exactly once. A post-run repository Actions query found exactly one matching workflow-dispatch run after authorization: run `37845283040`. No rerun, failed-job rerun, second dispatch, alternate dispatcher, API dispatch, CLI dispatch, workflow mutation, or implementation repair was performed.

## Run identity

| Field | Observed value |
|---|---|
| Workflow | `F1 OpenF1 Lightweight Source Closure` |
| Workflow path | `.github/workflows/f1-openf1-lightweight-source-closure.yml` |
| Event | `workflow_dispatch` |
| Run ID | `37845283040` |
| Run number | `88` |
| Attempt | `1` |
| Branch / ref | `main` / `refs/heads/main` |
| Head SHA | `ca7a9646588daa567aafd350e86bec4a263a51ec` |
| Actor / triggering actor | `F1Lllewellyn` / `F1Lllewellyn` |
| Created / started UTC | `2026-10-08T21:13:48Z` |
| Completed API update UTC | `2026-10-08T21:15:12Z` |
| Run conclusion | `success` |
| GitHub UI total duration | `1m 24s` |

Run: https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37845283040

The run head is the verified PR #226 merge commit and contains the Issue #228 pins:

| Relevant dependency | Git blob |
|---|---|
| `.github/workflows/f1-openf1-lightweight-source-closure.yml` | `c32bd7bb2f8a84d1bb4e8995be246c389418f512` |
| `scripts/openf1/publish_openf1_lightweight_source_closure.py` | `f2e28d326255a48a48f873d101cd3e3e99955c1f` |
| `configs/openf1/openf1_lightweight_source_closure_policy.json` | `f386d8b6dd7025b313a1ea082ef699c4b1bd2e7c` |
| `tests/test_openf1_lightweight_source_closure_drivers_provenance_shadow_v1.py` | `97d3e8f2cfb8786410f13cb7fac40c11b1a91ee8` |
| `scripts/forecast_bundles/dr002_openf1_historical_rest_capture_v1.py` | `e68fa528cd73cd5c72afd97622a00d6e5b29be19` |
| `scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py` | `357ac56a6cfe317e21d9ce71d78c58683e444a5a` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

Before this documentation branch was created, current `main` had advanced to `9ae42ed8fb83e58f6c3b4fdf778785b124b5e7e5` through unrelated generated-output movement. All seven relevant blobs above remained exact.

## Job and step evidence

The sole job was `openf1-lightweight-source-closure`, job ID `113544515042`, and concluded `success`. GitHub reported these relevant step conclusions:

| Step | Conclusion |
|---|---|
| Reject drivers shadow without explicit session | `skipped` |
| Checkout repository | `success` |
| Set up Python | `success` |
| Install dependencies | `success` |
| Enforce main-only provenance shadow | `skipped` because the selected ref was already `refs/heads/main` |
| Run lightweight OpenF1 source closure publisher | `success` |
| Upload legacy source closure artifact | `skipped` |
| Upload historical REST provenance shadow artifact | `success` |
| Commit source closure outputs | `skipped` |
| Post Checkout repository | `success` |
| Complete job | `success` |

For this observed dispatch/session combination, the pinned workflow resolves checkout `persist-credentials` to false. The successful run therefore used the accepted shadow path without persisted checkout credentials. The skipped legacy-upload and commit steps, artifact contents, and manifest flags independently agree that no `latest/**`, `history/**`, commit, or push path ran.

## Artifact identity and archive safety

Exactly one artifact with the required name was attached to the run:

| Field | Observed / recomputed value |
|---|---|
| Name | `dr002-pre2b7k4r7-openf1-drivers-historical-rest-shadow` |
| Artifact ID | `11578953444` |
| GitHub reported size | `5182` bytes |
| Downloaded ZIP size | `5182` bytes |
| GitHub reported digest | `sha256:82a322bf126d3307f11267370f9eb5aab74d4bf0b7b962cba7db52da01ed33fc` |
| Recomputed ZIP SHA-256 | `82a322bf126d3307f11267370f9eb5aab74d4bf0b7b962cba7db52da01ed33fc` |
| Artifact created UTC | `2026-10-08T21:15:08Z` |
| Artifact expiry UTC | `2026-11-07T21:15:07Z` |
| Run-scoped logical path | `_runtime/dr002_pre2b7k4r2_openf1_historical_rest_shadow/gha-37845283040-1/` |

The ZIP central directory contained exactly five unique root members. Every member was a regular `100644` file; reading every member passed ZIP CRC verification. There were no duplicate names, directories, absolute paths, parent traversal, backslash path aliases, symlinks, nested members, or generated CSV files.

| Logical evidence file | Exact bytes |
|---|---:|
| `drivers.response.json` | 9166 |
| `source_capture_receipt.json` | 926 |
| `historical_rest_capture_assessment.json` | 1405 |
| `shadow_manifest.json` | 2175 |
| `shadow_report.md` | 1079 |

## Exact drivers evidence

The exact `drivers.response.json` bytes have SHA-256:

`66b3d285c5cfc388d488c14e59d03a3ca2f3bd910a7ad5c8ad3e76c7f91148fb`

Strict JSON parsing produced a nonempty list of 22 rows. Every row contained the K4R6 required fields `meeting_key`, `session_key`, `driver_number`, `broadcast_name`, `full_name`, and `team_name`; any optional fields were limited to the accepted K4R6 set, including optional `country_code`. Every row was scoped to meeting `1295` and session `11371`. Driver numbers were positive integers and unique:

`1, 3, 5, 6, 10, 11, 12, 14, 16, 18, 23, 27, 30, 31, 41, 43, 44, 55, 63, 77, 81, 87`

Observed row count: `22`.  
Observed unique-driver count: `22`.

The selected endpoint and canonical request URI were:

- endpoint: `drivers`
- URI: `https://api.openf1.org/v1/drivers?session_key=11371`
- deterministic source ID: `openf1:drivers:0616975c53e4d4534f26b9ad6d6931b5997ae5592e798fb0ac58c15734cb0ec7`.

The source ID equals `openf1:drivers:<sha256(canonical URI UTF-8 bytes)>`.

## Receipt, K4R1, and exact-byte binding

The source-capture receipt was canonical JSON and had:

- receipt type `source_capture`;
- no parents: `parent_receipt_ids=[]`;
- exact scope `event_id=2026_1295_azerbaijan_baku_baku`, `meeting_id=1295`, `session_id=11371`;
- the exact canonical URI and deterministic source ID above;
- `source_sha256=66b3d285c5cfc388d488c14e59d03a3ca2f3bd910a7ad5c8ad3e76c7f91148fb`;
- receipt ID `source_capture:ce0bbededd2ce695f078c4f77cc806b1fd3c2c0b78ca3b659ff3c9484eae840b`;
- exact canonical receipt-bytes SHA-256 `c8a276c6b34d4420456569d811b8440c360f0a3c80605efa5511d9f2dad52ac9`.

The recomputed raw hash matched the receipt, K4R1 assessment, and shadow manifest. The recomputed canonical receipt hash matched the K4R1 assessment and manifest. The receipt ID was revalidated from the accepted canonical receipt identity. No receipt was invented or replaced during verification.

K4R1 assessment status and manifest status both equal:

`OPENF1_HISTORICAL_REST_CAPTURE_VALIDATED`

## K4R6 independent in-memory recomputation

The unchanged accepted adapter at blob `357ac56a6cfe317e21d9ce71d78c58683e444a5a` was executed in memory against the exact captured raw bytes and exact persisted receipt bytes. It returned:

- status: `OPENF1_DRIVERS_PRODUCER_ADAPTER_VALIDATED`;
- row count: `22`;
- unique-driver count: `22`;
- derived CSV SHA-256: `884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424`;
- derived runtime identity: `derived:openf1-drivers-csv:884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424`;
- frozen-evidence-manifest SHA-256: `877d41594c59b55243e44d13af1919f207e5c6f44116fadc1bea56816af058ea`.

These values exactly matched the persisted K4R6 metadata. The derived CSV bytes existed only in verifier memory. No CSV was present in the artifact and no derived CSV was treated as raw evidence.

## Chronology

| Boundary / observation | UTC |
|---|---|
| Known session end | `2026-09-24T13:00:00Z` |
| Historical eligibility boundary | `2026-09-24T13:30:00Z` |
| First observed | `2026-10-08T21:15:07.487220Z` |
| Ingested | `2026-10-08T21:15:07.487592Z` |
| Receipt created | `2026-10-08T21:15:07.487611Z` |

The required ordering holds:

`eligible <= first_observed_utc <= ingested_utc <= receipt_created_utc`

The observation values bind across the receipt payload, K4R1 assessment, and manifest. They are local execution observations from this run. They are not an authenticated provider clock and were not backdated to the race weekend.

## Negative and mutation checks

The manifest records all of these as false:

- `derived_csv_persisted`
- `derived_csv_is_source_evidence`
- `new_scientific_receipt_created`
- `normalization_receipt_created`
- `verified_receipt_bindings_created`
- `historical_availability_before_first_observation_proven`
- `openf1_official_f1_roster_authority`
- `latest_or_history_written`
- `repository_mutation_performed`
- `dr002_activated`
- `promotion_allowed`.

The artifact contains no credentials, secrets, verified-receipt binding, `latest/**`, `history/**`, or CSV output. The GitHub commit/push step was skipped.

## Evidence classification and trust ceiling

Observed facts are the GitHub run/job/step identities and conclusions, the explicit browser form values, the artifact metadata, and the exact downloaded artifact bytes. Recomputed facts are archive safety, hashes, canonical JSON, schema/scope/count checks, chronology, deterministic identities, and unchanged-adapter output. The interpretation below is bounded by those observations and computations.

This run proves one hosted, historical OpenF1 drivers REST provenance-shadow capture through the already accepted K4R7 capability at the stated run head. It does **not** prove official FIA/F1 driver-roster authority, final-grid authority, authenticated provider truth, publisher/global revision completeness, historical availability before the local first observation, blind forecast eligibility, stable-engine execution, real forecast source composition, production enforcement, forecast lock/outcome/revision validation, DR-002 activation, model promotion, accuracy, or accuracy improvement.

No production model, stable engine, canonical workbook, prediction, processor/observer runway, paid real-time OpenF1, MQTT, streaming, token, Pipedream, Gmail, or alternate endpoint/session was used or changed.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion **NOT ALLOWED**.
