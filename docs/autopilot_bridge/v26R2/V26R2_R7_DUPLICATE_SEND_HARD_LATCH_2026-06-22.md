# v26R2-R7 Duplicate-Send Hard Latch

Status: PR-only governance documentation. This checkpoint does not activate production automation, does not open a forecast gate, does not change the stable engine, does not overwrite the canonical workbook, does not promote a model, and does not generate predictions.

## Summary

R7 formalizes a hard duplicate-send latch after R6 exposed that procedural “send tools are closed” language was not enough. The rule must be explicit, mechanical, and conservative.

## Purpose

Prevent repeated Gmail bridge command sends for the same gate, subject family, PR, branch, or command intent after an accepted Gmail message ID has been returned.

## Rule

After any Gmail bridge command is accepted and returns a Gmail message ID, the active gate enters `SEND_LATCH_CLOSED`.

While `SEND_LATCH_CLOSED` is active, the runner must not invoke any send-capable tool again for the same gate, same subject family, same PR, same branch, or same command intent.

This applies to:

- `assistant_patch`
- `assistant_pr_status`
- `assistant_repo_inventory`
- `assistant_merge_pr`
- any future bridge command with side effects or downstream bridge impact

## Mutation-capable commands

For mutation-capable commands, including `assistant_merge_pr`, duplicate send is a critical incident even if GitHub ultimately produces only one commit.

A mutation-capable duplicate send requires:

1. Stop all send tools.
2. Use read-only newest-email checks only.
3. Read terminal bridge/GitHub evidence.
4. Record the incident in closeout.
5. Do not issue another mutation command in the same gate.
6. Do not proceed to a new mutation gate until the current gate has terminal evidence and incident notes are written.

## Read-only commands

Duplicate read-only sends are lower severity than mutation-capable duplicates, but they are still workflow discipline incidents. They must be recorded and contained.

## Valid duplicate-send recovery

If a duplicate read-only command was sent:

- Use the first valid returned packet.
- Ignore duplicate returned packets if they match.
- If packets conflict, stop and treat as a snag requiring manual review.

If a duplicate mutation-capable command was sent:

- Stop send tools immediately.
- Treat user GitHub UI screenshots as authoritative live state.
- Use newest-email read-only checks only.
- Confirm whether GitHub produced one commit or multiple commits.
- Continue only after terminal evidence proves repository state.

## Pre-send checklist

Before any send-capable tool call, the runner must have all of the following in the active response state:

- exact subject
- command type
- target PR or branch
- expected head SHA when applicable
- duplicate search result
- explicit statement: `NEXT SEND IS THE ONLY SEND FOR THIS GATE`

After the send returns a Gmail ID, the runner must immediately record:

- Gmail ID
- subject
- command type
- timestamp if available
- `SEND_LATCH_CLOSED`

## Relationship to R5 and R6

- R5 governs lag-aware terminal evidence.
- R6 forbids scheduled automations for bridge-gate follow-up unless explicitly requested.
- R7 governs duplicate-send prevention after a send is accepted.

These are separate gates and must all remain active.

## Non-overclaim clause

R7 is a governance/documentation checkpoint. It does not prove deployed bridge-runtime content hashing, does not activate production automation, and does not modify prediction logic.
