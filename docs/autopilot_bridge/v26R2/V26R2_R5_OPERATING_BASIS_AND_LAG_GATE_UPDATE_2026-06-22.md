# v26R2-R5 Operating Basis + Lag-Aware Terminal Evidence Gate

Status: PR-only governance documentation. This checkpoint does not activate production automation, does not open a forecast gate, does not modify the stable engine, does not overwrite the canonical workbook, does not promote a model, and does not generate predictions.

## Operating basis after PR #112

The current Continuity Specialist Engine operating basis is:

- v26R2-R3 as the landed core transport-safe compiler/latch package.
- v26R2-R4 as the landed dormant file-hash verification lane reference and local sandbox verifier helper.
- PR #111 remains landed / merged / post-merge path-validated, with local sandbox hash verification passed against the frozen R3 payload.
- PR #112 remains landed / merged / post-merge path-validated.

## Mandatory lag-aware terminal evidence gate

Gmail, Pipedream, and GitHub Actions are asynchronous. A missing Gmail search result is not terminal evidence.

After any Gmail bridge send, the runner must not report a negative state such as `no status`, `not found`, `no PR`, `no returned status`, `not proven`, or `failure` merely because a Gmail search did not find the expected return message.

A bridge step may be closed only by terminal evidence:

- `DISPATCH_ACCEPTED`
- `PR_STATUS_READY`
- `MERGED`
- `MERGE_BLOCKED`
- `REPO_INVENTORY_READY`
- `PIPEDREAM_ERROR`
- GitHub Actions terminal failure/success evidence
- Explicit user-provided GitHub UI evidence such as a screenshot, reconciled with bridge status

If GitHub Actions shows pending or in-progress receiver/advisory/catchall activity, the only valid state is:

`ACTIVE / LAG WINDOW OPEN`

If a user screenshot shows a PR open/ready while Gmail search has not returned bridge status, the valid state is:

`SCREENSHOT-PROVEN / BRIDGE-STATUS-PENDING`

## Minimum conduct rule

The runner must wait for meaningful lag before status claims. Early sweeps may be used internally only to find positive terminal evidence. They must not be reported as negative evidence.

## Snag-handling rule

When a snag occurs:

1. Check the manual/control docs first.
2. Use available read-only bridge diagnostics before asking the user for manual logs.
3. Do not improvise a mutation path.
4. Do not resend unless an exact-subject duplicate check is clean and the prior send was not accepted by Gmail.
5. Stop only on critical rule violation, terminal failure, or missing authorization for a mutation gate.

## State-label discipline

Use exact state labels:

- `DISPATCH_ACCEPTED` does not mean GitHub receiver completed.
- GitHub receiver started does not mean PR created.
- PR open/ready does not mean merge gate passed.
- `MERGED` does not mean post-merge path validation is complete.
- Path validation does not mean content-hash validation unless per-file hashes are returned and match.

## R4 hash-verification status

R4 landed a dormant local verifier and a file-hash lane specification. It does not prove that deployed bridge runtime file hashing is active.

Allowed wording:

`PR #111 local sandbox hash verification passed against frozen R3 payload.`

Not allowed wording until a bridge-runtime hash lane returns per-file matches:

`PR #111 content-hash bridge validation complete.`
