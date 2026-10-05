# DR-002 pre-2B-7H1 GitHub-attested forecast-lock shadow

Date: 2026-10-05  
Work order: `F1-WO-DR002-PRE2B7H1-001`  
Authorization: Issue #171

## Installed capability

The manual-only `dr002-forecast-lock-shadow-pilot.yml` workflow can run the accepted synthetic frozen-producer shadow once, pass the same GitHub run identity and checkout head to the forecast-lock shadow wrapper once, and attest the resulting `lock_execution_manifest.json` with GitHub's first-party attestation action.

The lock wrapper verifies the complete producer-shadow evidence set before use. It checks the accepted producer implementation's Git blob identity, its copied code bytes, every declared evidence hash, the fixed synthetic source bytes, and the producer's scope and output consistency. It then copies `forecast_rows.csv` without transformation and calls the unchanged Gate 2B-4 `build_forecast_lock` constructor over those exact bytes.

The successful runtime package contains:

- `lock_execution_manifest.json`
- `forecast_payload.csv`
- `producer_execution_receipt.json`
- `forecast_lock_receipt.json`
- `lock_report.md`
- `github_attestation.bundle.json` after the attestation action succeeds
- `github_attestation_metadata.json` after the bundle and subject consistency checks succeed

All output remains under `_runtime/dr002_pre2b7h_forecast_lock_shadow/gha-<run_id>-<attempt>/`. The artifact upload contains runtime shadow evidence only. The workflow has no schedule or repository-write permission and does not dispatch a production workflow.

## Attestation boundary

The attestation subject is the exact successful `lock_execution_manifest.json`. The preservation step recomputes the subject SHA-256, checks that the action bundle names that digest as its only subject, retains the action-produced bundle bytes unchanged, and records factual action and workflow metadata.

That local subject consistency check is not independent cryptographic verification. The attestation binds the lock execution manifest bytes; it does not separately attest the payload, producer receipt, lock receipt, storage object, or internal timestamps. Those files are related to the subject by hashes recorded inside an attested manifest, not by separate external bindings.

## Synthetic receipt boundary

The wrapper constructs a structurally valid `producer_execution` receipt solely so the unchanged Gate 2B-4 lock constructor can exercise its normal parent and payload checks. Its source-receipt parent list is empty, its engine fields are null, and no `verified_receipt_bindings` input exists. The forecast manifest is explicitly `manual_validation` and `contract_approved: false`; its source references and observation times are synthetic, unbound runtime statements.

Consequently, the produced receipt pair is useful mechanical evidence that:

- the lock's sole parent is the generated producer receipt;
- the persisted payload hash, producer payload hash, and lock payload hashes agree; and
- the accepted Gate 2B-4 constructor rejected no local structural or temporal condition.

It is not evidence of a complete Gate 2B-1 receipt graph, authenticated capture times, an authenticated lock clock, stable-engine execution, production publication, or durable storage.

## Validation performed

Only focused offline validation is authorized for this installation. The test suite covers the manual/main-only workflow, minimum permissions, exact invocation count and ordering, accepted attestation pin and subject, immutable bundle preservation, exact payload bytes and hashes, accepted producer fingerprint, actual `build_forecast_lock` use, receipt parentage, false trust claims, absence of production dispatch/write paths, fail-closed tamper handling, and unchanged accepted producer and production-locker Git blobs.

No workflow was dispatched and no live attestation or lock run was performed as part of this work order.

## Checkpoint

```text
lock_shadow_capability_installed: true
live_lock_run_executed: false
exact_forecast_payload_bound: true
gate2b4_lock_constructor_used: true
producer_receipt_externally_bound: false
lock_receipt_externally_bound: false
lock_clock_authenticated: false
durable_storage_proven: false
full_gate2b1_chain_verified: false
production_forecast_locked: false
dr002_activated: false
promotion_allowed: false
```
