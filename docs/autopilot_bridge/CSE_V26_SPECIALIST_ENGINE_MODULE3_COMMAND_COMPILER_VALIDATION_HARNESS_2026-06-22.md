# CSE v26 Specialist Engine — Module 3 Command Compiler Validation Harness

Date: 2026-06-22
Artifact class: documentation/governance only
Target path: `docs/autopilot_bridge/CSE_V26_SPECIALIST_ENGINE_MODULE3_COMMAND_COMPILER_VALIDATION_HARNESS_2026-06-22.md`
Status: Module 3 control artifact; not activation; not runtime execution.

## Purpose

This artifact converts the Module 2 live A-to-J lessons into mechanical rules for the next runner. It is PR-only governance for the Continuity Specialist Engine. It does not authorize production activation, forecast gate activation, runtime/status regeneration, processor execution, stable-engine modification, workbook change, model logic change, prediction generation, or model promotion.

## Module 3 completion contract

Module 3 is complete only at:

```text
LANDED / MERGED / POST-MERGE VALIDATED
```

PR-created is not complete. PR-open-and-validated is not complete. Dispatch-accepted is not complete.

## Active lane

The active lane is:

```text
Gmail command transport
-> Pipedream command parser / dispatcher
-> GitHub Actions receiver
-> PR / merge / post-merge returned-status evidence
```

Direct GitHub mutation is not part of this lane unless a future gate explicitly switches lanes.

## Evidence ladder

The runner may only advance labels when the matching proof exists:

```text
COMMAND_DRAFTED
-> COMMAND_VALIDATED_LOCALLY
-> SEND_LOCK_READY
-> GMAIL_SENT_ONCE
-> PIPEDREAM_DISPATCH_ACCEPTED
-> GITHUB_RECEIVER_STARTED
-> VALIDATE_COMMAND_PASS
-> APPLY_COMMAND_FILES_PASS
-> RUN_REQUESTED_TESTS_PASS
-> WRITE_STATUS_LEDGER_PASS
-> PR_CREATED_OR_UPDATED
-> PR_OPEN_AND_SCOPE_VERIFIED
-> MERGE_GATE_PASS
-> MERGED
-> POST_MERGE_VALIDATED
-> FINAL_CHAIN_OF_CUSTODY
```

Forbidden substitutions: `DISPATCH_ACCEPTED` is not PR success; PR success is not merge; merge is not post-merge validation.

## Completion contract registry

Every future module must declare one contract before work begins:

- `READ_ONLY_MAP_COMPLETE`
- `PR_CREATED_ONLY`
- `PR_OPEN_AND_SCOPE_VERIFIED`
- `MERGED`
- `POST_MERGE_VALIDATED`
- `FINAL_CHAIN_OF_CUSTODY`

The runner may not say "done", "complete", or "closed" until the declared contract is reached.

## Live receiver-validator parity

Before any `assistant_patch` send, the command compiler must match the live GitHub Actions receiver validator. The active receiver requires:

- `schema_name`
- `schema_version`
- `command_type`
- `project`
- `safety_mode`
- `target_branch`
- `base_branch`
- `title`
- `summary`
- `files`

Required values:

```text
project = F1_Prediction_Engine
command_type = assistant_patch
safety_mode = pr_only or outputs_only
```

A command package missing any live-validator required field must HARD STOP before Gmail send.

## SEND_LOCK

No outbound command may be sent unless SEND_LOCK exists before send with:

- `gate_id`
- `module_id`
- `command_type`
- `target`
- `intended_recipient`
- `intended_subject`
- `intended_body_sha256`
- `dispatch_count_for_gate: 0`
- `pre_checks_complete: true`
- `send_authorized: true`
- `created_before_send: true`

After successful send: `dispatch_count_for_gate = 1`, send tools disabled, phase becomes `READ_ONLY_RETURNED_STATUS_WAIT`.

## No-repeat failure latch

Every failed tool call creates a latch containing tool name, argument-pattern hash, failure type, and `allowed_retry: false` unless a named fallback was pre-authorized. Do not repeat failed body-file sends, blocked merge dry-run sends, or connector 404 read loops.

## Receiver-log diagnosis

If Pipedream returns `DISPATCH_ACCEPTED` but no PR appears, diagnose the GitHub receiver first: Actions run, receiver job steps, validator output, apply output, test output, status ledger, and PR creation/update output. Do not blindly resend.

## Merge command compiler

A merge command is not send-ready unless it includes `assistant_merge_pr`, `approved_merge_gate`, `pull_number`, expected base/head controls, allowed author logins, allowed path prefixes, forbidden path parts, promotion/activation OFF, production/forecast OFF, stable/workbook/model/prediction flags false, merge method, and `dry_run: false` only when the active contract requires merge.

If PR author is `F1Lllewellyn`, `allowed_author_logins` must include `F1Lllewellyn`.

## Post-merge verification

After `MERGED`, the runner must verify PR state closed, merged true, merge timestamp, merge commit SHA, changed file count/list, final head SHA, safety flags still off, and workflow status. If direct GitHub reads fail, approved bridge returned-status evidence can satisfy this when it contains those fields.

## Safety boundaries

This artifact does not authorize any change outside `docs/autopilot_bridge/`, nor any stable-engine, workbook, runtime, forecast, processor, model, prediction, production, or promotion action.

## Module 3 final closeout rule

A successful Module 3 closeout must report:

```text
CSE-v26 Module 3 = LANDED / MERGED / POST-MERGE VALIDATED
```

with PR number, merge SHA, final changed file list, and confirmation that no protected system was touched.
