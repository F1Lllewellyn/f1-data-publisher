# DR-002 pre-2B-7H3 — Truthful lock-shadow workflow identity composition

Work order: [F1-WO-DR002-PRE2B7H3-001 / Issue #179](https://github.com/F1Lllewellyn/f1-data-publisher/issues/179)  
Recorded: 2026-10-06  
Result: focused workflow-identity repair completed for review; no workflow run was dispatched.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Defect and repair

The accepted lock-shadow wrapper previously required every caller to identify `.github/workflows/dr002-forecast-lock-shadow-pilot.yml`. That was truthful for its historical H2 direct run, but it prevented safe composition: a different workflow could call the wrapper only by falsely naming the direct lock workflow.

The wrapper now validates the caller-supplied GitHub workflow reference in the form:

```text
<repository>/.github/workflows/<workflow-file>@<git-ref>
```

It requires:

- the workflow-reference repository to equal the explicit repository;
- the workflow-reference ref to equal the explicit Git ref;
- the repository-local path to be normalized and directly under `.github/workflows/`;
- a non-empty normalized `.yml` or `.yaml` filename; and
- the existing `refs/heads/main` execution restriction.

Repository mismatch, ref mismatch, malformed references, traversal, paths outside `.github/workflows/`, nested paths, empty filenames, invalid extensions, and non-main execution fail closed.

After validation, the wrapper derives `workflow_path` from the actual supplied reference. It preserves the validated `workflow_ref` exactly and preserves the caller-supplied GitHub workflow display name.

Direct execution continues to record `.github/workflows/dr002-forecast-lock-shadow-pilot.yml`. A future composed execution can truthfully record `.github/workflows/dr002-outcome-boundary-shadow-pilot.yml` instead.

## Preserved mechanics and evidence

No direct workflow file changed. Forecast payload bytes, producer and lock receipt construction, Gate 2B-4 lock construction, timing, storage reference, evidence hashes, producer behavior, trust flags, model logic, and DR-002 state are unchanged.

Focused tests confirm that direct and composed calls with identical run inputs produce byte-identical forecast payload, producer receipt, lock receipt, and report evidence; only the caller workflow identity changes. Existing run/head/attempt validation and false trust ceilings remain intact. Named direct-workflow, producer, production-locker, and Gate 2B-4 dependency blobs remain unchanged.

Historical H2 evidence is neither rerun nor rewritten. Its pinned historical run head and old wrapper blob remain the evidence for that completed run. A future GitHub/Sigstore attestation remains the cryptographic proof of the actual signer workflow, run, and head.

## Checkpoint

```text
lock_shadow_workflow_identity_composable: true
direct_lock_workflow_identity_preserved: true
composed_workflow_identity_truthful: true
historical_h2_evidence_rewritten: false
lock_mechanics_modified: false
trust_ceiling_modified: false
live_workflow_run_executed: false
dr002_activated: false
promotion_allowed: false
```
