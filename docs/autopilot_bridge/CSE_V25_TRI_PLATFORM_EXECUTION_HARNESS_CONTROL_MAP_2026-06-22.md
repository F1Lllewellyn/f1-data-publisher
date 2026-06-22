# CSE v25 Tri-Platform Execution Harness Control Map

Date: 2026-06-22  
Artifact class: documentation/governance only  
Target path: `docs/autopilot_bridge/CSE_V25_TRI_PLATFORM_EXECUTION_HARNESS_CONTROL_MAP_2026-06-22.md`  
Status: PR-only control map; not activation; not runtime execution.

## Purpose

This document records the repository-side control map for Continuity Specialist Engine v25. It exists so future runner chats can re-enter the F1 Prediction Engine continuity workflow with a concise, auditable control artifact instead of relying on chat memory.

## Active operating basis

- Active workstream: Engine Optimization / Continuity Specialist Engine.
- v25 package: `Continuity_Specialist_Engine_v25_Tri_Platform_Execution_Harness_2026-06-22.zip`.
- v25 package SHA-256: `a47f62fa02e9db1518b1084dc92fcd932e87ae8c92ad2af3497fd7e1d32754dd`.
- PR #107 status carried forward: `LANDED / MERGED / POST-MERGE VALIDATED`.
- PR #107 chain-of-custody wording: `GitHub-validated merged / bridge-merge execution not proven`.

## Tri-platform bridge model

The controlled execution path is:

```text
Gmail command transport
-> Pipedream command parser / dispatcher
-> GitHub Actions receiver
-> PR/status/merge evidence
```

A successful upstream state never implies a downstream state. `DISPATCH_ACCEPTED` proves transport acceptance only. It does not prove GitHub receiver success, PR creation, merge eligibility, merge, or post-merge validation.

## Mechanical governance rule

Governance is not satisfied by reading instructions or promising compliance. A runner is compliant only when the next possible action is mechanically permitted by all of the following:

1. active gate,
2. tool firewall,
3. command compiler,
4. SEND_LOCK ledger,
5. evidence-state firewall.

If any layer is absent, contradictory, or incomplete, the runner must HOLD or HARD STOP before live tool use.

## Evidence-state firewall

The following substitutions are forbidden:

- `REPO_INVENTORY_READY` is not `PR_STATUS_READY`.
- `PR_STATUS_READY` is not `MERGE_GATE_PASS`.
- `MERGE_GATE_PASS` is not `MERGED`.
- `MERGE_BLOCKED` is not `MERGED`.
- GitHub UI merged evidence is not bridge `MERGED` evidence.
- `MERGED` is not `POST_MERGE_VALIDATED`.
- `POST_MERGE_VALIDATED` is not `FINAL_CHAIN_OF_CUSTODY`.

## Tool firewall

- Read-only gates expose only read tools.
- Send tools are unavailable until SEND_LOCK passes.
- After one successful send, send tools are disabled.
- `Gmail.read_attachment` is unavailable unless the active gate explicitly authorizes attachment reading and attachment metadata exists.
- Mutation-capable tools require explicit gate authorization plus validator/SEND_LOCK pass.
- A failed tool call creates a no-repeat latch for the same tool and same argument pattern unless a named fallback was pre-authorized.

## SEND_LOCK minimum fields

No outbound command can be sent unless a SEND_LOCK object exists before send with:

- `gate_id`,
- `command_type`,
- `target`,
- `intended_recipient`,
- `intended_subject`,
- `intended_body_sha256`,
- `dispatch_count_for_gate: 0`,
- `pre_checks_complete: true`,
- `send_authorized: true`,
- `created_before_send: true`.

After successful send:

```text
dispatch_count_for_gate = 1
send_tools_allowed = false
phase = READ_ONLY_RETURNED_STATUS_WAIT
```

## GitHub Actions receiver states

After any `assistant_patch` / repository_dispatch command, status must be tracked by receiver stage:

- `PIPEDREAM_ENVELOPE_ACCEPTED` / `FAIL`
- `PIPEDREAM_COMMAND_PARSED` / `FAIL`
- `PIPEDREAM_DISPATCH_ACCEPTED` / `FAIL`
- `GITHUB_RECEIVER_STARTED` / `UNKNOWN`
- `VALIDATE_COMMAND_PASS` / `FAIL` / `UNKNOWN`
- `APPLY_COMMAND_FILES_PASS` / `FAIL` / `UNKNOWN`
- `RUN_REQUESTED_TESTS_PASS` / `FAIL` / `UNKNOWN`
- `WRITE_STATUS_LEDGER_PASS` / `FAIL` / `UNKNOWN`
- `PR_CREATED_OR_UPDATED` / `PR_NOT_CREATED` / `UNKNOWN`

## Receiver validator parity rule

The command compiler must match the live GitHub Actions receiver validator before any `assistant_patch` send. For the active receiver, `scripts/autopilot/validate_command.mjs` requires:

- `schema_name`,
- `schema_version`,
- `command_type`,
- `project`,
- `safety_mode`,
- `target_branch`,
- `base_branch`,
- `title`,
- `summary`,
- `files`.

The active receiver also requires `project` to equal `F1_Prediction_Engine`, `command_type` to equal `assistant_patch`, and `safety_mode` to be `pr_only` or `outputs_only`. A command package missing any live-validator required field must HARD STOP before Gmail send.

This rule was added after the Module 2 live run exposed a command-compiler gap: Pipedream accepted the first transport, but the GitHub receiver failed validation because the payload omitted `project` and lacked validator parity. Future runners must check receiver validator parity before treating a command package as send-ready.

## Receiver-log diagnosis rule

If Pipedream returns `DISPATCH_ACCEPTED` but no PR appears, do not immediately resend and do not declare the bridge complete. First inspect receiver-side evidence: GitHub Actions run logs, receiver job step summaries, and validator output. The failed receiver stage, not the Gmail send, is the correct diagnostic target.

## PR #107 closeout rule

PR #107 is closed for continuity purposes. Do not reopen, resend, re-merge, rerun merge, or try to prove bridge-merge execution for PR #107 unless new explicit evidence appears. Preserve the chain-of-custody wording: `GitHub-validated merged / bridge-merge execution not proven`.

## Safety boundaries

This artifact does not authorize:

- production automation activation,
- forecast gate activation,
- runtime/status regeneration,
- processor execution,
- observer runway execution,
- stable-engine modification,
- canonical workbook write or overwrite,
- prediction generation,
- model promotion,
- model-logic change,
- engine-code change,
- merge execution.

## Module 2 completion definition

For this lane, Module 2 is complete when this documentation/governance artifact is created or updated through the approved tri-platform bridge path and verified on GitHub as a PR-only docs/autopilot_bridge change.
