# F1 Bridge Transport and Recovery Lock — R9 Revised Draft Only

R9 revision status: **LOCAL DRAFT ONLY / V20-ALIGNMENT REVISION / NOT LANDED / NO BRIDGE COMMAND / NO PR / NO DISPATCH**  
Revision checkpoint: `CONTINUITY-1F-R9-DRAFT-ONLY-MODULAR-REVISION-FOR-V20-ALIGNMENT`  
Source artifact: `/mnt/data/F1_CONTROL_ROOM_CONTINUITY_AND_BRIDGE_PROCESS_LOCK_2026-06-21.md`  
Source byte length: `19963`  
Source SHA-256: `9406825bfbde70c9068b7455301784d3e08d7cfc399bd49a7c1aa47f27fc86fc`  

This local draft revision is documentation/governance-only. It does not authorize Gmail send, Gmail draft, bridge dispatch, `assistant_patch`, `assistant_merge_pr`, PR creation, merge, GitHub mutation, runtime/status regeneration, processor execution, observer runway, activation review, production automation activation, forecast gate activation, stable-engine modification, canonical workbook write/overwrite, prediction generation, model promotion, model-logic change, or engine-code modification.

Critical limitation carried forward: `02H-4 = LANDED / MERGED / POST-MERGE VALIDATED_WITH_CONTENT_HASH_LIMITATION`. `CONTENT_HASH_READY` is **not claimed**. Direct main file-content SHA was **not returned or validated**.


## 0. Current-governance transport rule

Future bridge work must follow the latest explicit user-provided governance/manual/control document. If v20 operational reliability governance or later queued updates are available, those controls supersede stale v14-era transport language. This module records transport and recovery rules after the large-body continuity dispatch blocker; it does not authorize dispatch by itself.

The blocked R4/R5 path proved that a local `/mnt/data` path passed as Gmail `body_file` is **not** a safely validated default transport route. Do not preserve local `/mnt/data` `body_file` retry as an acceptable default.

## 1. Module purpose

This module is the bridge-specific process and recovery lock. It covers bridge process mapping, observed-success command-pattern discipline, dispatch envelope manifests, large-body transport rules, duplicate-dispatch prevention, returned-status/lag discipline, assistant_merge_pr exactness for future merge gates, soft anomaly recovery, and bridge-specific do-not-do rules.

It intentionally contains **no executable bridge command bodies** and introduces **no invented bridge schemas**.

## 2. Source-section mapping for this module

| Original artifact section | Status in this module |
|---|---|
| 5. GitHub/Gmail/Pipedream bridge process map | Included as conceptual process only; updated for transport blocker. |
| 7. Observed-success command-pattern rule | Included; extended for assistant_merge_pr future merge gates. |
| 8. Common failure/recovery decision tree | Included and expanded for large-body transport exactness. |
| 11. Do-not-do section | Bridge-relevant subset mirrored. |
| 14. Content-hash limitation registry | Mirrored as bridge evidence limitation. |

## 3. Bridge process map — conceptual only

This is a process map, not a runnable command body.

1. **Scope/selection:** control room selects a named checkpoint, evidence outcome, and hard boundaries.
2. **Gate contract:** runner compiles the gate contract from latest governance, observed-success evidence, and the active user instruction.
3. **Draft/review:** local artifacts, command plans, or envelope manifests are prepared only if the gate permits them.
4. **Pre-dispatch validation:** verify recipient, subject, command purpose, target path, expected changed files, hashes, body markers if applicable, duplicate-search terms, and prohibited actions.
5. **Single dispatch:** only when explicitly authorized, send exactly one message using a validated transport path. Do not retry because of lag.
6. **Returned-status protocol:** search exact subject, command type, object IDs, branch/path/SHA terms, status families, and broad recent F1 status terms inside the lag window.
7. **Evidence classification:** claim only the evidence level actually returned: sent only, accepted, PR existence, PR status, merge evidence, post-merge validation, or exact HOLD/error.
8. **Stop at checkpoint:** do not proceed to PR validation, merge, or post-merge validation unless the next named gate is opened.

## 4. Dispatch envelope manifest requirement

Every future bridge dispatch gate must include an envelope manifest before sending:

| Field | Requirement |
|---|---|
| Gate/checkpoint | Exact active checkpoint name. |
| Command type | Exact intended bridge command type, if dispatch is authorized. |
| Recipient | Exact raw Gmail recipient; no invented aliases. |
| Subject | Exact approved subject; no placeholders. |
| Content type | Exact content type. |
| Body source | Inline exact content, supported connector-file body reference, or other explicitly authorized route. |
| Body hash | SHA-256 of source body and, if possible, outgoing body. |
| Body markers | Marker validation when the command format requires markers. |
| Attachments | Must be none unless a future gate explicitly authorizes attachment transport. |
| Expected changed files | Exact count and paths for PR-only documentation/governance landing. |
| Prohibited actions | Explicit list of actions not allowed in the gate. |
| Duplicate search terms | Exact-subject and broad duplicate-search terms. |
| Returned-status search terms | Exact subject, command type, target path, artifact SHA, body SHA, branch/path/PR terms if known. |
| Evidence ceiling | Maximum claim allowed from the checkpoint. |

If any envelope field is missing, placeholder, or unsafe, HOLD. Do not invent it.

## 5. Large-body and `body_file` transport rules

The continuity single-dispatch body was validated locally but blocked by Gmail transport exactness:

| Item | Fact |
|---|---|
| Validated blocked body | `/mnt/data/CONTINUITY-1F_SINGLE_DISPATCH_BODY_LOCAL_COPY_DO_NOT_REUSE_2026-06-21.txt` |
| Body byte length | `30474` |
| Body SHA-256 | `f504a0d1ac9d98452daab5e7ae8dc1d887ace0f8ba344b2ee09e39b4ea1e8685` |
| Blocker | Gmail connector rejected local `/mnt/data` `body_file` path as a valid outgoing body file reference. |
| Result | No Gmail message ID, no thread ID, no dispatch, no duplicate dispatch, no merge. |

Rules carried forward:

- Do not retry local `/mnt/data` `body_file` as an outgoing Gmail body default.
- Do not use attachments as a workaround for body exactness unless a future gate explicitly authorizes attachment transport and the bridge supports it.
- Do not manually reconstruct oversized bodies from memory.
- Inline body transport is allowed only when the runner can validate exact body identity against the local source before send and the gate explicitly authorizes inline send.
- A future **tool-native connector-file body reference** may be valid only if the tool provides an actual connector-file reference object or method and the runner validates it before send.
- A rejected local path and a future tool-native connector-file reference are different things; do not treat them as interchangeable.
- If no exact transport route is available, classify HOLD and do not send.

## 6. Observed-success command-pattern rule

Future bridge commands must follow latest current-governance and observed successful command morphology for the same command type and gate purpose. This rule prevents command-shape drift, subject drift, branch/path drift, and schema invention.

The control room selects checkpoint, goal, evidence outcome, and hard boundaries. The runner compiles the gate contract and chooses a valid execution path. The control room does not write detailed bridge operating instructions, command bodies, schemas, or Gmail transport procedures unless the runner explicitly asks for a missing input such as exact subject, exact recipient, target path, or artifact selection.

This module does not include command bodies or schemas.

## 7. assistant_merge_pr observed-success exactness rule — future merge gates only

`assistant_merge_pr` is merge-gate specific. It must not be used in dispatch, draft, source audit, PR-only landing-prep, or PR status gates.

When a future named merge gate explicitly authorizes `assistant_merge_pr`, the runner must:

1. Verify current-governance merge instructions.
2. Verify PR number, PR title, base, head, changed files, mergeability/check status, expected path, and guardrails from returned evidence.
3. Use the observed-success merge command pattern for the current bridge/manual version.
4. Use an exact merge envelope manifest.
5. Dispatch at most once.
6. Claim merge only from returned merge evidence.
7. Stop before post-merge validation unless the next named gate is opened.

A merge gate must never be inferred from a dispatch or PR-existence gate.

## 8. Duplicate dispatch and returned-status discipline

- Exact-subject duplicate search is required before any authorized dispatch.
- Broad duplicate search must include checkpoint, target artifact/path, artifact SHA, body SHA if applicable, and command type.
- A rejected send attempt with no Gmail message ID is not a successful dispatch, but it must be logged.
- Delayed returned status is not permission to resend.
- Search newest likely returned statuses first, then exact subject, command type, object identifiers, status family, and broad F1 status terms.
- Classify evidence exactly: `DISPATCH_SENT_ONLY`, `DISPATCH_ACCEPTED`, `HOLD_RETURNED_STATUS_NOT_FOUND_AFTER_PROTOCOL`, `HOLD_BRIDGE_ERROR`, or the precise available status.

## 9. Common failure/recovery decision tree

| Symptom | Likely cause | Required response |
|---|---|---|
| Exact recipient or subject missing | Envelope incomplete. | `HOLD_MISSING_EXACT_TRANSPORT_FIELD`; do not invent. |
| Local `/mnt/data` `body_file` rejected | Gmail connector needs tool-native file reference, not local path. | `HOLD_TRANSPORT_TOOL_REJECTED_VALIDATED_BODY_FILE`; do not retry same route. |
| Oversized inline route cannot be verified | Body exactness not safely proven. | `HOLD_TRANSPORT_EXACTNESS_BLOCKER`; do not send. |
| Exact-subject duplicate found | Possible prior dispatch. | HOLD and review returned evidence; do not resend. |
| Returned status delayed | Normal lag. | Run full lag/fanout protocol; no duplicate dispatch. |
| Bridge accepted but PR not found | Receiver lag or receiver-side issue. | Diagnose only in a later authorized validation/diagnostic gate. |
| PR exists but changed files not validated | Evidence is incomplete. | Claim PR existence only. |
| Merge requested from wrong gate | Scope violation. | HOLD; open merge gate only if user authorizes. |
| Soft anomaly without hard-boundary breach | Minor mismatch, stale label, incomplete but nonblocking metadata. | Log anomaly, downgrade claim if needed, route to recovery/clarification; do not invent or duplicate. |
| Hard-boundary breach risk | Action would exceed checkpoint or mutate prohibited area. | HOLD immediately. |
| Main path verified but direct file hash absent | Chain-of-custody limitation. | Claim post-merge validation only with content-hash limitation. |

## 10. Soft anomaly recovery rule

A soft anomaly is an irregularity that does not itself prove failure and does not authorize mutation, retry, or overclaim. Examples: stale search results, broad-search unrelated matches, absent optional metadata, or inconsistent non-control labels.

Soft anomaly handling:

1. Name the anomaly.
2. Identify whether it affects evidence level.
3. Preserve hard boundaries.
4. Downgrade the claim if needed.
5. Recommend a recovery or clarification checkpoint.
6. Do not duplicate dispatch or invent a procedure.

## 11. Bridge-specific hard boundaries

- No Gmail send unless a later named dispatch checkpoint explicitly authorizes it.
- No Gmail draft unless a named draft-review checkpoint explicitly authorizes it.
- No attachment transport by default.
- No local `/mnt/data` `body_file` retry as default outgoing body transport.
- No duplicate dispatch because of lag.
- No manual reconstruction of oversized command bodies from memory.
- No invented schemas, no “cleaned up” command body variants, and no command-body writing by the control room unless explicitly scoped and requested.
- No merge or `assistant_merge_pr` outside a future named merge gate.
- No PR-open/merged/landed/post-merge claims from dispatch evidence alone.
- No runtime/status regeneration, processor execution, observer runway, activation review, production automation, forecast gate activation, stable-engine modification, workbook overwrite, prediction generation, model promotion, model-logic change, or engine-code change.

## 12. Content-hash limitation carried into bridge claims

Bridge returned evidence must not turn 02H-4 into a content-hash-ready lane unless it returns direct main file-content SHA validation in a future named gate.

Safe carry-forward status: `02H-4 = LANDED / MERGED / POST-MERGE VALIDATED_WITH_CONTENT_HASH_LIMITATION`.

Prohibited claim: `CONTENT_HASH_READY`.

## 13. R9 revision commitments

- Removed stale permissive local `body_file` retry language.
- Distinguished rejected local path from future tool-native connector-file body reference.
- Added dispatch envelope manifest requirement.
- Strengthened control-room/runner separation for bridge operation.
- Added no-silent-non-execution expectation by dependency on Runner/Process Lock.
- Added assistant_merge_pr observed-success exactness rule for future merge gates only.
- Added soft anomaly recovery rule.
- Preserved documentation/governance-only scope.
- Preserved 02H-4 content-hash limitation and no `CONTENT_HASH_READY` claim.
- Added no executable bridge command body and no invented schema commitments.
