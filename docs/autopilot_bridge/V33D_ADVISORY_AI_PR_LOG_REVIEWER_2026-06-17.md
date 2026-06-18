# v33D Advisory AI PR and Failed-Log Reviewer

v33D adds an advisory AI review layer for pull-request diffs and failed GitHub Actions logs.

## Scope

- Adds `.github/workflows/f1_ai_pr_log_advisory_reviewer.yml`.
- Adds `scripts/autopilot/f1_ai_pr_log_advisory_reviewer_v33d.py`.
- Runs on PR open/update and on failed F1 bridge receiver workflows.
- Posts or updates an advisory PR comment when a PR context is available.
- Writes the same review to the GitHub step summary.

## Governance

- Advisory by default.
- No GitHub merge endpoint is called.
- No repository contents are written by the reviewer.
- No production automation is activated.
- No live F1 data is fetched.
- No workbook, canonical workbook, Forecast Bundle Ledger, Race/Fantasy readiness, notification, or model-promotion action is performed.
- `Engine_2026-06-07_STABLE` remains protected.

## Verdicts

- `VERDICT: PASS`
- `VERDICT: REVIEW_REQUIRED`
- `VERDICT: BLOCK`

`REVIEW_REQUIRED` is forced for workflow/config/governance changes even if the AI response says PASS.

## Required setup

The workflow needs repository secret `OPENAI_API_KEY` to perform AI review. If the secret is missing, the reviewer exits successfully with `REVIEW_REQUIRED` so PR flow is not broken during setup.

Optional repository variable:

- `OPENAI_MODEL`, default `gpt-4o-mini`.

## Recommended branch-protection posture

Do not allow this reviewer to merge code. If branch protection is later updated, use this job only as an additional advisory/status signal. The existing deterministic Pipedream merge gate remains the merge authority.
