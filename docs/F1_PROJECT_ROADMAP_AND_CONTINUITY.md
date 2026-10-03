# F1 Prediction Engine — Project Roadmap and Continuity Spine

**Status:** Canonical continuity spine on main — landed via merged PR #124, merge commit `3da3fca55e62356b387a6e2724fa08b42cb60d8e`  
**Prepared:** 2026-10-02  
**Current-state checkpoint:** 2026-10-03  
**Primary implementation route:** 1B / Engine Optimization Active Workstream  
**Repository:** `F1Lllewellyn/f1-data-publisher`  
**Current observed `main`:** `d719fbb10babac3760d33165a77094e983acef06`  
**Current DR-002 status:** **PROPOSED — NOT ACTIVATED**  
**Landed integrity PR:** #123 — Gate 2B-1, MERGED; merge commit `d719fbb10babac3760d33165a77094e983acef06`; reviewed implementation head `f14db284e59ba1d457d9265596164dd6f07518e4`

---

## 0. Purpose of this document

This file is the continuity spine for the F1 Prediction Engine project.

Its purpose is to let a new chat, reviewer, or implementation worker recover the project without replaying months of conversation history or re-auditing the entire repository simply to learn what has already been decided.

It answers five questions:

1. What are we building?
2. How did the project evolve into its current architecture, and why?
3. What has actually been implemented, validated, merged, activated, or merely proposed?
4. What defects and scientific limitations are still open?
5. What is the intended route from the current state to a dependable production prediction system?

This document is not a substitute for detailed gate checkpoints, the Enhancement Ledger, test evidence, or repository code. It is the map that points to them.

---

## 0A. Current state — read this first

**As of 2026-10-03:**

- Active route: **1B / Engine Optimization**.
- Stable engine: **protected**.
- DR-002: **PROPOSED — NOT ACTIVATED**.
- Gate 2A: **MERGED / isolated contract validated** via PR #122.
- Gate 2B-1: **MERGED / isolated receipt-verifier contract landed** via PR #123.
- PR #123 merge commit: `d719fbb10babac3760d33165a77094e983acef06`; reviewed implementation head: `f14db284e59ba1d457d9265596164dd6f07518e4`.
- Continuity spine: **MERGED** via PR #124, merge commit `3da3fca55e62356b387a6e2724fa08b42cb60d8e`.
- Current observed `main`: `d719fbb10babac3760d33165a77094e983acef06`.
- Current scheduled 1B support chain: active.
- Forecast gate: **OFF**.
- Promotion: **NOT ALLOWED**.
- Stable-engine modification: **false**.
- Canonical-workbook overwrite: **false**.
- Downstream readiness/context chain: operational when sources are clean; no automatic stable prediction overwrite.
- Next material decision: **design Gate 2B-2 — Capture Provenance Pilot**.
- Gate 2B-2 is **NOT STARTED**; architecture/read-only design comes first. Coder/Work implementation is not yet authorized.

A future chat should be able to read this block, the authority rules below, and the newest relevant checkpoint before doing any deeper reconstruction.

---

## 1. Authority and source-of-truth rules

The active user remains the final authority for project goals and material modelling decisions.

For stored project state, apply this order:

1. Current explicit user instruction.
2. Newer dated control/checkpoint documents that explicitly supersede older ones.
3. This continuity spine, landed via PR #124 and kept current.
4. Current repository code, PR state, generated artifacts, and validated test evidence.
5. The latest Project Chat Ledger and Enhancement Ledger rules where not superseded.
6. Older continuity/control documents.
7. Prior chat summaries or memory.
8. Older generated artifacts.

Never use an older document merely because it is more detailed if a newer explicit control decision supersedes it.

A file existing in the repository does not prove that its workflow ran, that its claim was true at forecast time, that a prediction was blind, or that a production capability was activated.

---

## 2. Project mission

The goal is not simply to build a spreadsheet that predicts Formula 1 results.

The target system is a dependable, auditable, source-backed F1 evidence and forecasting platform in which:

- public/official evidence is captured with defensible provenance;
- event/session identity is explicit;
- exact forecast inputs can be reconstructed;
- the exact producing code and, where applicable, the exact prediction engine execution can be proven;
- forecasts are locked at known times and cannot be silently rewritten;
- Race Predictions, Fantasy Predictions, and Race Reports consume the same evidence foundation but retain separate contracts and evaluation rules;
- experimental ideas remain separate from the protected stable layer until replay/backtest evidence justifies promotion;
- post-event scoring can determine whether a prediction was correct for the right reason rather than only whether the final order happened to match.

The project should ultimately answer not only **“Who is fastest?”** but **“What evidence was available, what system consumed it, why did it produce this forecast, and did that reasoning survive the outcome?”**

---

## 3. Non-negotiable governance

These rules have survived every major project pivot and remain active unless explicitly superseded:

- Protect `Engine_2026-06-07_STABLE`.
- Keep stable and experimental/challenger layers separate.
- Do not promote model logic without replay/backtest or equivalent validation evidence.
- Do not claim improved predictive accuracy without proof.
- Do not rewrite historical forecasts or retroactively make unproven history “blind.”
- Do not use a later API response as proof that the information was available before an earlier forecast cutoff.
- Distinguish source fact, deterministic calculation, hypothesis, and judgment.
- Official FIA/F1/team/Pirelli facts override external interpretation.
- 2026 F1 has no DRS. Use energy deployment, battery state, regen/harvest, clipping, cooling, dirty-air cost, traffic cost, and attack/defend energy availability.
- The workbook is a control room and reporting surface, not the primary heavy processor.
- Do not delete or overwrite protected project files without explicit approval.
- A successful workflow, PR, commit, hash, or artifact proves only the thing it actually proves.

### Working model for this chat and Coder/Work

The adviser chat performs architecture, scientific review, repo reading, non-duplication analysis, acceptance design, and bounded implementation planning.

Unless the user explicitly asks for direct implementation, short action prompts such as **“do it,” “proceed,” “keep going,” “what’s next?”** mean: prepare the next bounded copy/paste instruction for Coder/Work.

Coder/Work should be reserved for new implementation or mutation work that actually requires it. Do not spend Work credits rerunning expensive validation solely as ritual when relevant implementation state has not materially changed. Cheap read-only freshness checks are preferred; full reruns are justified when relevant code/control files changed, a trust boundary is about to be crossed, or existing evidence is insufficient.

---

## 4. The architecture we are converging on

```text
OFFICIAL / PUBLIC SOURCES
FIA | F1 | teams | Pirelli | OpenF1 | FastF1 | weather/public data
                |
                v
SOURCE CAPTURE + PROVENANCE
exact source identity | hashes | event/session scope | first observation | ingestion
                |
                v
SESSION / EVENT PROCESSING
validation | normalization | anomaly handling | source-readiness state
                |
                v
SHARED EVIDENCE FOUNDATION
frozen evidence set + cutoff contract + source receipts
                |
        +-------+-------+
        |               |
        v               v
  FORECAST / MODEL     REPORT / CONTEXT
  EXECUTION            CONSUMERS
        |
        v
PRODUCT-SPECIFIC CONTRACTS
Race Predictions | Fantasy Predictions | Race Reports
        |
        v
FORECAST LOCK / IMMUTABLE SNAPSHOT
payload hash | lock time | durable storage proof
        |
        v
OUTCOME BOUNDARY + REVISION RECORDS
        |
        v
POST-EVENT SCORING / REPLAY / LEAKAGE AUDIT
        |
        v
EXPERIMENTAL PROMOTION DECISIONS
```

A separate **model-science lane** runs alongside this evidence architecture. Provenance correctness and predictive accuracy are different problems. A perfectly traceable model can still be bad; an accurate backtest can still be contaminated by leakage.

---

## 5. How the project got here — and why

### Phase A — Workbook model expansion and the first calibration lesson

**Period:** early June 2026  
**Primary evidence:** `F1_Model_Project_Context_and_Memory_Summary.md`, workbook update logs, v17/v24 operational reset sheets

The project began as a rapidly expanding workbook-based prediction engine. It accumulated driver, team, track, weather, reliability, tyre, strategy, start, clean-air, engineering, Monte Carlo, feature-attribution, and social/public-signal layers.

A critical architectural choice appeared early: keep large raw row-level datasets outside the workbook. The completed Jolpica ingest, OpenF1 enrichment, and FastF1 targeted-analysis packages became data layers; the workbook stored summaries, KPIs, model inputs, calibration and control-room views.

By v17, the project had a meaningful 2026 backtest/calibration layer. It showed both useful predictive structure and important weaknesses, especially around reliability/live changes and midfield conversion.

Then an important failure mode emerged: v18-v23 added more direct data-driven logic but did not consistently improve practical race-by-race prediction. Some versions over-averaged the system and diluted the driver × track × car × weekend reasoning that made v17 sharper.

That produced the **v24 Operational Reset** on 2026-06-07:

- v17 was restored as the practical operational core;
- v18-v23 were retained as experimental/data-learning history;
- new data became advisory until it could beat the baseline under promotion guardrails;
- candidate factors were to be tested one at a time rather than quietly absorbed into the stable model.

This is the origin of the protected-stable-engine philosophy later represented by `Engine_2026-06-07_STABLE`.

**Why this mattered:** more data and more formulas were not automatically better. The project learned early that complexity can reduce predictive quality and that experimental learning must be separated from operational promotion.

---

### Phase B — Move heavy work into GitHub; keep workbook as control room

**Period:** June 10-12, 2026  
**Primary evidence:** `docs/F1_AUTOMATION_OPERATIONAL_BASELINE_2026-06-10.md`, `docs/F1_WORKBOOK_CONTROL_ROOM_BRIDGE_2026-06-10.md`, forecast/scoring canonical-file notes, Forecast Bundle Locker and gate-orchestrator installation records

The next pivot moved extraction, automation and heavy computation into GitHub while keeping the workbook as a human-readable control room.

The project established:

- automated OpenF1 ingestion;
- Elite Weekend Engine outputs;
- source-readiness and reliability boards;
- workbook/control-room bridge exports;
- forecast dry-review tooling;
- post-race scoring-loop scaffolding;
- race-weekend operating rhythm;
- Forecast Bundle Locker and forecast-gate orchestration infrastructure.

The explicit design statement was: **“The workbook remains the control room. GitHub remains the heavy compute/extraction layer.”**

The no-source commit guard on the Forecast Bundle Locker was an early example of the project learning to fail closed: manual validation should not commit structural placeholder bundles and accidentally make missing forecast data look legitimate.

**Why this mattered:** the workbook had become too important and too fragile to serve as both processor and control room. GitHub offered reproducibility, versioning, automation, code review and historical evidence.

---

### Phase C — Governed bridge and sandbox end-to-end execution

**Period:** June 13-18, 2026  
**Primary evidence:** early GitHub PRs, v31/v32/v33 control-room documents, v33C-v33J roadmap

The project then tried to make ChatGPT-guided work safely actionable through a governed transport chain:

```text
ChatGPT-approved command
-> Gmail command transport
-> Pipedream parser/dispatcher
-> GitHub repository_dispatch / receiver
-> branch / PR / status evidence
```

This required repeated hardening because transport acceptance did not necessarily mean receiver success, PR creation, merge, or post-merge validation.

In parallel, the session-data path was decomposed into gated sandbox stages rather than jumped directly into production. By v33, the intended end-to-end chain had been rehearsed as:

```text
source pull
-> source quality review
-> processor execution
-> sandbox workbook reflection
-> sandbox Forecast Bundle Ledger snapshot
-> Race/Fantasy readiness refresh
-> material-change notification rehearsal
-> final activation decision packet
```

The final v33J artifact explicitly remained **review only**. Production automation, forecast gate, stable-engine changes, canonical workbook writes, production ledger writes, predictions, notifications and model promotion remained blocked.

**Why this mattered:** a pipeline can look complete while still mixing execution, approval, mutation and promotion. The v31-v33 work separated those concerns and created a culture of staged gates.

---

### Phase D — Immutable Forecast Ledger and Enhancement Ledger discipline

**Period:** June 18-20, 2026  
**Primary evidence:** PRs #83-#91, `docs/autopilot_bridge/IMMUTABLE_FORECAST_LEDGER_*`, PR #92 forensic custody manifest, Enhancement 02A-derived documents

The Enhancement Ledger ranked the **Immutable Forecast Ledger / Canonical Event-State Processor + Forecast Bundle Ledger Operating Spine** as a parent-spine enhancement.

PRs #83-#91 built the modular audit foundation:

- foundation rules;
- schema stub;
- validator behavior;
- sample entries;
- integration map;
- sandbox write rehearsal;
- readiness checkpoint;
- later writer rehearsal / validation work.

The intended ledger semantics were already strong for the time:

- append-only;
- revisions become new entries rather than mutation;
- SHA-256 content hashes;
- separate stable and experimental context;
- source readiness before forecast output;
- later scoring consumes prior entries rather than rewriting them.

But the readiness checkpoint was explicit: this was an **audit foundation**, not a production ledger.

Enhancement Ledger v2/v3 then identified **Controlled Production Activation & Multi-Weekend Observer Runway** as the next major priority after v33. The update-discipline rules required preserving completed items for audit, marking status rather than deleting entries, re-ranking when scope changes, checking overlaps before adding enhancements, and treating refinements as refinements rather than duplicates.

A crucial continuity warning followed immediately. PR #92's forensic custody manifest recorded that the physical Project Chat Ledger pack, True Processor package, and the original/v2/v3 Enhancement Ledger packs were not present in that dispatch. Derived repository checkpoints survived, but some original control sources had to be reconstructed from those descendants and prior chats.

The subsequent 02A-02H evidence work repeatedly found that source documents or generated files existing in the repository did not necessarily prove the required runtime/status evidence for observer-runway activation.

**Why this mattered:** the project learned that an immutable-looking artifact is still not the same as authenticated provenance. Content hashes answer “did these bytes change?” They do not automatically answer “who created them, what exact source was available then, what code actually executed, or was this truly blind?”

---

### Phase E — Continuity Specialist and bridge hardening

**Period:** June 20-24, 2026  
**Primary evidence:** PRs #102-#116, `F1_CONTROL_ROOM_CONTINUITY_INDEX_2026-06-21.md`, `CSE_V25_TRI_PLATFORM_EXECUTION_HARNESS_CONTROL_MAP_2026-06-22.md`, bridge transport/recovery documents

The project invested heavily in continuity because long chats, bridge failures, schema drift and ambiguous evidence were themselves becoming system risks.

The Continuity Specialist work formalized:

- a control-room continuity index;
- tool/evidence firewalls;
- strict SEND_LOCK / duplicate-send controls;
- receiver-validator parity;
- lag-aware returned-status interpretation;
- exact transport behavior;
- the rule that `DISPATCH_ACCEPTED` proves only transport acceptance;
- chain-of-custody wording that distinguishes GitHub-validated merge state from unproven bridge execution state.

This period also exposed how easily a control process could become more complicated than the work it was protecting.

The enduring lesson is not that the Gmail/Pipedream bridge is the desired final architecture. It is that the project must mechanically separate **requested action, transport, receiver execution, PR state, merge state and post-merge validation**.

**Why this mattered:** human/AI workflow state must be as auditable as model state. A system that protects predictions but loses track of whether its own commands executed is not dependable.

---

### Phase F — Source authority and operational writer hardening

**Period:** September 16-21, 2026  
**Primary evidence:** `docs/GRID_PROVENANCE_CHECKPOINT_2026-09-16.md`, PRs #117-#121, `docs/PROJECT_CHECKPOINT_2026-09-21.md`

The September work exposed two major classes of defects.

#### 1. Source authority / final-grid provenance

The session processor correctly discovered that OpenF1 race/sprint `starting_grid` data may be absent and that the corresponding qualifying session can hold a plausible grid. But Madrid supplied the decisive counterexample: an OpenF1 grid captured before the race did not reflect the later FIA final-grid revision moving a car to the pit lane.

The project therefore established that:

- qualifying order must never simply be sorted into a race grid;
- OpenF1 starting-grid data can be useful evidence but cannot certify the official FIA final grid;
- `official_final_grid_verified=false` and `forecast_as_of_eligible=false` must remain explicit until independent authority/timing is proven;
- a hash difference proves a change between captures but does not date when that source changed;
- historical API availability cannot prove forecast-time availability.

This became one of the intellectual foundations of DR-002.

#### 2. Scheduled-writer / safe-push failures

PRs #117-#121 addressed stale queued checkouts, safe-push collisions and a hidden worktree mutation caused by Auto-Repair safe-test preflight.

The project refused the tempting but unsafe fixes: force push, stash/reset, broad staging, or weakening conflict guards.

Instead it:

- refreshed scheduled jobs to the current branch tip;
- reproduced the worktree mutation;
- moved the peak preflight to runtime-only diagnostics;
- preserved output ownership boundaries;
- made rejected-push dirty-path diagnostics explicit;
- validated the ordinary deployed path after merge without falsely claiming that every future rebase conflict was proven safe.

**Why this mattered:** operational robustness depends on exact ownership and evidence. A successful later run does not retroactively explain an earlier failure, and a safety guard should not be weakened just because it is inconvenient.

---

### Phase G — DR-002: move from “auditable-looking” to scientifically defensible forecast integrity

**Period:** September 20-29, 2026  
**Primary evidence:** DR-002 architecture discussion, Gate 1 read-only audit, PR #122, PR #123

The central architectural decision was clarified:

> One shared, source-backed evidence foundation should support multiple distinct products with separate contracts and separate evaluation.

This was not a proposal to replace the repository's existing forecast infrastructure. It was a proposal to harden it so that the system can later prove what each product knew and when.

The critical time distinction became:

```text
evidence cutoff
!= forecast generation time
!= forecast deadline
!= forecast lock time
!= publication time
```

A later API response can never be used to prove earlier availability.

#### DR-002 Gate 1 — read-only audit findings

The audit found six major defects:

1. **Blind eligibility bug** — existing bundle logic could mark a forecast blind merely because source rows existed. A real Baku `post_event` bundle was marked blind despite its post-race lock.
2. **Insufficient temporal provenance** — copied/generated/locked timestamps were not the same as source `first_observed_utc`.
3. **Event/session contamination risk** — the producer discovered broad aggregate source files rather than a frozen event/session-qualified evidence set. The Baku post-qualifying producer generated 28 driver rows from season-wide inputs.
4. **Misleading stable-engine lineage** — a lane/config label such as `stable_baseline` / `Engine_2026-06-07_STABLE` did not prove that protected engine code actually executed.
5. **Model-science debt** — hard-coded priors, weights, reliability adjustments and probability transforms existed without being validated by DR-002. They were deliberately kept out of the integrity gate rather than silently changed.
6. **Temporal validation scaffolding** — the repository had useful validation pieces but could not yet claim that leakage was solved.

The audit also preserved a crucial distinction: `race_result` and `post_event` are outcome/evaluation gates and can never be prospective/blind forecast gates.

#### Gate 2A — isolated integrity contract

PR #122 was merged on 2026-09-27 as merge commit:

`09a222b4a089f561378518d1e27b2b8c5d40806f`

Gate 2A added an isolated deterministic classifier/schema/tests without wiring it into production.

Forecast states:

- `VALID_LOCKED`
- `HOLD`
- `MISSED_DEADLINE`
- `SUPERSEDED`
- `OUTCOME_AWARE_EVALUATION_ONLY`
- `TEMPORAL_ELIGIBILITY_UNPROVEN`

Revision-event state:

- `POST_CUTOFF_REVISION`

Only `VALID_LOCKED` is blind-validation eligible.

Gate 2A also established that a separately named engine requires independent execution provenance:

- engine implementation identity;
- engine execution ID;
- engine code SHA-256;
- engine execution proof reference.

A wrapper hash or lane name cannot stand in for a distinct engine.

Gate 2A's 41 offline tests prove classifier behavior. They do not prove a real stable-engine execution, real source observation, or production trust.

#### Gate 2B-1 — offline receipt/verifier foundation

At the 2026-10-02 checkpoint, PR #123 implemented the next bounded layer and was open/unmerged. It was science/architecture reviewed and merged on 2026-10-03 as `d719fbb10babac3760d33165a77094e983acef06`; the offline receipt/verifier foundation is now on main.

It adds one strict receipt envelope with seven typed receipt classes:

- `source_capture`
- `engine_execution`
- `producer_execution`
- `normalization`
- `forecast_lock`
- `outcome_boundary`
- `revision`

The verifier checks deterministic graph, scope, hash, time and parent-child consistency against separately supplied `verified_receipt_bindings`.

The critical trust rule is explicit: **a receipt cannot authenticate itself**. A caller-supplied external binding is only an interface. Gate 2B-1 does not implement PKI, HMAC, signing, authenticated clocks or production issuer trust.

The reviewed PR contains exactly six files, reports 41 Gate 2A + 75 Gate 2B-1 passing tests, and has no production integration.

**Why DR-002 exists:** the older Immutable Forecast Ledger work answered “how do we keep append-only forecast records?” DR-002 asks the harder question: **“Can we prove that the evidence, execution and lock represented by that record were actually valid at the time claimed?”**

---

## 6. Current operational state — 2026-10-03

Older June documents repeatedly say “production automation OFF.” That statement must now be interpreted historically and by scope.

The repository has scheduled operational support chains producing `latest/` and `history/` artifacts. The operational evidence observed on 2026-10-02 showed:

- the 1B control-room scheduled chain may execute `full_run_chain`;
- the current source/session processor is producing live readiness artifacts;
- downstream Race Predictions, Fantasy Predictions and Race Reports context handoffs can be marked ready when source/workbook state is clean;
- the decision mode remains `decision_only_no_external_send`;
- `forecast_gate_activated=false`;
- `promotion_allowed=false`;
- `stable_engine_modified=false`;
- `canonical_workbook_overwrite=false`;
- sandbox workbook refreshes are used rather than silently overwriting the protected workbook.

This means **operational support automation is active**, while **forecast-gate activation, stable promotion and DR-002 production enforcement remain off**.

Current observed `main` is:

`d719fbb10babac3760d33165a77094e983acef06`

At the 2026-10-02 checkpoint (`0e757d1b54a1c9feb100b64216af0d107a482468`), the repository had advanced since the previously reviewed `84aa38cc...` through scheduled/generated `latest/` and `history/` activity. That targeted comparison found no changes to the protected DR-002 implementation/contract files used for the Gate 2B-1 review. PR #124 subsequently landed the continuity spine, and PR #123 landed the isolated Gate 2B-1 foundation; neither landing activated DR-002 or changed production/model/workbook behavior.

A newly generated `cross_car_microdelta_forensics` output on 2026-10-02 correctly returned `no_action` because the required driver-session summary schema was unavailable. It explicitly records no stable-engine modification, no canonical-workbook overwrite and no promotion. It is experimental evidence, not a new main-roadmap activation.

---

## 7. Status matrix

| Component / decision | Current status | What is proven | What is NOT proven |
|---|---|---|---|
| `Engine_2026-06-07_STABLE` | Protected baseline | Stable/experimental separation is a durable governance rule | Current lane/config labels do not prove the stable engine actually executed |
| Raw Jolpica/OpenF1/FastF1 layers | Established data inputs | Useful source and KPI coverage exists | Historical first availability is not automatically proven |
| Session Data Processor | Operational support layer | Event/session validation, source hashes, source-readiness and grid safeguards exist | Authenticated `first_observed_utc` and official final-grid authority are not universally proven |
| Workbook | Control room / protected | Human-readable KPI/readiness reflection and sandbox refreshes | Not the primary processor and not to be silently overwritten |
| Forecast producer / source writer / locker | Existing infrastructure | Forecast rows, normalization, bundle history and lock-like artifacts exist | Current live semantics do not yet satisfy DR-002 integrity requirements |
| Immutable Forecast Ledger Enhancement 01 | Historical audit foundation | Append-only/hash/revision principles were established | Production immutable provenance/authentication was never completed |
| v33 sandbox chain | Completed rehearsal / review-only | End-to-end gated process could be decomposed and rehearsed | It was not production activation |
| Continuity Specialist / bridge governance | Historical operational control | Strong lessons on transport, evidence states, duplicate sends and chain of custody | Pipedream/Gmail bridge is not the desired final processing architecture |
| Gate 2A / PR #122 | **Merged / isolated validated** | Deterministic forecast classification and fail-closed integrity contract | No production enforcement or real execution authentication |
| Gate 2B-1 / PR #123 | **MERGED / isolated validated** | Offline receipt graph/verifier behavior, 41+75 tests; landed via merge commit `d719fbb10babac3760d33165a77094e983acef06` | No live source-capture receipt adapter, production authentication, authenticated historical first-observation proof, live forecast repair or DR-002 production enforcement |
| DR-002 overall | **PROPOSED — NOT ACTIVATED** | Architecture and initial isolated contracts exist | Production leakage/provenance problem is not solved |
| `pre_qualifying` gate | Proposed only | Architectural need identified | Not active |
| `final_pre_race` gate | Proposed only | Need for independently verified FIA final grid identified | Not active; no final deadline policy activated |
| `race_result` / `post_event` | Evaluation/outcome gates | Can support scoring/evaluation | Never blind prospective forecast gates |
| Model weights / priors / probability transforms | Existing implementation | Current algorithms can run | Scientific optimality / promotion-worthiness remains a separate replay/backtest question |

---

## 8. Known live defects and unresolved scientific debt

These remain open unless a later dated checkpoint explicitly closes them.

### A. Temporal provenance

The live system does not yet universally prove:

- source event time;
- publisher time;
- first observed time;
- ingestion time;
- evidence cutoff;
- forecast generation;
- forecast deadline;
- forecast lock;
- publication.

These timestamps must remain semantically distinct.

### B. Blind-eligibility legacy behavior

Legacy bundle logic can still present source existence as blind eligibility. Gate 2A detects/defines the correct state model but is not wired into production.

### C. Event/session containment

The generic forecast producer has used broad/aggregate source files. A season-wide file hash is not equivalent to an event/session-scoped source receipt.

### D. Stable-engine proof

`stable_baseline` or `Engine_2026-06-07_STABLE` configuration text is not execution proof.

### E. FIA final-grid authority

OpenF1 qualifying/starting-grid evidence cannot automatically certify the FIA final grid. Official final-grid timing, late penalties, pit-lane starts, withdrawals and revisions require independent authority handling.

### F. Lock authenticity / durable storage

A copy timestamp, history directory or stored payload hash does not by itself prove that a forecast became immutable at the claimed time.

### G. Revision completeness

A revision receipt can prove the revision supplied to the verifier. It cannot prove that a production observer discovered every relevant revision unless the observation system itself is complete and trusted.

### H. Receipt trust

Gate 2B-1's external binding interface is intentionally not a production authentication system. Issuer trust, signed attestations, clock trust, durable storage and policy authority remain future integration work.

### I. Model science

Hard-coded model priors/weights/reliability transforms/probability mappings need separate replay/backtest evaluation. DR-002 must not quietly rewrite these while solving provenance.

### J. Existing CLI integration defects

The source-writer and bundle-locker workflows have pre-existing `--commit-outputs` argument mismatches with their Python parsers. This is real debt but intentionally out of scope for Gate 2B-1.

### K. Pipedream / 1C retirement

The repository-visible bridge route historically included Gmail -> Pipedream -> GitHub dispatch. September checkpointing still warned not to declare it retired without reconciling external triggers, credentials and consumers. The strategic direction is dependable GitHub-based operation without unnecessary Pipedream dependency, but removal must be separately verified.

---

## 9. DR-002 forward roadmap

### Gate 2B-1 — Offline receipt/verifier contract

**State:** implementation completed; science/architecture reviewed; PR #123 merged as `d719fbb10babac3760d33165a77094e983acef06`. Gate 2B-1 is now the landed offline receipt/verifier foundation.  
**Next material decision:** design Gate 2B-2 — Capture Provenance Pilot; architecture/read-only design first, with Coder implementation not yet authorized.  
**Do not redo the implementation simply to repeat already-completed work unless relevant code changed.**

### Gate 2B-2 — Capture provenance pilot

**State:** NOT STARTED. Architecture/read-only design must precede separately authorized Coder implementation.

**Goal:** adapt one bounded existing capture path to emit trustworthy, event/session-scoped source-capture evidence without redesigning every source system at once.

Likely best starting point: Session Data Processor, because it already has event/session identity, raw-response hashes, normalized hashes, validation state and explicit grid provenance.

Required design work before Coder implementation:

- choose one source/end-point pilot;
- define exactly what `first_observed_utc` means operationally;
- distinguish raw-response hash from normalized-data hash;
- define external binding/authentication boundary without pretending Gate 2B-1 authenticates it;
- prevent aggregate season files from masquerading as scoped evidence;
- prove fail-closed behavior when identity/timing is ambiguous.

### Gate 2B-3 — Event/session containment + execution shadow adapter

**Goal:** ensure forecast inputs are frozen to the correct event/session and create shadow execution evidence for producer/engine runs.

Must address:

- broad source discovery;
- driver-universe contamination;
- exact frozen input manifest;
- producer implementation/commit/code/execution ID;
- distinct engine proof where a separate engine is claimed.

No production enforcement yet.

### Gate 2B-4 — Lock / outcome-boundary / revision proof integration

**Goal:** create credible lock provenance and explicit outcome/revision boundaries without rewriting prior forecasts.

Must address:

- exact locked payload bytes;
- durable storage reference and authentication;
- explicit lock time;
- outcome availability boundary;
- pre-cutoff versus post-cutoff revision handling;
- no silent fallback to knowingly obsolete forecasts.

### Gate 2B-5 — Full shadow integrity assessment

**Goal:** run the entire evidence -> execution -> lock chain in shadow beside the existing system and measure where live artifacts fail the new contract.

No primary scoring/promotion should depend on this until the failure modes are understood.

### Gate 2B-6 — Replay and leakage evidence

**Goal:** determine whether historical/replay forecasts can satisfy the integrity contract without using outcome-aware or later-available data.

This is where leakage claims must finally be tested rather than inferred.

### Gate 2B-7 — Separately approved production enforcement

**Goal:** only after shadow/replay evidence is satisfactory, decide whether the integrity contract should become a production gate.

This requires an explicit approval decision. It is not implied by completing earlier gates.

---

## 10. Forecast/product architecture

### Shared evidence, separate products

The central evidence system should support multiple independently evaluated outputs rather than one monolithic forecast.

#### Race Predictions

Needs exact forecast contracts, forecast-time evidence, stable output, experimental deltas, confidence/risk flags and later result scoring.

#### Fantasy Predictions

Uses the same evidence foundation but requires separate value/risk/budget/constructor/chip/transfer logic and separate evaluation. No automatic transfer or chip execution.

#### Race Reports

Consumes source-backed context and outcome evidence for narrative/reporting. It is not a blind forecast product simply because it shares upstream data.

### Existing and proposed gates

Existing forecast-ish gates:

- `pre_weekend`
- `post_fp3`
- `post_qualifying`

Proposed only:

- `pre_qualifying`
- `final_pre_race`

Outcome/evaluation gates:

- `race_result`
- `post_event`

`race_result` and `post_event` must always remain outcome-aware evaluation states.

The `final_pre_race` concept requires independently verified FIA final-grid evidence and a defined deadline policy. A T-30 concept was discussed but **has not been activated as policy**.

---

## 11. Revision semantics already decided

The project has established the following conceptual behavior:

- If an official revision is first observed before the forecast deadline, the prior final forecast may become `SUPERSEDED`; a replacement must still meet the deadline.
- If the replacement misses the deadline, classify it `MISSED_DEADLINE`; do not silently fall back to a knowingly obsolete prior forecast for primary scoring.
- If a revision is first observed after the cutoff/deadline, preserve the original locked forecast and record `POST_CUTOFF_REVISION` separately.
- Exactly-at-deadline behavior remains intentionally fail-closed pending a specific policy decision.

These are integrity semantics, not yet full production enforcement.

---

## 12. Evidence-time vocabulary

Future code and documentation should use these terms precisely:

| Field | Meaning |
|---|---|
| `event_time_utc` | When the real-world event represented by the datum occurred, if meaningful |
| `publisher_time_utc` | When the source claims it published the information, if known |
| `first_observed_utc` | First time our trusted observation system actually observed this exact source state |
| `ingested_utc` | When our system ingested/persisted that observed source state |
| `evidence_cutoff_utc` | Latest evidence observation allowed for a forecast contract |
| `forecast_generation_utc` | When the producer generated the forecast payload |
| `forecast_deadline_utc` | Last permissible time for that forecast product/gate |
| `forecast_lock_utc` | When the exact forecast payload was locked/committed under the contract |
| publication time | When a human-facing prediction/report was published; never substitute this for lock or evidence time |

Never infer one of these from another merely because the values are close.

---

## 13. Model-science roadmap — deliberately separate from DR-002

Once integrity is strong enough to support trustworthy replay, evaluate the actual model separately.

Major questions include:

- Do current hard-coded priors improve forecasts versus the protected baseline?
- Are probability mappings calibrated?
- Which OpenF1/FastF1 features add predictive value rather than explanation-only value?
- Are reliability and DNF hazards calibrated without outcome leakage?
- Do driver × track × car interactions outperform generic averaging?
- Which candidate engineering hypotheses survive multi-event tests?
- Are there event families where v17/stable-style dynamic reasoning remains stronger than newer aggregate formulas?

Promotion should require replay/backtest evidence and should remain independent of whether the provenance pipeline is technically valid.

---

## 14. Continuity lessons that must not be forgotten

### File existence is not execution proof

This lesson recurs from the v33/02A-02H recovery work through DR-002.

### Content hashes are necessary but not sufficient

They prove byte identity, not truthful timing, issuer identity, source completeness or engine execution.

### “Latest” is dangerous without scope

A latest file can be correct bytes for the wrong event, wrong session or wrong point in time.

### A successful later run does not explain an earlier failure

Operational evidence must remain specific to the path actually exercised.

### Safety guards should be diagnosed, not disabled

The PR #117-#121 work showed the value of fixing the dirty-worktree producer rather than weakening safe-push protection.

### More model complexity is not automatically better

The v24 reset remains the project’s clearest model-science warning.

### Later data cannot make an old forecast blind

This is the central temporal-integrity rule.

### Outcome-aware products must be labelled outcome-aware

Race reports, post-event analysis and scoring are valid products, but they must never be presented as prospective forecasts.

---

## 15. Historical continuity artifacts and how to interpret them

### `F1_PROJECT_CHAT_LEDGER_v2.md`

Useful for durable routing/governance and the original shared-intelligence concept. It correctly establishes 1B as the active heavy-engine workstream and stable/experimental separation. It is dated June 17 and is not a complete current status map.

### Enhancement Ledger original / v2 / v3

Durable recovered rules remain important:

- preserve completed items for audit;
- update status instead of deleting;
- re-rank when scope changes;
- check overlap before adding items;
- refinements are not duplicate enhancements;
- Chat 7 is enhancement tracking only;
- implementation belongs in the active Engine Optimization workstream.

However, PR #92 explicitly recorded missing physical control sources in that dispatch, including:

- `F1_Project_Chat_Ledger_Pack_2026-06-16_v2_Unified_Ledger.zip`;
- `F1_1B_True_Processor_Automation_Execution_Package_2026-06-12_v1.zip`;
- `F1_Enhancement_Ledger_Pack_2026-06-18.md`;
- `F1_Enhancement_Ledger_Pack_2026-06-18_v2_Post_v33.md`;
- `F1_Enhancement_Ledger_Pack_2026-06-18_v3_Update_Discipline.md`.

Do not pretend the repository contains those source files when it does not. Use recovered durable rules and repository descendants honestly.

The current `ledgers/locked_forecast_ledger_v2.jsonl` file on `main` is empty. Its path is historical scaffolding, not evidence of an operational immutable forecast ledger.

### `F1_CONTROL_ROOM_CONTINUITY_INDEX_2026-06-21.md`

Useful historical continuity design, but the file itself says it is an R9 local draft/revision and warns against fossilizing stale governance. It is not a substitute for current state.

### `CSE_V25_TRI_PLATFORM_EXECUTION_HARNESS_CONTROL_MAP_2026-06-22.md`

Useful for command/evidence-state discipline and bridge chain-of-custody lessons. It is historical operational governance, not current forecast architecture.

### `docs/GRID_PROVENANCE_CHECKPOINT_2026-09-16.md`

Still highly relevant to official-grid authority and the rule against backdating API availability.

### `docs/PROJECT_CHECKPOINT_2026-09-21.md`

Authoritative checkpoint for the scheduled-writer / safe-push repair and transition into DR-002-era work.

### `docs/DR002_GATE2A_CHECKPOINT_2026-09-27.md`

Authoritative merged Gate 2A checkpoint.

### `docs/DR002_GATE2B1_CHECKPOINT_2026-09-29.md`

Now on main via merged PR #123 (`d719fbb10babac3760d33165a77094e983acef06`). It is the detailed checkpoint for the landed offline Gate 2B-1 foundation.

---

## 16. Repository breadcrumb index

Use these as the preferred detailed evidence trail rather than replaying chats:

| Era | Repository evidence |
|---|---|
| GitHub operational baseline | `docs/F1_AUTOMATION_OPERATIONAL_BASELINE_2026-06-10.md` |
| Workbook/control-room split | `docs/F1_WORKBOOK_CONTROL_ROOM_BRIDGE_2026-06-10.md` |
| Forecast/scoring/control-room setup | `CURRENT_CANONICAL_FILES_CONTROL_ROOM_FORECAST_SCORING_2026-06-10.md` |
| Session-processor roadmap | `docs/autopilot_bridge/F1_CHAT_LEDGER_CONTINUITY_V31D_NEXT_STEPS_2026-06-16.md` |
| v33 final review-only chain | `docs/autopilot_bridge/V33J_FINAL_ACTIVATION_DECISION_PACKET_2026-06-18.md` |
| Immutable ledger foundation | `docs/autopilot_bridge/IMMUTABLE_FORECAST_LEDGER_FOUNDATION_2026-06-18.md` |
| Immutable ledger integration/readiness | `docs/autopilot_bridge/IMMUTABLE_FORECAST_LEDGER_*_2026-06-18.md` |
| Missing-control-source custody | PR #92 / `docs/forensics/ledger_source_recovery/2026-06-18/SOURCE_CUSTODY_MANIFEST_2026-06-18.md` |
| Controlled activation/observer runway | `docs/autopilot_bridge/ENHANCEMENT_02A_CONTROLLED_ACTIVATION_PREFLIGHT_2026-06-19.md` and derived 02-series docs |
| Continuity/bridge control | `docs/autopilot_bridge/F1_CONTROL_ROOM_CONTINUITY_INDEX_2026-06-21.md`, `CSE_V25_TRI_PLATFORM_EXECUTION_HARNESS_CONTROL_MAP_2026-06-22.md` |
| Official-grid provenance | `docs/GRID_PROVENANCE_CHECKPOINT_2026-09-16.md` |
| Writer/safe-push operational checkpoint | `docs/PROJECT_CHECKPOINT_2026-09-21.md`, PRs #117-#121 |
| DR-002 Gate 2A | PR #122 / `docs/DR002_GATE2A_CHECKPOINT_2026-09-27.md` |
| DR-002 Gate 2B-1 | PR #123 / `docs/DR002_GATE2B1_CHECKPOINT_2026-09-29.md` |

Important external Project-file breadcrumbs:

- `F1_Model_Project_Context_and_Memory_Summary.md` — early model/workbook/data-layer state.
- `F1_PROJECT_CHAT_LEDGER_v2.md` — routing/governance/shared-intelligence rules.
- historical workbook variants containing v17/v24 operational reset evidence.

---

## 17. New-chat startup protocol

A future chat should not begin by re-reading the entire repository.

Start here:

1. Read this continuity spine.
2. Apply current explicit user instructions and any newer dated control document.
3. Read the newest relevant detailed checkpoint only.
4. Check current `main` SHA and open PR state.
5. Compare only the implementation/control paths relevant to the next gate.
6. If no relevant implementation changed, do not waste Work credits rerunning old work solely for ceremony.
7. If the user asks “what’s next?”, identify the current unresolved decision/gate and prepare a bounded Coder/Work instruction only if implementation is actually needed.
8. Never infer activation, merge, blind eligibility, source availability or engine execution from filenames, branch names or labels.

For enhancement ideas, route to Chat 7 and check the Enhancement Ledger/active workstream for overlap before adding a new item.

---

## 18. Update discipline for this continuity spine

Update this document whenever one of the following materially changes:

- a gate moves from proposed -> implemented -> validated -> shadow -> production active;
- a PR central to the roadmap merges, closes unmerged, or is superseded;
- a known defect is actually resolved;
- a new trust boundary is introduced;
- a product/gate contract is activated or retired;
- stable-engine or promotion governance changes;
- the implementation workstream/routing changes;
- Pipedream/bridge architecture is retired or replaced;
- a major new model-science decision changes the protected baseline;
- a newer control document supersedes this state.

Do not delete old milestones. Mark them **superseded**, **historical**, **closed**, or **retained for audit**.

The top **Current State** block should be kept short and current. Detailed evidence belongs in dated checkpoints, not copied repeatedly into this file.

---

## 19. Current-state maintenance rule

The authoritative short state block is near the top of this document under **0A. Current state — read this first**. Update that block before changing deeper historical sections. It should always contain the active route, DR-002/gate status, stable/promotion/workbook controls, current main/open-PR anchors, and the single next material decision.

Do not allow the short block to become a second history log. Historical detail belongs in the dated phases and checkpoint documents.

---

## 20. What this document must never be used to claim

This continuity spine does **not** prove:

- that current predictions are accurate;
- that historical forecasts were blind;
- that the protected stable engine executed in a particular historical artifact;
- that first-observation timestamps are authenticated;
- that a forecast lock is cryptographically or operationally immutable;
- that all revisions were observed;
- that DR-002 is active in production;
- that `pre_qualifying` or `final_pre_race` gates are active;
- that Pipedream is safe to cancel;
- that a model enhancement should be promoted.

Those claims require their own evidence.

---

## 21. Core direction in one paragraph

The F1 Prediction Engine started as a fast-growing workbook model, learned that more complexity could make forecasts worse, protected its strongest practical baseline, moved heavy computation and data collection into GitHub, built staged sandbox and audit infrastructure, learned through bridge and runtime failures that file existence and hashes do not equal execution truth, learned through FIA grid provenance that source correctness and timing are inseparable, and is now building DR-002 so every future prospective forecast can eventually prove **what evidence was known, when it was known, what exact code and engine consumed it, what payload was produced, when it was locked, and how later revisions/outcomes are kept separate**. Only after that integrity foundation survives shadow and replay testing should the project enforce it in production or use it to support scientific model promotion.

