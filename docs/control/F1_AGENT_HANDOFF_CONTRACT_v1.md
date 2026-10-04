# F1 Adviser ↔ Coder Handoff Contract v1

**Contract version:** F1_AGENT_HANDOFF_V1  
**Principle:** COMPRESS COORDINATION, NOT COGNITION.  
**Status:** Review proposal; this PR alone does not activate the convention.

## Purpose and authority

GitHub is the authoritative coordination handoff surface between the Science / Architecture Adviser and Coder / implementation worker once this convention is accepted and activated. This is an execution coordination contract, not a new autonomous-agent architecture.

Current explicit user instruction is highest authority. Newer dated scientific/control documents supersede older controls. A work order may narrow authorized scope but may not silently override durable governance. Conflict or ambiguity => HOLD.

This contract does not replace Git history, DR-002 scientific/provenance receipts, the [Project Roadmap / Continuity Spine](../F1_PROJECT_ROADMAP_AND_CONTINUITY.md), Enhancement Ledger, checkpoints, test evidence or official source evidence.

## Durable controls

Apply existing governance rather than copying it into each work order:

- Protect Engine_2026-06-07_STABLE; keep stable and experimental separate.
- No model promotion without replay/backtest evidence; no accuracy claims without evidence.
- No deletion or overwrite without authorization.
- Official FIA/F1/team/Pirelli facts outrank external interpretation.
- Preserve strict temporal/provenance semantics; later retrieval is not earlier availability.
- HOLD rather than improvise; workbook remains control room, not processor.
- No Pipedream in this handoff; no Gmail transport. This does not authorize removing existing dependencies.
- 2026 F1 has no DRS.

## Select the authorized work order

When told **"Proceed with the current authorized F1 work order."**, enumerate open GitHub Issues and match the exact title prefix **[F1-WO][AUTHORIZED]**. Do not depend on custom labels. Use complete retrieval, not a partial result as proof of uniqueness.

- Zero matches => HOLD_NO_AUTHORIZED_WORK_ORDER.
- More than one => HOLD_AMBIGUOUS_AUTHORIZED_WORK_ORDER.
- Exactly one => retrieve and validate its full current content and authorization.

The title prefix is discovery, not independent proof of authorization. A malformed, conflicting or unauthorized order => HOLD. Coder must not infer work from chat memory when an authorized work order exists. Do not execute another order concurrently.

## Before mutation

Coder must:
1. Read this permanent contract.
2. Read the authorized work order.
3. Fetch fresh main.
4. Compare every declared relevant dependency `path / blob_sha` fingerprint.
5. Verify allowed, protected and prohibited paths/actions.
6. Verify the accepted predecessor state if declared.

`observed_main_sha` records the observed baseline for audit; it is not a global equality lock. Unrelated generated latest/** or history/** movement alone is not a HOLD if all relevant dependency blob SHAs remain unchanged. Any relevant dependency change => HOLD. Any other change affecting interpretation => HOLD even if omitted from the dependency list. Missing/ambiguous fingerprints => HOLD. Never silently broaden dependency scope.

Implementation work requires relevant dependency fingerprints. Stop before mutation if they cannot be verified. New-file targets must be explicitly authorized and checked for unexpected existing content.

## Work Result and delta review

Coder returns implementation in a PR with the structured **Work Result** template. Do not call it a receipt: "receipt" is reserved for DR-002 scientific/provenance classes. A PR is not self-accepting; completion does not mean Adviser acceptance, merge, activation or promotion.

Adviser normally reviews:
accepted predecessor → authorized work order → actual PR delta → tests/evidence → current relevant dependencies.

Do not reconstruct the whole project unless an invalidation condition requires it.

**Never repeat reasoning that has already been proven; never skip reasoning that has not.**

Reopen previously accepted reasoning/evidence only when a relevant dependency changed, evidence changed, later evidence contradicts it, the trust boundary changed, or a control explicitly requires stronger verification. Acceptance must identify the reviewed implementation/evidence; a prior PASS does not cover new changes.

The Adviser records ACCEPT / HOLD / the proposed next decision through GitHub history within explicit authority. Keep accepted/closed work orders for audit. Do not authorize a successor while another authorized work order remains open.

## Work-credit economy and Coder model selection

Work-credit efficiency is a permanent project constraint. Compress coordination, not cognition.

### Model-selection default

Use the **least expensive Coder setting that preserves expected outcome quality**. Do not select a more expensive model/effort merely because the task touches important code.

Default ladder:

- **GPT-5.6 Sol — Medium:** default for merges, docs/evidence work, deterministic bounded implementation, ordinary 1–4 file changes, and well-specified tests.
- **GPT-5.6 Sol — High:** bounded work with subtle correctness/security/provenance/temporal semantics where the architecture and acceptance criteria are already decided.
- **GPT-6 Astra — Low:** open-ended diagnosis, unfamiliar cross-system debugging, or solution discovery where Sol has encountered a concrete ambiguity/HOLD or the Adviser explicitly identifies meaningful unresolved design search.
- **GPT-6 Astra — Medium:** exceptional architecture-critical or multi-system work with genuinely unresolved competing designs or failure hypotheses.
- **GPT-6 Astra — High:** not a normal project setting. Use only with explicit Adviser justification that states why lower settings are inadequate.

Do not use Astra merely for implementation of an Adviser-specified architecture. Escalate after evidence of need, not pre-emptively.

Every authorized work order must state one recommended Coder setting and a one-line reason. If the task changes materially, the Adviser may revise that recommendation in GitHub before execution.

### Coordination-size discipline

Permanent controls belong in this contract and canonical control documents; **do not restate them in each work order**.

A work order should contain only what is necessary to execute the current delta:
objective → exact allowed delta → relevant dependency fingerprints → task-specific acceptance/tests → task-specific HOLD/prohibitions → expected Work Result.

Reference accepted checkpoints/PRs by identifier, reviewed SHA/blob and relevant fact instead of reproducing their full reasoning. Do not duplicate generic trust ceilings, stable-engine protections, activation rules, replay rules, or handoff rules unless the current task changes or tests one of them.

Prefer a concise work order. As a soft budget, keep ordinary bounded orders under roughly **2,000 words**; exceeding that requires a short explicit justification in the order. Safety/scientific precision outranks the word budget, but repetition never does.

### Execution economy

- Do not rerun unchanged accepted tests/evidence as ceremony.
- Do not redownload/reverify accepted artifacts unless a dependency, trust boundary, or evidence claim changed.
- Batch read/reason/test work before final GitHub publication mutations where practical.
- Preserve partial valid work across transport/session interruption only when its bytes/state can be independently re-established; otherwise reconstruct from canonical GitHub state.
- A transport/UI failure is not evidence invalidating scientific work.
- Adviser review should use targeted delta verification and reopen prior reasoning only under the invalidation rules above.

## Human authority and activation

The user remains approval authority for material project decisions. After this system is explicitly accepted and activated, "do it", "proceed", "keep going" and "what's next?" authorize the Adviser to publish ONE bounded GitHub work-order issue. They do not authorize Adviser-side implementation mutation. Coder remains implementation executor.

The user should normally only need to tell Coder: **"Proceed with the current authorized F1 work order."**

This PR creates no live work-order issue. Gate 2B-5 is not begun; its pilot order requires later authorization after review/merge and acceptance/activation of this convention.

## Design ancestry and limits

This refines the existing continuity/control architecture and command/envelope/result concepts. Preserve and reference:
- [Continuity Index](../autopilot_bridge/F1_CONTROL_ROOM_CONTINUITY_INDEX_2026-06-21.md)
- [Bridge Transport and Recovery Lock](../autopilot_bridge/F1_BRIDGE_TRANSPORT_AND_RECOVERY_LOCK_2026-06-21.md)
- [CSE v25 control map](../autopilot_bridge/CSE_V25_TRI_PLATFORM_EXECUTION_HARNESS_CONTROL_MAP_2026-06-22.md)
- [Command validator](../../scripts/autopilot/validate_command.mjs)
- [Status ledger writer](../../scripts/autopilot/write_status_ledger.mjs)

These are historical/control evidence and design ancestry, not authorization to reactivate transport. This convention supersedes none of their scientific evidence and replaces none of those components.

GitHub Issues hold authorized work orders; PRs hold structured Work Results. No mutable CURRENT_STATE.json, work-order database, receipt database, queues, dispatcher, bots or autonomous execution. No workflows/scripts are added. DR-002 remains PROPOSED — NOT ACTIVATED.
