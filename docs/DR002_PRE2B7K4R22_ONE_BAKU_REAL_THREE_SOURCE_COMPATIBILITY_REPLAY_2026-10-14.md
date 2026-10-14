# DR-002 pre-2B-7K4R22 one real Baku three-source compatibility replay

**Work order:** Issue #262 / `F1-WO-DR002-PRE2B7K4R22-REPLAY-001`

**Result:** `OPENF1_THREE_SOURCE_EVENT_COMPATIBILITY_VALIDATED_POST_EVENT_MECHANICS_ONLY_NOT_A_PREDICTION`

**Classification:** `POST_EVENT_MECHANICS_ONLY_NOT_A_PREDICTION`

**DR-002:** PROPOSED — NOT ACTIVATED

**Forecast gate:** OFF

**Promotion:** NOT ALLOWED

## Execution record

One and only one call to
`assess_openf1_three_source_event_compatibility` was made using the exact
original bytes read in memory from the three verified GitHub Actions artifact
ZIPs below. No prior identical K4R22 execution record was present.

- execution started: `2026-10-14T18:09:28.165825Z`;
- execution completed: `2026-10-14T18:09:28.170699Z`;
- call count: **exactly 1**;
- execution Git head: `e12f3336d1ca198e0c67fc22554926932e892485`;
- K4R21 function Git blob: `f0850f4c13132b213f03a2b1aeaea01acebe2bf8`;
- reason codes: `[]`;
- canonical deterministic result JSON SHA-256:
  `34526b010972bc2e51af0cb095d3601802e21e40aedb415d434efccc052a2c6c`.

The result digest is over UTF-8 JSON with keys sorted, compact separators,
non-ASCII preserved, and non-finite values rejected. The complete returned
metadata was retained only in the private disposable sandbox for readback and
digest verification; no raw response, receipt, driver name, or row payload is
published here.

## Original artifact verification

| Role | Run | Artifact | ZIP bytes | Whole-ZIP SHA-256 | Members |
| --- | ---: | ---: | ---: | --- | ---: |
| Weather / Practice 2 | `37775058587` | `11549846922` | 4,620 | `11d756f5c8960298ec65fd628f7cf5129ca17e6e3c9e2091c09d8e21897ad332` | 5/5 exact |
| Drivers / Practice 2 | `37845283040` | `11578953444` | 5,182 | `82a322bf126d3307f11267370f9eb5aab74d4bf0b7b962cba7db52da01ed33fc` | 5/5 exact |
| Starting grid / Qualifying | `38548009086` | `11885033135` | 7,992 | `9c3af9b3e0b2c701aa2b77c53cb976aa702dc1896577827ae57086283d65ae1b` | 6/6 exact |

All three archives passed byte-length and whole-ZIP digest checks, exact member
set and case checks, CRC validation, duplicate/path-traversal/absolute-path
checks, directory and symlink rejection, and private readback. No provider,
FIA, or other source request was made.

## Source and session identities

Event `2026_1295_azerbaijan_baku_baku`, meeting `1295`:

| Role | Source session | Target | Original rows | Raw source ID | Raw SHA-256 | Canonical source receipt ID |
| --- | --- | --- | ---: | --- | --- | --- |
| Weather | Practice / Practice 2 `11371` | Race `11377` | 85 | `openf1:weather:7f0dd3ec9bada87879adac918d747e7af0434f17de65901101aed1c52a784fd3` | `bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6` | `source_capture:0bdb0098ea88ea420f70d7e71630c90091513476c91746365b2a9c2d168a748f` |
| Drivers | Practice / Practice 2 `11371` | Race `11377` | 22 | `openf1:drivers:0616975c53e4d4534f26b9ad6d6931b5997ae5592e798fb0ac58c15734cb0ec7` | `66b3d285c5cfc388d488c14e59d03a3ca2f3bd910a7ad5c8ad3e76c7f91148fb` | `source_capture:ce0bbededd2ce695f078c4f77cc806b1fd3c2c0b78ca3b659ff3c9484eae840b` |
| Starting grid | Qualifying / Qualifying `11373` | Race `11377` | 22 | `openf1:starting_grid:42a1e7d49fd26ba241fb3c48aea5e615bde90f7f7f4f0757e125a97f517c6cd4` | `23d798ed27e99138c6bcc61e6efbc557a4022f18ea874dee489f98b6f571cda9` | `source_capture:ab36241b7276bddff68cd33ff37209d0a5f3a7aa214749316aecb22c7b6858e4` |

The exact 131-row session-discovery response SHA-256 was
`f76bc38e3326eec1d43b5108e323dc197f1b690cd9e505c47210414de819e61b`.
It preserved Practice 2 `11371`, Qualifying `11373`, and Race `11377` as three
distinct identities with the accepted event chronology. The grid manifest
recorded both requests as literal `true` and both HTTP status codes as integer
`200`; its exact input-byte SHA-256 was
`8a3e7bf6ddc6b2fa191d4109326601584d359e61f1a3ef68552f03ab2a47d76f`.

The original receipt-byte SHA-256 values were:

- weather: `02313f69842b30c1a8a3e2d682c474e0474dc581cb67f2305937dc9b8111e431`;
- drivers: `c8a276c6b34d4420456569d811b8440c360f0a3c80605efa5511d9f2dad52ac9`;
- starting grid: `a405f6908095d6ac1f37388425b6f2705eb81a020aaebf7a926b9ca630a71d2d`.

Each receipt was independently rehashed as a canonical parentless source
receipt and bound to its exact raw SHA before the call.

## Actual compatibility result

The assessment returned `VALIDATED` under its full post-event-mechanics-only
status. It reported 85 weather rows, 22 unique driver rows, 22 unique grid
rows, and contiguous grid slots 1–22 with exact driver-number roster parity.
The three deterministic derived CSV SHA-256 values were:

- weather: `ef19f099e1f52e793f23186d57aef9049019e0282b150287351739435bc3e540`;
- drivers: `884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424`;
- starting grid: `16ff7a35f2ddb45eba24e566e4144f1215a28e16bda5384046daf98183fd531c`.

The original first-observed timestamps were preserved as:

- weather: `2026-10-08T12:12:09.784033Z`;
- drivers: `2026-10-08T21:15:07.487220Z`;
- starting grid: `2026-10-14T10:14:27.291789Z`.

All are after the Race ended at `2026-09-26T13:00:00+00:00`. All three raw
frozen-evidence binding statuses remain `UNBOUND`, and the distinct source
receipts and raw source identities remain separate from their derived runtime
identities.

## Claim ceilings and scientific limitations

Readback of the recorded result verified all of these fields are exactly
`false`:

- `combined_frozen_producer_manifest_created`;
- `cross_session_producer_join_authorized`;
- `producer_execution_attempted`;
- `historical_pre_race_availability_proven`;
- `official_fia_final_grid_authenticated`;
- `blind_validation_eligible`;
- `new_scientific_receipt_created`;
- `verified_receipt_bindings_created`;
- `stable_engine_execution_proven`;
- `production_forecast_generated`;
- `dr002_activated`; and
- `promotion_allowed`.

This result establishes only that the three genuine archived sources are
mechanically compatible at event level under the accepted offline contract.
It does not establish pre-race availability, an authenticated FIA final grid,
a valid forecast freeze, a cross-session producer join, prediction accuracy,
blind validation, a forecast, or production readiness. No producer, composer,
model, forecaster, stable engine, or workflow was executed.

## Dependency and publication controls

The execution head contained the exact accepted blobs for the K4R21 assessor
and every pinned dependency:

- compatibility assessor `f0850f4c13132b213f03a2b1aeaea01acebe2bf8`;
- weather adapter `5061d8007d06c37e164df2c6cc643e385be885f8`;
- drivers adapter `357ac56a6cfe317e21d9ce71d78c58683e444a5a`;
- starting-grid adapter `702a1219c4b97450d7aeec16b5dd8409f2b73d75`;
- K4R9 composer `f69a5ac49b6e3055cd13472037f8b49e8ea41265`;
- frozen-evidence contract `8dfd855184b172ce88235ee7de3ea33a68031b2e`;
- protected producer `af27586668c767de126af829c1131c6bae4634ad`;
- K4R19 publisher `dbbc36dc01737084f2b1ff332e26c6c270be0049`; and
- handoff contract `85ce44807ef159b5ba5d3bfd543ea1f945097f77`.

The sole Work Result path is
`docs/DR002_PRE2B7K4R22_ONE_BAKU_REAL_THREE_SOURCE_COMPATIBILITY_REPLAY_2026-10-14.md`.
The final document bytes are independently hashed and read back after GitHub
publication; the resulting Git blob and SHA-256 are recorded in the Work
Result PR because embedding either digest here would change the document.
