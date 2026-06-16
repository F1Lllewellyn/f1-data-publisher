# V30W Sandbox-Live Source Pull Harness

This patch adds a controlled source pull harness for the Session Data Processor Loop.

## Scope

- Builds OpenF1 request manifests after a session-end gate.
- Supports `dry_run`, `fixture`, and explicit `sandbox_live` modes.
- Performs live source pulls only when both conditions are true:
  - mode is `sandbox_live`
  - `--allow-live true` is supplied
- Emits a source summary that can be consumed by later processor-loop readiness steps.

## Governance

- Production automation remains OFF.
- Forecast gate remains OFF.
- Model promotion remains false.
- Stable engine is not touched.
- Canonical workbook is not touched.
- Workbook writes remain disabled.
- Race Predictions refresh remains disabled.
- Fantasy refresh remains disabled.
- Notifications remain disabled.

## Intended Follow-Up

After review, v30X should add an end-to-end replay and fixture validation runner for the watcher, source pull, processor-loop, ledger, and readiness chain.
