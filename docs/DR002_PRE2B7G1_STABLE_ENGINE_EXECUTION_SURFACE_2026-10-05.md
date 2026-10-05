# DR-002 pre-2B-7G1 — Stable-engine execution surface assessment

Work order: [Issue #162](https://github.com/F1Lllewellyn/f1-data-publisher/issues/162), `F1-WO-DR002-PRE2B7G1-001`.
Assessment baseline: [`f9b26908b7ab4f0e96d928ab5cbbe73d097c8299`](https://github.com/F1Lllewellyn/f1-data-publisher/commit/f9b26908b7ab4f0e96d928ab5cbbe73d097c8299).
Root Git tree: `984c2807ceadf118f83ffbaa36e32bb524c6a268`.
Handoff contract Git blob: `85ce44807ef159b5ba5d3bfd543ea1f945097f77`.

**Finding: route C — HOLD on claiming protected stable-engine execution.**
No exact executable identity corresponding to `Engine_2026-06-07_STABLE` was established in the assessed current code, archives or targeted history. Executable forecasting code exists, but its identity is the current generic producer, not a proven recovery of the protected June 7 baseline.

This completes the authorized read-only assessment. The scientific HOLD is the assessment's conclusion, not an authorization to repair, reconstruct or rename an engine.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate OFF. Promotion NOT ALLOWED.

## Evidence scope and retrieval limits

Fresh open-issue enumeration returned two issues and exactly one exact-prefix authorized work order: #162; its comment collection was empty. Main equals the accepted PR #160 merge commit from the preceding work order.

The root and these component inventories were fetched at the pinned baseline: `scripts`, `.github`, `docs`, `config`, `configs`, `_archive`, `_backups`, `_backup_F1_1A_no_source_commit_guard_2026-06-11`, `F1_Peak_Elite_System_Installer_v1`, `installer`, `templates`, `workbooks` and `workbook_bridge`. All component recursive responses were untruncated. Scripts contained 242 entries; docs 245; the archive 1,255. No path naming the protected June 7 engine was found in those inventories.

The initial attempt at a whole-main recursive inventory was truncated amid generated history. It is **not** evidence of complete repository coverage; the assessment instead uses the separate complete component inventories above. Generated `latest/**` and `history/**` forecast labels are not executable identities and were not exhaustively downloaded or revalidated.

All 150 current branches were enumerated across pages of 100 and 50, with an empty third page. None had a name containing `stable`. Seven tag refs were enumerated through `git/matching-refs/tags/`: six season-archive tags and the automation baseline tag. None names the June 7 stable engine. The ordinary tags endpoint was rejected by the connector; no conclusion depends on that rejected request.

Default-branch connector searches for the two label strings returned no results despite known references in fetched files. They were not treated as negative evidence. Findings use actual file bytes, trees and path histories.

History retrieval was targeted: root commit and June 8 publisher state, June 10 automation baseline, complete returned path histories for producer, writer, locker, Elite v2 and FULL7 policy, and an exact `Engine_2026-06-07_STABLE` path-history query. This is not an exhaustive search of every blob in every commit, deleted branch, unreachable object, external workbook or prior chat. The negative finding means **no recoverable exact stable identity was established by this assessment**, not proof that no external archive could exist.

## Current executable and metadata surfaces

| Surface | Observed role | Protected stable-engine identity |
| --- | --- | --- |
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | Actual executable with internal driver scoring, probabilities and three lane policies | **Unproven; must not be claimed** |
| `stable_baseline` inside that producer | Branch of its internal scoring/risk policy | Lane label, not separate-engine execution proof |
| `scripts/forecast_bundles/write_gate_forecast_rows_v1.py` | Normalizes existing forecast rows and fills lane configuration text | Not a protected-engine invocation |
| `scripts/forecast_bundles/create_forecast_bundles_v1.py` | Discovers/copies existing forecast rows, writes bundle metadata and lock/copy times | Not a protected-engine invocation |
| `.github/workflows/f1-actual-forecast-producer-v1.yml` | Invokes the current generic producer | Workflow identity does not establish stable identity |
| `.github/workflows/f1-forecast-bundle-locker-v1.yml` | Invokes the bundle-copy/metadata script | Locking is not engine execution |
| `scripts/elite/elite_weekend_engine_v2.py` | Artifact consumer producing readiness, warnings, risk boards, reports and workbook exports | No byte/history equivalence to the protected stable engine established |
| `config/protected_paths.json` / `.yml` | Governance markers including the protected name | Protection declarations, not implementation bytes |
| Current operational control-room workbook | Repository workbook artifact and documented view/import layer | No exact June 7 implementation identity established |

### Current actual producer

Exact producer Git blob: `af27586668c767de126af829c1131c6bae4634ad`.
Independently recomputed producer code SHA-256: `8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564`.

At this blob, line 21 declares three lanes. `reliability_risk`, `score_driver`, `probability_from_rank` and `produce_rows` calculate outputs inside the producer. The stable lane selects its internal aggression/risk settings. Its scoring uses grid position, hard-coded team priors, fallback rank, source-row readiness and its own deterministic transforms. The inspected imports and call chain contain no separate protected-stable module load or subprocess invocation.

Entry point is `main()`, called by the module's `__main__` block; the workflow invokes this path with event, race, gate/lane and source options. This is a statically observed invocation contract, **not an execution performed for this work order**.

Frozen mode accepts an explicit `dr002-frozen-producer-input-v1` manifest plus event/meeting/session scope and exact source CSV identities/hashes. Source categories are drivers, starting_grid, intervals, stints, weather, race_control, pit, position and source_readiness. Outputs include forecast_rows.csv, source_snapshot_manifest.csv and forecast_metadata.json under latest/history forecasts, compatibility forecast_outputs mirrors, and a runtime producer audit.

The code at lines 244–249 explicitly retains `stable_engine_execution_proven=False` in frozen audit data. Frozen input containment therefore proves no protected-engine identity. The existing `_run_producer` output writers remain enabled: frozen mode alone is **not** a read-only/no-publish execution interface. No prediction was executed here to test those outputs.

### Source writer and bundle locker

The source writer's `LANE_CONFIG` maps `stable_baseline` to `Engine_2026-06-07_STABLE` at lines 26–30. `normalize_rows` fills `engine_lane_config` when absent. It neither resolves that name to implementation bytes nor invokes it.

The locker repeats that mapping near its top, finds existing forecast rows and writes the label into row/config/manifest metadata. Its `stable_engine_touched=False` field is a written assertion; it is not independent evidence of any stable-engine execution.

Legacy blind-eligibility and timestamp behavior in these components is already documented in the DR-002 continuity spine. This assessment neither upgrades that behavior nor repairs it. Copying a producer forecast into a bundle cannot retrospectively establish a separate engine invocation.

### Elite Weekend Engine v2

Exact current blob: `a39a0930f2873a0ff9816624e44aa96c2006beac`.
Independently recomputed code SHA-256: `08acf17d81f9aa9ab4662861d02a52a09f5cd81a801d35f72840afced8b5e4f9`.

It takes `--input-dir` and `--output-dir`, reads OpenF1 artifact manifests/profile summaries, and writes metrics, reports, ledgers, validation, manifests and workbook_exports. Its declarations disallow automatic stable race P1–P20 and qualifying P1–P5 changes. The workflow downloads artifacts then runs this consumer.

Its current bytes also exist unchanged in `_archive/f1_operational_baseline_all5_patch_2026-06-10/payload/scripts/elite/elite_weekend_engine_v2.py`. Earlier archived Elite v2 bytes are `01fd2f63baa1af1e2df8fec565616010241ded68`. These prove recoverable **Elite artifact-consumer** implementations, not equivalence to the June 7 stable engine. No protected-engine invocation or identity binding was found in the inspected consumer.

## Historical identity and recovery

### Strongest explanatory repository evidence

The current continuity spine, Git blob `23f7ee1f673a02fa676ca29f4ba1ab9f049e7189`, lines 173–192, describes the June 7 v24 Operational Reset: v17 restored as the practical operational core; v18–v23 retained as experimental/data-learning history; new data advisory pending promotion evidence. It expressly describes this as the origin of the protected name.

That is the strongest retrieved repository account of **what the name referred to**. It is later documentary evidence, not a contemporaneous implementation manifest, executable checksum or independently verified June 7 run. Its cited v17/v24 sheets and prior context are not present as an exact executable identity in the assessed objects.

The current `workbooks/` inventory contains one file:
`F1_2026_Prediction_Model_Data_Workbook_OPERATIONAL_CONTROL_ROOM_READY_2026-06-10.xlsx`,
Git blob `cb67dd0596f7b42c59225c82ca314d1b3ea6c0fb`.
Its companion document, blob `939469ac4b1310ab4f73f133dffa3e62563524a2`, describes a readable control-room workbook. Workbook presence and a document's role description do not prove an exact frozen v17/v24 computational model. Workbook contents/formulas were not opened or evaluated here, and no claim that this file lacks formulas is made. Supplied historical attachments were not modified or substituted for current authority.

### Exact historical repository observations

| Object | Exact evidence | Meaning |
| --- | --- | --- |
| Root commit | `4e7c22a12355d2a53ac64dd5e2a65c3a8cc7e0dd`, 2026-06-08; no parents; tree `17bd6e84a0d81e83b4e6e3fcfc96410e5848161e` | Five-file publisher bootstrap, not a June 7 stable implementation |
| Bootstrap recipe | `chatgpt_fetch_recipe.md`, blob `79fda7c7a9b3c167b0eed3f456596a93d8fc913e` | Embedded OpenF1/FastF1 collection/publishing code |
| June 8 publisher | Commit `942ab7a3f70fc33d084584f3b8db8f83413bd6bd`; `scripts/publish_f1_data.py` blob `1143a29268ad71b196c8259090e027f857c37276` | Source fetching, event/session resolution, readiness and publishing; stable URLs are not stable-engine identity |
| Automation baseline tag | `F1_Automation_Baseline_2026-06-10_READY` → `9e6e7b8ab904b322c2ecdb543148afb8df0c50fb`; complete 381-entry tree | Freeze of the operational ingestion/artifact stack; contains the same current Elite v2 blob, not a proven June 7 stable implementation |
| Historical locker | Commit `6c0c6d128cef9fe880ae177f7254bffb835c2f3b`; locker blob `ffcdbfa9c5add5ba059737afd010e4290aa0165c` | Already maps stable lane to protected name; metadata assignment, not executable lookup |
| Writer path history | Sole returned commit `7f15daf5f85107642be5c90923ba9d4350e32154`; current blob `133c17d41b31a8b2d8934258d3b985d4b10f94ae` | Same label/normalization implementation, not stable recovery |
| Initial actual producer | Commit `4a1117b1c794c763dcf00cc8aa67828db15bb267`; blob `4cf9d24965565b6a094d20f411300e9b0944c6dc` | June 12 generic producer with internal three-lane scoring |
| Producer evolution | Source-discovery commit `af33cb98820baa3b754e740dc2f5aa0d7bd83c09`; frozen-mode commit `67693ce3b5450e1cede3c9e0e5e917bc036d48fa` | The other two returned producer-path changes; no demonstrated protected-engine ancestry |
| Elite path history | Commits `4c8240cc88e5ecf35db7d07beef65973999c0800` and `1d49333230a8ea007261cb4d45e1a0c927d4094f` | June 10 artifact-consumer introduction/update, distinct from a proven June 7 core |
| Exact protected-name path history | `commits?path=Engine_2026-06-07_STABLE` returned an empty array | No recovery candidate at that exact path; does not rule out another historical name |

The baseline tag's companion document is `docs/F1_AUTOMATION_RELEASE_BASELINE_2026-06-10_READY.md`, blob `31d8ddd9f4c557194ca570dad3e3aefff075f0ce`; its stated freeze is automation before forecast consumption. FULL7 policy blob `0f7b9693d9a2751b346313709ca649932fabbb94` similarly protects rank authority while describing an operational support layer. Neither supplies stable executable bytes.

Exact recovery of the generic producer, writer, locker and Elite consumers is possible from these Git objects. **Exact recovery of the protected June 7 stable implementation is not established.** Recovering a similarly named lane, a later algorithm or a workbook view would substitute a different identity.

## Execution-proof requirements and smallest next step

Gate 2B-1 verifier blob `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae`, lines 250–270, requires an engine receipt when a producer declares non-null engine_implementation. It checks separate engine identity, invocation linkage, code/commit, input manifests, source parents, result hash, completion ordering and an external proof binding. It rejects a differently named engine borrowing the wrapper hash. No such engine receipt is created here.

- **A is unsupported:** a wrapper around the current producer would prove current producer execution, not identity with the protected baseline.
- **B is unsupported at this checkpoint:** there is no identified archived stable implementation object to recover exactly.
- **C is the defensible route:** retain HOLD on protected-engine execution claims. The smallest later decision is a separately authorized, targeted identification of the original v17/v24 stable artifact and its complete calculation/runtime dependencies, followed by byte-level custody and identity review. If an exact historical object becomes available, reassess route B; do not reconstruct/invent an engine and give it the old name.

This is a recommendation for Adviser review, not a successor work order. Existing generic-producer and Elite evidence remains valid within its own identity and trust ceilings.

## Pinned current evidence fingerprints

All paths below were fetched at the assessment baseline. Their local Git blob hashes were independently recomputed and matched the connector-reported identities.

| Path | Git blob SHA |
| --- | --- |
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | `af27586668c767de126af829c1131c6bae4634ad` |
| `scripts/forecast_bundles/write_gate_forecast_rows_v1.py` | `133c17d41b31a8b2d8934258d3b985d4b10f94ae` |
| `scripts/forecast_bundles/create_forecast_bundles_v1.py` | `ae7e43e001e905c67949ac35dcb28ae425f7ea8e` |
| `scripts/elite/elite_weekend_engine_v2.py` | `a39a0930f2873a0ff9816624e44aa96c2006beac` |
| `.github/workflows/f1-actual-forecast-producer-v1.yml` | `e115718f2b7fed9f0e87a47b1138b3462b9b6cb1` |
| `.github/workflows/f1-forecast-bundle-locker-v1.yml` | `77fa17a868911b7750d6b02f2becaeae5de079c1` |
| `.github/workflows/elite-weekend-engine-run.yml` | `cabb816a9afb6284b96e7156a36e00ba8302ade5` |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| `docs/F1_PROJECT_ROADMAP_AND_CONTINUITY.md` | `23f7ee1f673a02fa676ca29f4ba1ab9f049e7189` |
| `config/protected_paths.json` | `35af37aa31af31cc968f2b3c2b3cd7a52f97e76b` |

No work-order dependency fingerprint list was supplied for implementation; none was invented as authorization. This task is assessment/documentation only. The observed evidence fingerprints above pin its claims and must be checked again before publication.

## Verification and scope

Static file/call-chain inspection, untruncated component tree inventories, paginated branch enumeration, tag-ref inventory and targeted historical object/path reads support this assessment. Ten primary source blobs passed independent local Git-blob hash recomputation. No model/producer/test module was imported or executed. No test suite was run because this delta adds documentation only; no prior test pass or CI success is newly claimed.

Exactly one documentation addition is authorized. No workflow dispatch/rerun, prediction generation, engine receipt, implementation edit, workbook write, protected-state change, promotion or production activation occurred. Pipedream/Gmail were not used. The Work Result PR remains for independent Adviser review and is not to be merged by this order.

## Final checkpoint conclusions

`stable_engine_current_executable_found: false`
`stable_engine_exact_identity_proven: false`
`stable_baseline_lane_is_execution_proof: false`
`elite_weekend_engine_v2_is_stable_engine: unproven`
`recommended_next_route: C`

Rationale: the current producer, writer, locker and Elite consumer have exact recoverable Git identities, but none has demonstrated byte/history linkage to the protected June 7 v17/v24 baseline. The strongest retrieved historical explanation is the continuity spine, not executable proof. Exact evidence anchors are the pinned current blobs and historical objects above. Keep the stable execution claim on HOLD until an exact original implementation and its identity can be independently established.
