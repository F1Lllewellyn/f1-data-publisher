# v26R2-R6 No Automations for Bridge Gates

Status: PR-only governance documentation. This checkpoint does not activate production automation, open a forecast gate, change the stable engine, overwrite the canonical workbook, promote a model, or generate predictions.

## Rule

Scheduled automations must not be used for Gmail/Pipedream/GitHub bridge gates unless the user explicitly asks for that behavior.

Bridge gates must stay in the active chat because the active chat holds the current send ledger, current gate state, latest screenshots, returned bridge packets, and mutation authorization boundary.

## Why this rule exists

A scheduled follow-up opened in a separate chat during the v26R2-R5 flow. That broke the expected continuity model and created unnecessary risk. The user explicitly rejected that route and authorized manual newest-email checks instead.

## Correct follow-up pattern

After a Gmail bridge send is accepted:

1. Record the Gmail ID and subject.
2. Close send tools for that gate.
3. Wait for meaningful bridge/GitHub/Gmail lag.
4. Check newest emails first.
5. Read terminal packets before making state claims.
6. Never treat negative Gmail search results as terminal evidence.
7. If a snag occurs, use the manual and read-only bridge diagnostics first.
8. Do not use scheduled automations for bridge follow-up.

## Valid terminal evidence

- `DISPATCH_ACCEPTED`
- `PR_STATUS_READY`
- `MERGED`
- `MERGE_BLOCKED`
- `REPO_INVENTORY_READY`
- `PIPEDREAM_ERROR`
- explicit GitHub Actions terminal failure/success
- user-provided GitHub UI evidence reconciled with bridge packets

## Required state wording

Allowed:

`SENT_ONCE / HARD LAG WINDOW OPEN`

`SCREENSHOT-PROVEN / BRIDGE-STATUS-PENDING`

`MERGED / MAIN BRANCH COMMIT VALIDATED / POST-MERGE PATH-VALIDATED`

Not allowed:

`no status yet` from a premature search

`no PR` from a Gmail search miss

`content hash validated` from path validation alone

## Relationship to R5

R5 formalized the lag-aware terminal evidence gate. R6 adds the narrower operational rule that scheduled automations are not an acceptable bridge-gate follow-up mechanism unless the user explicitly authorizes them.
