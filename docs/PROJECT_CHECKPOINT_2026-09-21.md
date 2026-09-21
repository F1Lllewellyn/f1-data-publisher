# F1 project checkpoint — 2026-09-21

Status: **Gate 1 review in progress**. This file is the repository handoff for the peak-control dirty-worktree repair. Recheck current `main` and live runs before treating the proposed fix as deployed.

## Baseline and observed outcomes

- Investigation began from `main` `9980606ea69a4debf42d609e7f5d947ac9778205`; `main` was `a7da5554976ca59e42d6d314db2087db15cc85c0` at this checkpoint. The supplied DR-002 baseline `3c02291b9f2113b48975f322d800e995ec4bf1a2` is its direct predecessor, not the latest tip. Confirm branch tip again before merging.
- PRs #117–#119 are merged. [KPI run 35533645342](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/35533645342) had event SHA `4c31409`, checked out `69b64fa` after PR #119, and pushed `17e8a4c` successfully. This validates that queued checkout can resolve a newer tip; it does not prove every writer is conflict-free.
- [Peak run 35533235285](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/35533235285) had event SHA `fb47017` before PR #119 merged at 19:53:11 UTC. It produced local commit `7b04f034c` at 20:00:18 UTC; the push was rejected because `main` had moved to PR #119's `69b64fa`, and the retry refused to rebase with unstaged changes (exit 20). Its log did **not** print the dirty path list. PR #119 caused the push collision, not the creation of those local changes.
- Later peak [runs 35541520848](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/35541520848) and [35547779609](https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/35547779609) succeeded with first-attempt pushes. Both still invoked the old Auto-Repair safe test. These successes do not demonstrate a clean worktree on a rejected push.
- A fresh local reproduction of that exact safe-test invocation modified three tracked paths: `latest/autorepair/session_workbook_recovery/autorepair_status.json`, `autorepair_report.md`, and `autorepair_manifest.json` (all under the same directory). It also created a dated untracked history directory. This is a reproduced mechanism for the failed rebase, not a claimed forensic status listing from the 19:43 run.

## Output ownership and bounded change

| Output | Producer and intended owner | Peak-control handling |
| --- | --- | --- |
| `latest/autorepair/session_workbook_recovery/{autorepair_status.json,autorepair_report.md,autorepair_manifest.json}` and `history/autorepair/session_workbook_recovery/<run_id>/` | `scripts/autorepair/f1_autorepair_orchestrator_v1.py`; recovery workflows stage Auto-Repair latest/history when source-backed recovery permits a commit. | Peak health called `--mode safe_test`, which wrote these tracked latest files even though peak does not own or stage Auto-Repair outputs. Proposed peak preflight uses `--runtime-only` so its diagnostic remains in the uploaded `_runtime/autorepair/` artifact and leaves the owner snapshots untouched. Standalone safe test and `run_now` retain their existing output contract. |
| `latest/session_data_processor/**`, `history/session_data_processor/**`, and three top-level `latest/{latest_manifest,data_readiness,combined_source_manifest}.json` | Session Data Processor Loop owns source observations and manifests. | Peak's live chain can produce session outputs; its 19:43 run reported `no_recent_completed_session_found`, so it did not rewrite the three top-level manifests. Potential output ownership overlap during a new session remains a separate review gate. |
| `latest/workbook_kpi_refresh_applier/**`, `history/workbook_kpi_refresh_applier/**` | Scheduled KPI writer owns its sandbox workbook and KPI reports. | Peak also runs the applier and intentionally stages its source-backed handoff. Shared latest reports can collide; safe-push conflicts must stay explicit. |
| `latest/readiness_dashboards/**`, `latest/chat_context/**` and dated history | Dashboard connector and scheduled dashboard writer produce consumer readiness summaries. | Peak invokes the connector and stages its own refreshed summaries. These are downstream readiness context, not prediction activation. |

The proposed change keeps the safe-push retry and conflict stop. On a rejected push it now records any tracked dirty paths before refusing rebase; it never stages, stashes, resets, discards, or force-pushes those files. Offline tests cover legacy reproduction, runtime-only isolation, invalid live mode, dirty collision refusal with data retained, clean rebase success, and genuine conflict refusal. **Live proof and PR checks remain pending.**

## Protected decisions and open gates

- `Engine_2026-06-07_STABLE`, the canonical workbook, source facts, coefficients, and forecast activation are unchanged. FIA final-grid verification still holds race-grid readiness under [GRID_PROVENANCE_CHECKPOINT_2026-09-16.md](GRID_PROVENANCE_CHECKPOINT_2026-09-16.md). A later API result cannot establish availability at an earlier forecast lock.
- **DR-002 is proposed, not adopted.** One evidence foundation with product-specific contracts, immutable checkpoints, and separately scored predictions is a design candidate. Its exact checkpoint offsets, product deadlines, FIA final-grid timing, historical coverage, and model-sharing validation require a separate reviewable decision before implementation. No 30-minute final pre-race deadline has been activated.
- Pipedream retirement remains conditional on an inventory of current external triggers, webhooks, notifications, secrets, and workflow dependencies. Nothing is removed by this gate.
- Branch API reported `main.protected=false` and the repository rulesets listing was empty at this checkpoint; the detailed classic branch-protection endpoint returned 403 to this integration. Do not treat that permission error as proof of every protection setting.

## Next gate

Review this narrowly scoped PR and its offline collision tests; update the base from fresh `main`, merge only if checks and diff support it, then examine a **post-merge peak-control live run** for the new runtime-only invocation, push outcome, and any tracked dirty diagnostics. Update this checkpoint with the actual run ID/SHA. If another path appears, stop and trace its producer before changing any commit allowlist. After Gate 1, audit remaining GitHub writers and Pipedream dependencies as separate work; assess DR-002 separately with current FIA primary-source regulations.
