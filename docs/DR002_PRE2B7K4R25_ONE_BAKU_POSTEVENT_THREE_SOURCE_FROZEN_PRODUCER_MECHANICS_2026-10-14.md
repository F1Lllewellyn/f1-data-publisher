# DR-002 pre-2B-7K4R25 one Baku post-event three-source frozen-producer mechanics experiment

**Work order:** Issue #271 / `F1-WO-DR002-PRE2B7K4R25-001`

**Result:** `K4R25_CONTAINED_POST_EVENT_FROZEN_PRODUCER_MECHANICS_VALIDATED_NOT_A_PREDICTION`

**Producer audit status:** `forecast_rows_created`

**HOLD reasons:** none

**DR-002:** PROPOSED — NOT ACTIVATED

**Forecast gate:** OFF

**Promotion:** NOT ALLOWED

## Scientific meaning

This was one contained, offline, post-outcome mechanics experiment using the
unchanged frozen-input CLI of the existing producer. It establishes only that
the accepted original-derived Baku weather, drivers and unscoped Qualifying-
grid projection can pass the producer's frozen-input boundary and generate a
structurally consistent private sandbox output.

The private files named `forecast_rows.csv` are not predictions, prelock
forecasts, model-performance evidence or downstream-usable Race, Fantasy or
Reports products. The producer's generic internal classification
`actual_forecast_rows_generated_from_available_prelock_sources` does not prove
historical availability. The original sources were captured after the Race.
No accuracy or competitive-edge inference is permitted.

## Execution and one-attempt control

- execution Git head:
  `6440740e5c7586c8041c791e4cd7a20d150d00c9`;
- producer Git blob:
  `af27586668c767de126af829c1131c6bae4634ad`;
- producer file SHA-256:
  `8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564`;
- Coder-reported producer subprocess attempt count: **exactly 1**;
- started: `2026-10-14T22:26:19.710720Z`;
- completed: `2026-10-14T22:26:19.773883Z`;
- private run ID: `20261014T222619Z`;
- timeout: `false`;
- return code: `0`;
- stderr bytes: `0`;
- stdout bytes: `2,337`;
- stdout SHA-256:
  `1bc2bad07c51790d8f95ffa3e59b939a03ab4aab60d64e8912b08f2ba4e62b10`;
- empty stderr SHA-256:
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- canonical verification-record SHA-256:
  `e814c788d97ef16d7b5a421b50c0eb6c5e4b23995f30f4d2016fec3435a845a1`.

The attempt marker was written immediately before the subprocess and retained
privately after completion to prevent a retry. As required, the docs-only Work
Result records the Coder-reported invocation count; a public documentation
commit cannot mathematically prove a private process count.

The exact command, with private paths sanitized, was:

```text
python scripts/forecasts/produce_actual_forecast_rows_v1.py \
  --frozen-input-manifest <PRIVATE_SANDBOX_INPUT_ROOT>/frozen_input_manifest.json \
  --event-id 2026_1295_azerbaijan_baku_baku \
  --meeting-id 1295 \
  --session-id 11371 \
  --race-name "Baku post-event three-source mechanics shadow - NOT A PREDICTION" \
  --gate post_event \
  --lane experimental_challenger \
  --repo-root <PRIVATE_SANDBOX_ROOT> \
  --strict-source
```

The subprocess used the disposable sandbox as its working directory,
`PYTHONDONTWRITEBYTECODE=1`, captured stdout and stderr, `check=False`, and a
120-second maximum timeout. The producer source path was absolute and remained
inside the pinned read-only checkout; the producer `--repo-root` was the
private sandbox, never the checkout.

## Original source evidence and preserved lineage

No source artifact was downloaded and no provider was contacted. The already
retained exact archives were re-read and passed byte length, whole-ZIP digest,
exact member set, duplicate/path/symlink/directory rejection, CRC, raw-content
digest, canonical receipt identity, receipt-byte digest, scope and raw-binding
checks.

| Role | Original run / artifact | Source session | ZIP SHA-256 | Raw SHA-256 | Receipt-bytes SHA-256 |
| --- | --- | --- | --- | --- | --- |
| Weather | `37775058587 / 11549846922` | Practice 2 `11371` | `11d756f5c8960298ec65fd628f7cf5129ca17e6e3c9e2091c09d8e21897ad332` | `bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6` | `02313f69842b30c1a8a3e2d682c474e0474dc581cb67f2305937dc9b8111e431` |
| Drivers | `37845283040 / 11578953444` | Practice 2 `11371` | `82a322bf126d3307f11267370f9eb5aab74d4bf0b7b962cba7db52da01ed33fc` | `66b3d285c5cfc388d488c14e59d03a3ca2f3bd910a7ad5c8ad3e76c7f91148fb` | `c8a276c6b34d4420456569d811b8440c360f0a3c80605efa5511d9f2dad52ac9` |
| Starting grid | `38548009086 / 11885033135` | Qualifying `11373` | `9c3af9b3e0b2c701aa2b77c53cb976aa702dc1896577827ae57086283d65ae1b` | `23d798ed27e99138c6bcc61e6efbc557a4022f18ea874dee489f98b6f571cda9` | `a405f6908095d6ac1f37388425b6f2705eb81a020aaebf7a926b9ca630a71d2d` |

Additional original grid evidence remained exact:

- session-discovery SHA-256:
  `f76bc38e3326eec1d43b5108e323dc197f1b690cd9e505c47210414de819e61b`;
- shadow-manifest SHA-256:
  `8a3e7bf6ddc6b2fa191d4109326601584d359e61f1a3ef68552f03ab2a47d76f`;
- original five-column Qualifying-derived grid lineage SHA-256:
  `16ff7a35f2ddb45eba24e566e4144f1215a28e16bda5384046daf98183fd531c`.

Canonical source receipt identities remained distinct:

- weather:
  `source_capture:0bdb0098ea88ea420f70d7e71630c90091513476c91746365b2a9c2d168a748f`;
- drivers:
  `source_capture:ce0bbededd2ce695f078c4f77cc806b1fd3c2c0b78ca3b659ff3c9484eae840b`;
- starting grid:
  `source_capture:ab36241b7276bddff68cd33ff37209d0a5f3a7aa214749316aecb22c7b6858e4`.

Raw source identities remained distinct:

- weather:
  `openf1:weather:7f0dd3ec9bada87879adac918d747e7af0434f17de65901101aed1c52a784fd3`;
- drivers:
  `openf1:drivers:0616975c53e4d4534f26b9ad6d6931b5997ae5592e798fb0ac58c15734cb0ec7`;
- starting grid:
  `openf1:starting_grid:42a1e7d49fd26ba241fb3c48aea5e615bde90f7f7f4f0757e125a97f517c6cd4`.

The target Race remained separate session `11377` and only a provenance
relationship. Neither original Qualifying source evidence nor its five-column
derived view was relabelled as Practice 2 or Race.

## Accepted runtime inputs

The K4R24 main projection function and K4R21 event assessment were not called.
Because the accepted runtime byte strings had not been retained as files, they
were regenerated from the already verified archives using the accepted
individual weather, drivers and grid adapters plus the accepted deterministic
two-column projection helper. All resulting bytes had to match the K4R24 pins
before the producer attempt.

| Private runtime input | Rows | SHA-256 | Derived runtime identity |
| --- | ---: | --- | --- |
| `weather.csv` | 85 | `ef19f099e1f52e793f23186d57aef9049019e0282b150287351739435bc3e540` | `derived:openf1-weather-csv:ef19f099e1f52e793f23186d57aef9049019e0282b150287351739435bc3e540` |
| `drivers.csv` | 22 | `884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424` | `derived:openf1-drivers-csv:884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424` |
| `starting_grid.csv` | 22 | `953983810b5b974dbbbcd190cbd9212b4997cee1f2d2d74791bb3bbfa48809cd` | `derived:postevent-unscoped-qualifying-grid-projection:953983810b5b974dbbbcd190cbd9212b4997cee1f2d2d74791bb3bbfa48809cd` |

The weather and drivers CSVs retained truthful Practice 2
`session_key=11371` scope. The runtime grid header was exactly
`driver_number,position`, contained 22 unique drivers and contiguous positions
1 through 22, and contained no event, meeting or session scope column. Its
unscoped runtime identity preserved Qualifying-grid lineage without pretending
the bytes were Practice 2 or Race source evidence. The driver and grid rosters
matched exactly.

The canonical sorted compact UTF-8 frozen-input manifest SHA-256 was
`c6525950f6b763006c3ed3fb6eb6cc7f6cea9110196199373e739b976ed9fc2e`.
It retained schema `dr002-frozen-producer-input-v1`, event
`2026_1295_azerbaijan_baku_baku`, meeting `1295`, declared mechanics scope
`session_id=11371`, and exact source order `drivers,starting_grid,weather`.
Each manifest source was bound to the derived runtime identity and digest
above. All four materialized input files passed nonempty, nonsymlink and exact
byte readback before execution.

## Actual producer result

The producer returned exit `0`. Its stdout parsed exactly to the emitted
private audit JSON. Independent readback established:

- audit status `forecast_rows_created`;
- `forecast_rows_created=22`;
- `gate_lane_files_created=1`;
- `driver_universe_count=22`;
- `input_mode=frozen_manifest`;
- schema `dr002-frozen-producer-input-v1`;
- exact candidate-manifest hash binding;
- exact event `2026_1295_azerbaijan_baku_baku`, meeting `1295` and mechanics
  session `11371`;
- `broad_discovery_used=false`;
- source counts drivers `22`, starting grid `22`, weather `85`, with all six
  other producer source types zero;
- exactly one requested and emitted gate, `post_event`;
- exactly one requested and emitted lane, `experimental_challenger`;
- no stable lane;
- exact mechanics-only race name;
- 22 unique private driver rows, exactly the accepted roster;
- each private row's grid position matched the accepted original-derived grid
  mapping;
- no unknown or filler row;
- all private rows reported source readiness `0.48`;
- all private rows retained `stable_output_overwrite_allowed=false` and
  `promotion_eligible_from_this_row=false`; and
- the nine-row source snapshot marked only drivers, starting grid and weather
  as found, with exact input counts, derived IDs, digests and relative paths.

## Private output evidence hashes

No row contents or driver names are published. Identical compatibility copies
were verified byte-for-byte before disposal.

| Evidence class | Private byte size | SHA-256 |
| --- | ---: | --- |
| Runtime audit JSON | 2,336 | `f5e15c10ee2c0dcc61c6dfda92d2707a6668507f65693f51b71400783a1b8119` |
| Source snapshot CSV, each of 3 copies | 849 | `19571fd5ebdb5d10144641487cd75ae1732056faf43fdd454219762fc93d91b6` |
| Forecast metadata JSON, each of 4 copies | 2,140 | `a284c469fc7b07544770d544a1954c3b4dc2eefb047870becefff839d4c91ffd` |
| Private 22-row output CSV, each of 4 copies | 9,767 | `7f96d4a4fe4d91c08c39520d99cf1a31b0e79e33c8006d62c084d86058772d58` |

The private sandbox contained exactly four materialized input files and twelve
producer-output files: two runtime records, three files under each primary
`latest/forecasts` and `history/forecasts` path, and two files under each
compatibility mirror. There were no extra files, gates, lanes or symlinks.

## Filesystem containment and disposal

The checked-out repository had no `latest`, `history` or `_runtime` output root
before execution. Each remained absent afterward. Their common empty-snapshot
digest was unchanged at
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
The tracked checkout remained clean before and after the experiment except for
this subsequently created documentation file.

The disposable private sandbox, including the runtime CSVs, manifest, private
rows, metadata, snapshots and audit, was deleted after hash and structure
verification. Cleanup readback succeeded. Only the non-sensitive hash-only
attempt and verification records remained privately outside the checkout.

## Negative claim and promotion QA

Audit and metadata readback confirmed every required trust flag was `false`:

- `production_authenticated`;
- `historical_availability_proven`;
- `stable_engine_execution_proven`;
- `dr002_activated`;
- `promotion_allowed`; and
- `stable_output_overwrite_allowed`.

No live source request, artifact download, workflow dispatch, K4R24 replay,
K4R21 event assessment, second producer call, model or stable-engine execution,
test run, code change, output publication, merge, activation or promotion was
performed. The experiment did not create a source, scientific or normalization
receipt and did not authorize a cross-session producer join for operational
use.

## Immutable dependency readback

All relevant Git blobs matched at execution head:

- producer:
  `af27586668c767de126af829c1131c6bae4634ad`;
- K4R23 projection implementation, not reinvoked:
  `63ae055aa54c9d9cbe12772c99301a41496863ab`;
- K4R21 compatibility assessor, not invoked:
  `f0850f4c13132b213f03a2b1aeaea01acebe2bf8`;
- weather adapter:
  `5061d8007d06c37e164df2c6cc643e385be885f8`;
- drivers adapter:
  `357ac56a6cfe317e21d9ce71d78c58683e444a5a`;
- starting-grid adapter:
  `702a1219c4b97450d7aeec16b5dd8409f2b73d75`;
- earlier contained-producer mechanics reference, not executed:
  `f69a5ac49b6e3055cd13472037f8b49e8ea41265`;
- accepted K4R24 documentation:
  `d7ca69cc1ee06db9df2a1faa570512503a86bac0`;
- handoff contract:
  `85ce44807ef159b5ba5d3bfd543ea1f945097f77`.

This result is post-event sandbox mechanics evidence only. It does not activate
DR-002, open the forecast gate, permit promotion, prove a blind forecast or
support any model-performance claim.
