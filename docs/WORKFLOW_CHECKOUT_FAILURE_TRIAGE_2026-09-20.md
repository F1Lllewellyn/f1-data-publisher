# Scheduled writer checkout failure triage — 2026-09-20

## Scope and evidence

This checkpoint was prepared on `audit/fresh-checkout-serialized-writers-20260920`. Its three-workflow pilot is reviewed through PR #117; deployment and live-run outcomes must be verified from GitHub, not inferred from this note.

Three recent failing runs completed their source processing and diagnostics upload, then failed when `scripts/ops/safe_git_push_rebase_retry.sh` refused a rebase conflict (exit 20) on `latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json` and `workbook_kpi_refresh_report.md`:

- [KPI refresh run 35526829717](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/35526829717)
- [Scheduled recovery run 35471361145](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/35471361145)
- [Integrated loop run 35444735886](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/35444735886)

For run 35526829717, the workflow was created at 17:44:38 UTC on commit `5df5e2d` and its job began at 17:54:58 UTC, just after the serialized peak control-room job completed at 17:54:56 UTC and pushed a later bot commit `4ca4371`. These jobs already share `f1-main-write-serialization` and `cancel-in-progress: false`. Serialization prevented simultaneous execution, but the event SHA selected by checkout was fixed before the wait. The safe-push conflict guard correctly stopped an ambiguous rebase; do not replace it with a force push or silently choose one version of the generated reports.

## Bounded pilot

In the three affected scheduled writer workflows, set `actions/checkout@v6` `with.ref: ${{ github.ref_name }}` alongside the existing `fetch-depth: 0`. This makes checkout resolve the current tip of the triggering branch when the queued job actually starts, while preserving manual-dispatch branch selection. No trigger, concurrency group, processor, commit allowlist, output contract, or safe-push code changes in this pilot.

The pilot does not guarantee that all conflicts vanish. A different writer can push after checkout, GitHub concurrency may replace an older pending run, and other workflows can still use stale event SHAs. Generated output conflicts must remain explicit and reviewed; no automatic conflict resolution is authorized here.

## Review and verification before promotion

1. Confirm the branch diff is exactly one `ref` line in each of the three workflow files. Validate workflow YAML expression syntax, preserving `on`, permissions, and concurrency.
2. Confirm production-workflow approval and the merged main SHA from PR #117. The PR advisory AI reviewer may consume API credits; avoid redundant PR updates.
3. After approved deployment, compare queued-run event SHA with checkout `HEAD` and branch tip in a representative scheduled run. Watch several later writer runs for exit 20, conflicts, and pending-run replacement; retain failure diagnostics. Do not claim notification relief until live runs substantiate it.
4. If failures persist, identify exact writer/paths and checkout age first. Keep the existing safe-push guard; use a separate reviewed change for writer ownership, transaction isolation, or concurrency coverage.

The competing Madrid/FIA final-grid readiness gate is staged separately on `audit/f1-readiness-fia-integrated-20260920`. Neither pilot promotes a forecast, modifies the stable engine or canonical workbook, nor permits writing an unverified final grid.

## Follow-up scope: dashboard and peak-control writers

[Dashboard run 34886952094](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/34886952094) completed processing, but its safe-push rebase conflicted on readiness and latest chat-context outputs after the branch moved. It uses the same serialized main-writer group and event-SHA checkout as the three pilot writers. PR #119 proposes the identical current-branch checkout line for this dashboard and the peak-control scheduled writer, whose work can also outlast changes to main. Preserve their triggers, output allowlists, and safe-push guard.

This checkout update addresses only *staleness before job start*. [Peak run 35341318551](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/35341318551) also reported `cannot rebase: You have unstaged changes` after a push rejection. That is a separate worktree/commit-scope defect. Capture the exact dirty path list and fix it in a reviewed follow-up; do not stash or discard those artifacts without verifying their purpose. Additional main writers and independent concurrency groups remain to be audited. Live results and merged state must be verified from GitHub.
