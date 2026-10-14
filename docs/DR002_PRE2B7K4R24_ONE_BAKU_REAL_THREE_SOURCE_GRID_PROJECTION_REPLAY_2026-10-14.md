# DR-002 pre-2B-7K4R24 one real Baku three-source grid projection replay

**Work order:** Issue #268 / `F1-WO-DR002-PRE2B7K4R24-REPLAY-001`

**Result:** `OPENF1_THREE_SOURCE_PRODUCER_INPUT_PROJECTION_VALIDATED_POST_EVENT_SANDBOX_PROJECTION_ONLY_NOT_A_PREDICTION`

**Classification:** `POST_EVENT_SANDBOX_PROJECTION_ONLY_NOT_A_PREDICTION`

**DR-002:** PROPOSED — NOT ACTIVATED

**Forecast gate:** OFF

**Promotion:** NOT ALLOWED

## Execution record

No prior K4R24 execution/result marker was present in the existing Work
session. After the complete artifact and implementation preflight passed, one
and only one call was made to
`project_compatible_openf1_three_sources_for_p2_mechanics` using the exact
original source/receipt/discovery/manifest bytes described below.

- invocation count: **exactly 1**;
- started: `2026-10-14T22:08:07.699744Z`;
- completed: `2026-10-14T22:08:07.710677Z`;
- implementation Git head:
  `ff6c9368adbbe91ea09ac0c40b1177a605d0cc07`;
- status: `OPENF1_THREE_SOURCE_PRODUCER_INPUT_PROJECTION_VALIDATED_POST_EVENT_SANDBOX_PROJECTION_ONLY_NOT_A_PREDICTION`;
- classification: `POST_EVENT_SANDBOX_PROJECTION_ONLY_NOT_A_PREDICTION`;
- reason codes: `[]`;
- independent canonical verification-record SHA-256:
  `f00e47fe22245863c06eb585b7d89a573b3ec0b45e29f132ec6a1eead5e31898`.

There was no retry, second projection call, separate K4R21 assessment call,
synthetic-test repetition, or attempt to alter a returned result.

## Original immutable artifact preflight

The already retained weather and drivers archives were reused. The identical
grid archive was not locally retained, so it was downloaded once from its
exact authorized GitHub Actions artifact ID. No provider, FIA, OpenF1 API, or
other live source was contacted.

| Role | Run | Artifact | ZIP bytes | Whole-ZIP SHA-256 | Exact members |
| --- | ---: | ---: | ---: | --- | ---: |
| Weather / Practice 2 | `37775058587` | `11549846922` | 4,620 | `11d756f5c8960298ec65fd628f7cf5129ca17e6e3c9e2091c09d8e21897ad332` | 5/5 |
| Drivers / Practice 2 | `37845283040` | `11578953444` | 5,182 | `82a322bf126d3307f11267370f9eb5aab74d4bf0b7b962cba7db52da01ed33fc` | 5/5 |
| Starting grid / Qualifying | `38548009086` | `11885033135` | 7,992 | `9c3af9b3e0b2c701aa2b77c53cb976aa702dc1896577827ae57086283d65ae1b` | 6/6 |

All archives passed exact length and whole-ZIP digest checks, exact case-
sensitive member-set checks, duplicate/path-traversal/absolute-path rejection,
directory and symlink rejection, and CRC validation before invocation.

The exact original member hashes were:

| Source evidence | SHA-256 |
| --- | --- |
| Weather raw response | `bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6` |
| Drivers raw response | `66b3d285c5cfc388d488c14e59d03a3ca2f3bd910a7ad5c8ad3e76c7f91148fb` |
| Starting-grid raw response | `23d798ed27e99138c6bcc61e6efbc557a4022f18ea874dee489f98b6f571cda9` |
| Grid session discovery | `f76bc38e3326eec1d43b5108e323dc197f1b690cd9e505c47210414de819e61b` |
| Grid shadow manifest | `8a3e7bf6ddc6b2fa191d4109326601584d359e61f1a3ef68552f03ab2a47d76f` |
| Weather receipt bytes | `02313f69842b30c1a8a3e2d682c474e0474dc581cb67f2305937dc9b8111e431` |
| Drivers receipt bytes | `c8a276c6b34d4420456569d811b8440c360f0a3c80605efa5511d9f2dad52ac9` |
| Starting-grid receipt bytes | `a405f6908095d6ac1f37388425b6f2705eb81a020aaebf7a926b9ca630a71d2d` |

Each receipt retained its canonical parentless source-capture identity and
original scope:

- weather, Practice 2 `11371`:
  `source_capture:0bdb0098ea88ea420f70d7e71630c90091513476c91746365b2a9c2d168a748f`;
- drivers, Practice 2 `11371`:
  `source_capture:ce0bbededd2ce695f078c4f77cc806b1fd3c2c0b78ca3b659ff3c9484eae840b`;
- starting grid, Qualifying `11373`:
  `source_capture:ab36241b7276bddff68cd33ff37209d0a5f3a7aa214749316aecb22c7b6858e4`.

## Source and target lineage

Event `2026_1295_azerbaijan_baku_baku`, meeting `1295`, preserved three
distinct sessions:

| Role | Session | Start UTC | End UTC |
| --- | --- | --- | --- |
| Weather and drivers source | Practice / Practice 2 `11371` | `2026-09-24T12:00:00+00:00` | `2026-09-24T13:00:00+00:00` |
| Starting-grid source | Qualifying / Qualifying `11373` | `2026-09-25T12:00:00+00:00` | `2026-09-25T13:00:00+00:00` |
| Target relationship only | Race / Race `11377` | `2026-09-26T11:00:00+00:00` | `2026-09-26T13:00:00+00:00` |

The original raw source IDs also remained separate:

- weather:
  `openf1:weather:7f0dd3ec9bada87879adac918d747e7af0434f17de65901101aed1c52a784fd3`;
- drivers:
  `openf1:drivers:0616975c53e4d4534f26b9ad6d6931b5997ae5592e798fb0ac58c15734cb0ec7`;
- starting grid:
  `openf1:starting_grid:42a1e7d49fd26ba241fb3c48aea5e615bde90f7f7f4f0757e125a97f517c6cd4`.

No source scope was rewritten. In particular, the original starting-grid
evidence and its five-column derived view remain Qualifying `11373`; neither
was relabelled as Practice 2 `11371` or Race `11377`.

## Actual projected runtime result

The unchanged K4R23 implementation internally validated K4R21 and reran the
three accepted adapters. The returned weather and drivers CSVs retained their
original Practice 2 `session_key=11371` columns and bytes. The original
five-column Qualifying grid remained separately hashed lineage. Only the new
additional grid runtime view omitted source-scope columns.

| Runtime input | Rows | SHA-256 | Derived runtime identity |
| --- | ---: | --- | --- |
| `weather.csv` | 85 | `ef19f099e1f52e793f23186d57aef9049019e0282b150287351739435bc3e540` | `derived:openf1-weather-csv:ef19f099e1f52e793f23186d57aef9049019e0282b150287351739435bc3e540` |
| `drivers.csv` | 22 | `884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424` | `derived:openf1-drivers-csv:884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424` |
| projected `starting_grid.csv` | 22 | `953983810b5b974dbbbcd190cbd9212b4997cee1f2d2d74791bb3bbfa48809cd` | `derived:postevent-unscoped-qualifying-grid-projection:953983810b5b974dbbbcd190cbd9212b4997cee1f2d2d74791bb3bbfa48809cd` |

The original five-column Qualifying derived-grid CSV SHA-256 remained
`16ff7a35f2ddb45eba24e566e4144f1215a28e16bda5384046daf98183fd531c`
with distinct runtime identity
`derived:openf1-starting-grid-csv:16ff7a35f2ddb45eba24e566e4144f1215a28e16bda5384046daf98183fd531c`.

Independent byte-level verification confirmed:

- the prior accepted weather, drivers, and original-grid derived hashes all
  matched K4R22 exactly;
- the projected grid header was exactly `driver_number,position` in UTF-8/LF;
- projected positions were exactly the ordered integers 1 through 22;
- the 22 projected driver numbers exactly matched the 22 validated Practice 2
  driver numbers;
- no event, meeting, session ID or session key remained in the projected-grid
  bytes; and
- the three derived runtime identities were distinct and disjoint from every
  original raw source and receipt identity.

## Sandbox-candidate manifest

The canonical candidate manifest SHA-256 was
`c6525950f6b763006c3ed3fb6eb6cc7f6cea9110196199373e739b976ed9fc2e`.
It used schema `dr002-frozen-producer-input-v1`, event
`2026_1295_azerbaijan_baku_baku`, meeting `1295`, and Practice 2 mechanics
scope `session_id=11371`. Its exact source order and canonical filenames were:

1. derived drivers — `drivers.csv`;
2. derived unscoped Qualifying-grid projection — `starting_grid.csv`;
3. derived weather — `weather.csv`.

Each manifest source digest was independently recomputed from its returned
runtime bytes and matched. The manifest bytes were independently regenerated
as canonical sorted compact UTF-8 JSON and matched byte-for-byte. It embedded
no raw source data, receipt, URL or source identity.

This manifest is a **sandbox candidate only**. It is not an approved frozen-
evidence capture, source authorization, cross-session join authorization or
permission to execute the producer.

## Code preflight

All required merged-main Git blobs matched before invocation:

- K4R23 projector `63ae055aa54c9d9cbe12772c99301a41496863ab`;
- K4R21 compatibility assessor `f0850f4c13132b213f03a2b1aeaea01acebe2bf8`;
- weather adapter `5061d8007d06c37e164df2c6cc643e385be885f8`;
- drivers adapter `357ac56a6cfe317e21d9ce71d78c58683e444a5a`;
- Qualifying-grid adapter `702a1219c4b97450d7aeec16b5dd8409f2b73d75`;
- protected producer `af27586668c767de126af829c1131c6bae4634ad`;
- handoff contract `85ce44807ef159b5ba5d3bfd543ea1f945097f77`.

## Claim ceilings and execution audit

All 20 returned scientific, operational, authentication, scoring, activation,
and promotion claim flags were exactly `false`, including producer/model/
stable-engine execution, forecast generation, predictive accuracy,
historical pre-race availability, FIA final-grid authentication, cross-session
producer authorization, scientific/normalization receipt creation, verified
receipt binding, DR-002 activation, and promotion.

Workflow dispatches: **0**. Live provider/FIA/OpenF1 requests: **0**. Producer,
composer, model or stable-engine executions: **0**. Synthetic test runs: **0**.
Tracked implementation/test/workflow changes: **0**. Raw source publication:
**0**. Forecasts generated: **0**. Accuracy calculations: **0**.

This result establishes only that the genuine archived Baku sources can pass
the accepted offline projection and produce a scope-safe mechanics candidate.
It does not establish pre-race availability, an official FIA final grid,
producer acceptance, a forecast, blind evaluation, predictive accuracy,
production readiness, DR-002 activation or promotion. K4R25 remains separately
unauthorized.
