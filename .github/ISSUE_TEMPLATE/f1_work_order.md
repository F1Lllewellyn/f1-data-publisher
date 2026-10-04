---
name: F1 authorized work order
about: One bounded Adviser-authorized implementation order
title: "[F1-WO][AUTHORIZED] "
---

# F1 Authorized Work Order

work_order_id: <!-- F1-WO-<WORKSTREAM>-<GATE>-<NNN>, e.g. F1-WO-DR002-2B5-001 -->
contract_version: F1_AGENT_HANDOFF_V1
status: AUTHORIZED

active_workstream:
gate_or_checkpoint:

observed_main_sha:

accepted_predecessor: <!-- Accepted PR/checkpoint, exact reviewed SHA and evidence -->
previous_work_order_id:

recommended_coder_setting: <!-- Default Sol Medium; escalate only per handoff contract -->
model_reason: <!-- One line: why this is the least expensive setting that preserves quality -->

## Objective

## Authorized scope

## Allowed paths / areas

## Relevant dependency fingerprints

| path | blob_sha |
| --- | --- |
| | |

## Required tests

## Required evidence

## Success conditions

## HOLD conditions

## Prohibited actions

## Expected work result

## Notes / explicit exceptions

<!--
Read docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md.
Publish AUTHORIZED only with actual user/Adviser authority under that contract.
Provide enough task-specific detail to execute without reconstructing chat history.
Reference permanent governance; do not duplicate it. Task-specific restrictions belong here.
Follow the handoff contract's work-credit economy: default Sol Medium, escalate only when justified, and keep bounded work orders concise (ordinary soft budget ~2,000 words).
Relevant path/blob_sha fingerprints are mandatory for implementation work.
observed_main_sha is evidence, not a global equality lock.
Coder must fetch fresh main; changed/missing/ambiguous relevant dependencies => HOLD.
Any other change affecting interpretation => HOLD; never silently broaden dependencies or scope.
This order authorizes nothing outside its explicit boundaries.
Exactly one open issue may have the prefix [F1-WO][AUTHORIZED].
-->
