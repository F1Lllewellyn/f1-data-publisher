# DR-002 pre-2B-7K4R10 — exact historical artifacts dual-source replay

**Checkpoint identifier date:** 2026-10-08

**Replay execution:** 2026-10-09 UTC / 2026-10-08 EDT

**Work order:** `F1-WO-DR002-PRE2B7K4R10-001` / Issue #234

**Observed replay repository SHA:** `609ab31d5d399ae872cff14ab78035df27716cad`

**Result:** `DUAL_SOURCE_FROZEN_PRODUCER_MECHANICS_ONLY_NOT_A_PREDICTION`

This checkpoint records exactly one offline replay through the unchanged
accepted K4R9 composition using the exact previously archived K4R3 weather and
K4R8 drivers source artifacts. It is an after-event mechanics replay, not a
new capture, production forecast, blind backtest, or predictive-cutoff claim.

## OBSERVED — past GitHub runs and artifacts

No GitHub Actions workflow was dispatched or rerun for K4R10. Both inputs came
from fixed, already-existing, nonexpired GitHub artifacts downloaded once each
through the GitHub read/download surface.

### K4R3 weather artifact

| Fact | Observed value |
|---|---|
| Workflow | `F1 OpenF1 Lightweight Source Closure` |
| Run / attempt | `37775058587` / `1` |
| Run number / event / conclusion | `87` / `workflow_dispatch` / `success` |
| Run head | `4ac47b9b5d4439659fa2999ab611e85ec1564b41` |
| Run created / completed update | `2026-10-08T12:10:53Z` / `2026-10-08T12:12:13Z` |
| Artifact ID | `11549846922` |
| Artifact name | `dr002-pre2b7k4r2-openf1-historical-rest-shadow` |
| Artifact created / expires | `2026-10-08T12:12:10Z` / `2026-11-07T12:12:10Z` |
| GitHub size | `4,620` bytes |
| GitHub digest | `sha256:11d756f5c8960298ec65fd628f7cf5129ca17e6e3c9e2091c09d8e21897ad332` |

### K4R8 drivers artifact

| Fact | Observed value |
|---|---|
| Workflow | `F1 OpenF1 Lightweight Source Closure` |
| Run / attempt | `37845283040` / `1` |
| Run number / event / conclusion | `88` / `workflow_dispatch` / `success` |
| Run head | `ca7a9646588daa567aafd350e86bec4a263a51ec` |
| Run created / completed update | `2026-10-08T21:13:48Z` / `2026-10-08T21:15:12Z` |
| Artifact ID | `11578953444` |
| Artifact name | `dr002-pre2b7k4r7-openf1-drivers-historical-rest-shadow` |
| Artifact created / expires | `2026-10-08T21:15:08Z` / `2026-11-07T21:15:07Z` |
| GitHub size | `5,182` bytes |
| GitHub digest | `sha256:82a322bf126d3307f11267370f9eb5aab74d4bf0b7b962cba7db52da01ed33fc` |

The artifact metadata associated each fixed ID with the required run, head,
name, size, digest, and repository. Neither artifact was expired.

## RECOMPUTED — archive and source integrity

The downloaded ZIP bytes independently reproduced the GitHub sizes and
digests:

| Source | ZIP bytes | Recomputed ZIP SHA-256 |
|---|---:|---|
| Weather | 4,620 | `11d756f5c8960298ec65fd628f7cf5129ca17e6e3c9e2091c09d8e21897ad332` |
| Drivers | 5,182 | `82a322bf126d3307f11267370f9eb5aab74d4bf0b7b962cba7db52da01ed33fc` |

Each archive contained exactly five unique root-level regular `100644` files.
There were no directories, duplicate names, absolute paths, parent traversal,
backslashes, symlinks, CRC failures, derived CSVs, secrets, or `latest/**` or
`history/**` content.

| Weather member | Exact bytes |
|---|---:|
| `weather.response.json` | 18,359 |
| `source_capture_receipt.json` | 926 |
| `historical_rest_capture_assessment.json` | 1,405 |
| `shadow_manifest.json` | 1,452 |
| `shadow_report.md` | 373 |

| Drivers member | Exact bytes |
|---|---:|
| `drivers.response.json` | 9,166 |
| `source_capture_receipt.json` | 926 |
| `historical_rest_capture_assessment.json` | 1,405 |
| `shadow_manifest.json` | 2,175 |
| `shadow_report.md` | 1,079 |

The original response and receipt member bytes—not ZIP bytes, reconstructed
JSON, checkpoint prose, cached lookalikes, or fixtures—were passed to K4R9.

### Common exact scope and chronology boundary

- event: `2026_1295_azerbaijan_baku_baku`
- meeting: `1295`
- session: `11371`
- known Baku Practice 2 session end: `2026-09-24T13:00:00Z`
- historical-window eligibility: `2026-09-24T13:30:00Z`

Both receipts were canonical, parentless `source_capture` receipts under the
existing receipt schema. Receipt IDs were recomputed from their canonical
identities; raw hashes, scope, canonical URI, deterministic source ID,
chronology, assessment, manifest, and accepted K4R3/K4R8 checkpoint facts all
matched. The two source IDs and two receipt IDs were distinct.

### Exact weather evidence

| Fact | Recomputed value |
|---|---|
| Rows | `85` |
| Raw SHA-256 | `bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6` |
| Receipt-file SHA-256 | `02313f69842b30c1a8a3e2d682c474e0474dc581cb67f2305937dc9b8111e431` |
| Receipt ID | `source_capture:0bdb0098ea88ea420f70d7e71630c90091513476c91746365b2a9c2d168a748f` |
| Source ID | `openf1:weather:7f0dd3ec9bada87879adac918d747e7af0434f17de65901101aed1c52a784fd3` |
| Canonical URI | `https://api.openf1.org/v1/weather?session_key=11371` |
| K4R4 status | `OPENF1_WEATHER_PRODUCER_ADAPTER_VALIDATED` |
| Derived CSV SHA-256 | `ef19f099e1f52e793f23186d57aef9049019e0282b150287351739435bc3e540` |
| Frozen RAW manifest SHA-256 | `bbb7c5152886dbed8e125848b3237c6706037d3efeab515b85bb44bd0d409a27` |
| First observed | `2026-10-08T12:12:09.784033Z` |
| Ingested | `2026-10-08T12:12:09.784372Z` |
| Receipt created | `2026-10-08T12:12:09.784388Z` |

### Exact drivers evidence

| Fact | Recomputed value |
|---|---|
| Rows / unique positive driver numbers | `22` / `22` |
| Raw SHA-256 | `66b3d285c5cfc388d488c14e59d03a3ca2f3bd910a7ad5c8ad3e76c7f91148fb` |
| Receipt-file SHA-256 | `c8a276c6b34d4420456569d811b8440c360f0a3c80605efa5511d9f2dad52ac9` |
| Receipt ID | `source_capture:ce0bbededd2ce695f078c4f77cc806b1fd3c2c0b78ca3b659ff3c9484eae840b` |
| Source ID | `openf1:drivers:0616975c53e4d4534f26b9ad6d6931b5997ae5592e798fb0ac58c15734cb0ec7` |
| Canonical URI | `https://api.openf1.org/v1/drivers?session_key=11371` |
| K4R6 status | `OPENF1_DRIVERS_PRODUCER_ADAPTER_VALIDATED` |
| Derived CSV SHA-256 | `884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424` |
| Frozen RAW manifest SHA-256 | `877d41594c59b55243e44d13af1919f207e5c6f44116fadc1bea56816af058ea` |
| First observed | `2026-10-08T21:15:07.487220Z` |
| Ingested | `2026-10-08T21:15:07.487592Z` |
| Receipt created | `2026-10-08T21:15:07.487611Z` |

Both per-source frozen RAW manifests retained `binding_status=UNBOUND`,
`production_authenticated=false`, and
`historical_availability_proven=false`. No receipt observation time was
replaced with the replay time.

## EXECUTED NOW — sole contained K4R9 replay

After the complete preflight passed, the unchanged function
`compose_openf1_weather_drivers_into_frozen_producer` was invoked exactly once.
There was no direct producer invocation, retry, repair, second replay, model
execution, source request, or workflow action.

| Fact | Executed/recomputed value |
|---|---|
| Replay repository SHA | `609ab31d5d399ae872cff14ab78035df27716cad` |
| K4R9 Git blob | `f69a5ac49b6e3055cd13472037f8b49e8ea41265` |
| Producer Git blob before/after | `af27586668c767de126af829c1131c6bae4634ad` |
| Producer code SHA-256 | `8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564` |
| K4R9 status | `DUAL_SOURCE_FROZEN_PRODUCER_MECHANICS_ONLY_NOT_A_PREDICTION` |
| Producer run ID | `20261009T010444Z` |
| Forecast generation UTC | `2026-10-09T01:04:44Z` |
| Producer subprocess attempts | `1` |
| Input mode / broad discovery | `frozen_manifest` / `false` |
| Gate / lane | `post_event` / `experimental_challenger` |
| Race-name boundary | ends `NOT A PREDICTION` |
| Generated rows | `22` |
| Driver number/name/team matches | `22/22` |
| Synthetic-grid position matches | `22/22` |

The exact driver universe was:

`1, 3, 5, 6, 10, 11, 12, 14, 16, 18, 23, 27, 30, 31, 41, 43, 44, 55, 63, 77, 81, 87`

### Derived runtime identities

| Runtime input | Identity / exact SHA-256 | Rows |
|---|---|---:|
| Drivers | `derived:openf1-drivers-csv:884438ea3c7baa5f9a32d6a22b441b418b181e946329d7220224eacad693e424` | 22 |
| Starting grid | `synthetic:starting-grid-csv:6249bf449596e07c51e774454193bf80bd37e2e5975238a1da2c9c75a97a79f8` | 22 |
| Weather | `derived:openf1-weather-csv:ef19f099e1f52e793f23186d57aef9049019e0282b150287351739435bc3e540` | 85 |

The synthetic grid was independently parsed with exact unique driver
membership in ascending driver-number order and positions `1..22`. It is not
an observed or FIA official grid.

The canonical `dr002-frozen-producer-input-v1` manifest had exact source order
`drivers`, `starting_grid`, `weather`; exact relative paths `drivers.csv`,
`starting_grid.csv`, `weather.csv`; the common scope; and exact source
identities/hashes. Its SHA-256 was:

`40a5352b6159a2a377f2ccef493ae7b04245123b3b0929035445e7d8caff9ef5`

The unchanged producer source counts were drivers `22`, starting grid `22`,
weather `85`, and zero for intervals, stints, race control, pit, position, and
source readiness. Audit, metadata, and source snapshot independently matched
the manifest identities, hashes, paths, counts, scope, frozen mode, and
discovery bypass.

The resulting readiness value was exactly `0.48`: drivers `0.18`, synthetic
grid `0.20`, and weather `0.10`. Because the grid contribution is fabricated
for mechanics, `0.48` is **MECHANICS ONLY**. It is not authentic readiness,
source truth, confidence, blind eligibility, or predictive evidence.

### Returned in-memory evidence

| Evidence | Recomputed SHA-256 |
|---|---|
| `producer_audit.json` | `609777028287135a8b2e8e8a25e7e6b269ec1dcb0f81f9a4f87e079f0241f60a` |
| `source_snapshot_manifest.csv` | `33a4b5461d78dd0a8436825816020413efd74b9e0c06ff92ed562c722a1617d1` |
| `forecast_rows.csv` | `9f3ca5e8863235960a7ba6a659c90e460c90a78233335f0c2939ad668eeaf2cd` |
| `forecast_metadata.json` | `88c94f13c7c4e37787f1a4698b102bbf23d631239e91b8234e622933403dfe0f` |

All four returned evidence hashes recomputed. The exact sandbox allowlist held
16 files across inputs, runtime evidence, local latest/history outputs, and
compatibility mirrors. Mirrors matched, the sandbox was disposed, and
checked-out `latest/**` and `history/**` fingerprints were unchanged. No raw
ZIP, raw source, derived CSV, producer output, receipt, or binding is retained
in the repository.

## Relevant landed dependency pins

All Issue #234 relevant blobs matched on the replay checkout before execution:

| Dependency | Git blob SHA |
|---|---|
| K4R9 dual-source composition | `f69a5ac49b6e3055cd13472037f8b49e8ea41265` |
| K4R4 weather adapter | `5061d8007d06c37e164df2c6cc643e385be885f8` |
| K4R6 drivers adapter | `357ac56a6cfe317e21d9ce71d78c58683e444a5a` |
| K4R5 composition | `090c61af27ef932aae51a8fb83fe828c20c13a68` |
| Frozen evidence contract | `8dfd855184b172ce88235ee7de3ea33a68031b2e` |
| Current real producer | `af27586668c767de126af829c1131c6bae4634ad` |
| K4R3 weather checkpoint | `db92fb23ff0adf95e59a80f14dcd527b6d1f9906` |
| K4R8 drivers checkpoint | `943440c604163913a95690322bdcdfc850e03b58` |
| K4R9 checkpoint | `ef87ae0ad498f54e107fad813fa7ddcf61fd9bfd` |
| Handoff contract | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

Unrelated scheduler-generated `latest/**` and `history/**` changes after the
K4R9 merge did not alter these relevant dependencies.

## UNPROVEN / NOT CLAIMED

The raw OpenF1 observations occurred on October 8, 2026, after the September
24 Baku session and after the event. Exact-byte replay does not move those
observations backward in time and cannot prove the bytes existed at any
pre-race or predictive cutoff.

This checkpoint does **not** prove:

- official FIA/F1 driver-roster or final-grid authority;
- an observed starting grid—the replay grid is synthetic;
- authenticated OpenF1 provider truth or complete publisher revisions;
- historical availability before either recorded first observation;
- a real, live, prospective, blind, or production forecast;
- stable-engine execution or a model/engine performance result;
- forecast-lock, outcome-boundary, or revision enforcement;
- prediction accuracy or accuracy improvement;
- production authentication, verified receipt bindings, DR-002 activation, or
  model promotion.

OpenF1 remains unofficial. Official FIA/F1/team/Pirelli evidence overrides it.
All trust, activation, official-grid, blind-eligibility, promotion, and
accuracy flags remained false.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion
**NOT ALLOWED**.
