# F1 Peak-Elite System Layer — 2026-06-13

## Purpose

This layer turns the repository into a safer, more automated control room without asking the user to run Python locally.

The target chain is:

```text
workflow/watchers -> source readiness gate -> session data processor -> source validation -> workbook/KPI sandbox refresh -> Forecast Bundle / readiness ledger -> Race/Fantasy readiness briefs -> material-change commit/notification
```

## What this patch adds

- `F1 Peak Elite Control Room - One Click v1` workflow
- workflow syntax repair for broken Bash commit blocks
- deeper workflow static validation using `bash -n`
- peak-elite health reporting
- cleanup inventory reporting without deletion
- latest ChatGPT-facing status briefs in `latest/chat_context/`

## Governance

- Does not modify `Engine_2026-06-07_STABLE`
- Does not overwrite canonical workbook files
- Does not promote experimental/challenger logic
- Does not force push
- Does not delete files
- Uses source-backed readiness state before downstream consumption

## 2026 F1 rule

2026 F1 has no DRS. Downstream interpretation should use energy deployment, battery state, harvest/regen efficiency, cooling pressure, dirty-air cost, traffic cost, and attack/defend energy availability.

## Operating modes

- `syntax_repair_only`: repair workflow Bash block issues and validate them.
- `health_only`: validate workflows, scripts, latest readiness, workbook/KPI state, and governance guardrails.
- `full_safe_chain`: repair syntax and run safe tests only.
- `full_run_chain`: run the live source-backed session -> workbook -> dashboard chain.
- `scheduled_monitor`: scheduled guardrail run that avoids overcommitting unless material state changes.

## Cleanup posture

Cleanup is report-only by default. The repository has many dated installers, manifests, archived patches, and historical reports. This layer inventories cleanup candidates but does not delete or move them until a separate explicit cleanup approval.
