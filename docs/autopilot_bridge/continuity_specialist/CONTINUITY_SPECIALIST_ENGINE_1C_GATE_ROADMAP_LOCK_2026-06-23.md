# Continuity Specialist Engine — 1C Gate Roadmap Lock

**Control artifact date:** 2026-06-23  
**Purpose:** Preserve the successful 1C/V33/v60 gate operating formula so every future Continuity Specialist chat starts from the same disciplined execution shape.

## Status

This artifact is a control-room/governance layer for the Continuity Specialist Engine. It does not modify runtime code, stable engine files, canonical workbook files, predictions, or production automation.

## Prime Directive

Before any gate action, the assistant must answer one question:

> What did successful 1C do at this exact gate, and am I still inside that shape?

The assistant must not proceed from intuition, momentum, or partial evidence. Every gate begins by mapping the successful 1C roadmap, executing only the next valid 1C step, and validating the result against that roadmap.

## 1C Gate Roadmap Lock

Before any gate action:

1. Identify the exact active gate and gate family.
2. Map the successful 1C roadmap for that gate family.
3. Identify the matching successful fixture, status pattern, or doctrine source.
4. Compare the current state against that roadmap.
5. Execute only the next valid 1C step.
6. Verify returned evidence against the roadmap.
7. If drift is inside the same gate, correct once back to 1C.
8. If correction would require resend, mutation, alternate transport, manual workaround, duplicate risk, or a new command family, stop and report.

## Permanent Success Formula

```text
1C roadmap first
→ fixture/source match
→ one valid step
→ bounded latency
→ evidence read
→ doctrine verification
→ only then continue
```

## What This Prevents

This rule exists to prevent the repeated failure pattern:

```text
evidence looks good
→ momentum rises
→ assistant jumps to next action
→ failure is explained afterward
```

The required 1C pattern is:

```text
identify gate family
→ map successful 1C fixture
→ verify next step is valid
→ act once
→ wait/read with bounded latency
→ verify evidence
→ continue only on proof
```

## Core Prohibitions

Unless an explicitly approved 1C roadmap requires it, the assistant must not:

- retry a sent command without duplicate-send analysis,
- use a new transport route,
- recommend a manual workaround as the default 1C path,
- jump from read-only verification directly to mutation when a bridge-native dry-run exists,
- claim a merge, close, dispatch, or post-merge state without returned evidence,
- continue after a failed gate,
- blend gates,
- invent a recovery outside 1C doctrine,
- change stable engine files,
- overwrite canonical workbook files,
- activate production automation,
- generate predictions,
- promote a model.

## Mutation Discipline

For any mutation-capable gate, use this rule:

```text
No mutation-capable action runs directly after read-only verification if a bridge-native dry-run/gate-pass path exists.
```

For merge gates, the canonical sequence is:

```text
PR_STATUS_READY
→ assistant_merge_pr dry_run:true
→ MERGE_GATE_PASS
→ assistant_merge_pr dry_run:false
→ MERGED
→ post-merge read-only inventory
```

If the dry-run/gate-pass step fails, the actual mutation step is not allowed.

## Bounded Latency Doctrine

The assistant must not treat one missing Gmail search result as a final failure. 1C expects asynchronous bridge latency.

For status waits, use bounded read-only polling:

1. Search exact expected status subject.
2. Search exact status/body marker.
3. Search explicit blocked/error statuses.
4. Search `PIPEDREAM_ERROR` for the command family.
5. Search newest broad `F1 1C STATUS` packets relevant to the PR/checkpoint.
6. Read only candidate messages with `read_email`.
7. Verify object identity before claiming PASS.
8. If still missing after the bounded search pattern, HOLD.
9. Never resend during the wait window.

## Evidence Standard

A gate is not complete until there is returned evidence. Evidence must match object identity:

- command family,
- PR number or checkpoint identity,
- title/subject marker,
- base/head/head SHA where relevant,
- changed-file count where relevant,
- allowed path prefix where relevant,
- status value,
- safety fields,
- next-step field where relevant.

## Safety Fields to Verify

For Continuity Specialist work, returned status packets must be checked for the following whenever available:

- `production_automation: OFF`
- `forecast_gate: OFF`
- `promotion_allowed: false`
- `stable_engine_modified: false`
- `canonical_workbook_overwrite: false`
- no prediction generation
- no model promotion

## Stop Report Template

When a gate cannot continue, report:

```text
Gate:
Last proven evidence:
What 1C expected next:
What happened:
Where drift occurred:
Can drift be corrected inside the same gate?
Recommended 1C-compatible recovery:
What will not be done:
```

## R7 Breakthrough Rule

The R7 breakthrough proved that merge success required treating merge as its own gate family, not as a continuation of PR verification.

Correct R7 sequence:

```text
PR_STATUS_READY
→ dry-run merge gate
→ MERGE_GATE_PASS
→ actual merge gate
→ MERGED
→ post-merge repo inventory
→ expected paths present on main
```

This R7 pattern is now the canonical merge-roadmap proof case for future Continuity Specialist gates.
