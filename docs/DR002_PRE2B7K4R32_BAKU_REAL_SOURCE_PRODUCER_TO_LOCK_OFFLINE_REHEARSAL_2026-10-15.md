# DR-002 pre-2B-7K4R32 real-Baku producer-to-lock offline rehearsal

**Work order:** Issue #288 / `F1-WO-DR002-PRE2B7K4R32-REAL-TO-LOCK-001`

**Result:** `HOLD_POST_PRODUCER_PAYLOAD_NOT_RETAINED_CRLF_VERIFIER_MISMATCH`

**Producer invocation count:** **1 — exhausted; do not retry**

**Gate 2B-4 lock-constructor invocation count:** **0**

**DR-002:** PROPOSED — NOT ACTIVATED

**Forecast gate:** OFF

**Promotion:** NOT ALLOWED

## Result and stopping point

The sole authorized producer invocation ran in a private disposable sandbox.
It returned exit `0`, emitted empty stderr, and passed the integration harness's
readback checks through the producer audit, frozen-input binding, event/session
scope, gate/lane, broad-discovery prohibition and negative trust claims.

The next check rejected the generated `forecast_rows.csv` because the private
harness incorrectly required LF-only output. The unchanged producer writes CSV
through Python `csv.DictWriter` with its default CRLF record terminator. This is
compatible with the accepted K4R25 reader, but not with the new private
rehearsal reader.

The sandbox cleanup guard then disposed the generated payload before its exact
bytes, generation timestamp, size and SHA-256 were preserved. Those facts
cannot now be recovered truthfully without a second producer invocation. Issue
#288 prohibits a retry. Therefore the exact payload cannot be supplied to
`build_forecast_lock`, and the rehearsal stops on HOLD with **zero** lock-
constructor calls.

This is a private harness failure, not evidence that the producer, Gate 2B-4
constructor, source evidence or scientific contract is defective. No code fix
is authorized or proposed in this Work Result.

## Preflight evidence

The result path was absent on fresh `main`. The observed execution head was
`b8249cf2004a2ba67c4c5ae0a6c87a299e241c7c`. The checkout was clean before
execution. No prior K4R32 marker, result, issue comment, documentation result or
PR was found.

All ten work-order dependency blobs matched:

| Dependency | Git blob |
| --- | --- |
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | `af27586668c767de126af829c1131c6bae4634ad` |
| `scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py` | `064d93ee5ae30354590a3fb95be598c5fe8b3b9a` |
| `scripts/forecast_bundles/forecast_integrity_contract_v1.py` | `9f5a3585814f4e5eb7a1f95ecdada90a33090857` |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| `scripts/forecast_bundles/dr002_forecast_lock_shadow_pilot_v1.py` | `1ef04022041c7dcf625ae10c051c23b35ed72a9d` |
| `scripts/forecast_bundles/dr002_openf1_weather_producer_adapter_v1.py` | `5061d8007d06c37e164df2c6cc643e385be885f8` |
| `scripts/forecast_bundles/dr002_openf1_drivers_producer_adapter_v1.py` | `357ac56a6cfe317e21d9ce71d78c58683e444a5a` |
| `scripts/forecast_bundles/dr002_openf1_starting_grid_producer_adapter_v1.py` | `702a1219c4b97450d7aeec16b5dd8409f2b73d75` |
| `scripts/forecast_bundles/dr002_openf1_three_source_grid_projection_v1.py` | `63ae055aa54c9d9cbe12772c99301a41496863ab` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

The projection helper's accepted transitive K4R21 import was also present at
blob `f0850f4c13132b213f03a2b1aeaea01acebe2bf8`.

Inspection of the current exact Gate 2B-4 and Gate 2B-1 code established that
an unbound, post-event `producer_execution` receipt can truthfully bind the
three existing source-capture receipts, actual producer identity, Gate 2A
manifest hash and exact payload bytes. `build_forecast_lock` can then bind the
same exact payload without external bindings, authenticated clocks, stable-
engine claims or production activation. No `HOLD_INTEGRATION_CONTRACT_GAP` was
present before execution.

## Original accepted source evidence

No artifact was downloaded and no provider or workflow was contacted. The
three retained original archives were re-read and matched their accepted
whole-ZIP, raw-source, receipt-byte, receipt-identity and scope bindings.

| Role | Original artifact | Source session | ZIP SHA-256 | Raw SHA-256 | Receipt-bytes SHA-256 |
| --- | ---: | --- | --- | --- | --- |
| Weather | `11549846922` | Practice 2 `11371` | `11d756f5c8960298ec65fd628f7cf5129ca17e6e3c9e2091c09d8e21897ad332` | `bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6` | `02313f69842b30c1a8a3e2d682c474e0474dc581cb67f2305937dc9b8111e431` |
| Drivers | `11578953444` | Practice 2 `11371` | `82a322bf126d3307f11267370f9eb5aab74d4bf0b7b962cba7db52da01ed33fc` | `66b3d285c5cfc388d488c14e59d03a3ca2f3bd910a7ad5c8ad3e76c7f91148fb` | `c8a276c6b34d4420456569d811b8440c360f0a3c80605efa5511d9f2dad52ac9` |
| Starting grid | `11885033135` | Qualifying `11373` | `9c3af9b3e0b2c701aa2b77c53cb976aa702dc1896577827ae57086283d65ae1b` | `23d798ed27e99138c6bcc61e6efbc557a4022f18ea874dee489f98b6f571cda9` | `a405f6908095d6ac1f37388425b6f2705eb81a020aaebf7a926b9ca630a71d2d` |

The grid session-discovery SHA-256 remained
`f76bc38e3326eec1d43b5108e323dc197f1b690cd9e505c47210414de819e61b`,
and the grid shadow-manifest SHA-256 remained
`8a3e7bf6ddc6b2fa191d4109326601584d359e61f1a3ef68552f03ab2a47d76f`.
All original first-observation times were in October 2026, after the historical
Baku Race start `2026-09-26T11:00:00Z`. Nothing establishes pre-race
availability.

## Deterministic private runtime reconstruction

The accepted adapters and two-column projection helper regenerated the exact
K4R24 inputs before the producer call:

| Input | Rows | SHA-256 |
| --- | ---: | --- |
| `weather.csv` | 85 | `ef19f099e1f52e793f23186d57aef9049019e0282b150287351739435bc3e540` |
| `drivers.csv` | 22 | `884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424` |
| `starting_grid.csv` | 22 | `953983810b5b974dbbbcd190cbd9212b4997cee1f2d2d74791bb3bbfa48809cd` |

The original five-column Qualifying-derived grid SHA-256 remained
`16ff7a35f2ddb45eba24e566e4144f1215a28e16bda5384046daf98183fd531c`.
The canonical frozen-input manifest SHA-256 remained
`c6525950f6b763006c3ed3fb6eb6cc7f6cea9110196199373e739b976ed9fc2e`.
Weather and drivers retained Practice 2 session `11371`; the grid retained
Qualifying source `11373`; Race target `11377` remained a distinct provenance
relationship. The 22-driver roster and positions 1–22 matched.

## Sole producer invocation

- attempt marker written before subprocess: yes;
- invocation count: **1**;
- start UTC: `2026-10-15T12:13:51.356749Z`;
- exact head: `b8249cf2004a2ba67c4c5ae0a6c87a299e241c7c`;
- producer file SHA-256:
  `8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564`;
- timeout ceiling: 120 seconds;
- return code: `0` (the harness passed the explicit return-code check);
- stderr: empty (the harness passed the explicit empty-stderr check);
- parsed stdout equalled the private audit JSON;
- audit status: `forecast_rows_created`;
- audit rows: `22`;
- event / meeting / mechanics session: exact
  `2026_1295_azerbaijan_baku_baku / 1295 / 11371`;
- gate / lane: exact `post_event / experimental_challenger`;
- input mode and binding: `frozen_manifest` with exact manifest SHA above;
- broad discovery: `false`;
- race label: `Baku post-event producer-to-lock mechanics rehearsal - NOT A PREDICTION`;
- audit negative claims checked false through
  `production_authenticated`, `historical_availability_proven`,
  `stable_engine_execution_proven`, `dr002_activated`,
  `promotion_allowed`, and `stable_output_overwrite_allowed`.

The exact producer run ID, forecast-generation UTC, payload size, payload
SHA-256, metadata SHA-256 and snapshot SHA-256 were not preserved before the
HOLD and are therefore **not reported**.

## Lock and classification outcome

`build_forecast_lock` was not invoked. There is no lock receipt, lock receipt
hash, lock parent, stored-payload hash, lock time or immutable-payload binding
result to report. The integration-specific Gate 2A classification call was not
reached. Code inspection still confirms the unchanged Gate 2A function's
explicit `post_event` branch returns
`OUTCOME_AWARE_EVALUATION_ONLY / evaluation_gate`; this Work Result does not
misrepresent that inspection as a completed producer-to-lock integration.

The original checkout remained clean and received no `latest/**`,
`history/**`, `_runtime/**`, raw evidence, producer output or lock output. The
private execution sandbox was removed successfully. Only this authorized
hash-only documentation path is added to the repository.

## Trust ceiling

This HOLD proves no immutable real-source lock and makes no production,
accuracy, prospective, blind-validation, durable-storage, stable-engine,
official-FIA-grid, activation or promotion claim. No live source request,
artifact download, workflow dispatch, model/stable-engine execution,
implementation change or forecast publication occurred.

Engineering progress remains **93/100 PROVISIONAL** pending independent
Adviser review. `Engine_2026-06-07_STABLE` remains protected. DR-002 remains
**PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT
ALLOWED.
