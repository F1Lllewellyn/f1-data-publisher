# Gate 2B-3B2 live shadow checkpoint

This records the user's independently adviser-verified live handoff, not a new artifact download or live execution in Gate 2B-4. Execution-chain mechanics succeeded. Classification: OUTCOME_AWARE_EVALUATION_ONLY. Status: SHADOW_EXECUTION_ONLY_NOT_A_PREDICTION. Source remains UNBOUND.

## Runtime facts

- Run: 37152568516; number 1; attempt 1; event workflow_dispatch; completed successfully. Exactly one run/attempt used.
- Exact checkout/head: 8d164fce63aea97aee7c2db71b6eb23d8f5e2055.
- Permissions: Actions read / Contents read.
- Prior capture artifact: 11277594100, dr002-weather-capture-37133694090-1.
- Expected/downloaded prior digest: df9ced90ba0df602d4e896c48292964ff812880f9a38dd5b4f0867da88ff6b6d.
- New artifact: 11284482487, dr002-shadow-execution-37152568516-1.
- ZIP SHA-256: 92df37ad1a0c292b32f3f823ac5ae080399495a2251b75c1477b3967b12db507; adviser recomputation matched GitHub.

Exactly seven files beneath gha-37152568516-1/:
- source/frozen_evidence_manifest.json
- contract/shadow_input_manifest.json
- implementation/code_manifest.json
- output/shadow_producer_output.json
- receipts/producer_execution_receipt.json
- execution_manifest.json
- shadow_report.md

## Independently inspected artifact facts supplied by adviser

|Binding|Value|
|---|---|
|Source receipt ID|source_capture:5b0c88919ac0fa608e4b6f00ab801742e36c0e6c00acaeee183a30576e5ec9d9|
|Source SHA-256|bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6|
|Canonical source receipt SHA-256|1cae5a9cf6a10491b88cc05221db65d5790fdc1128cd5c58909cd097a389e42d|
|Source rows|85|
|Frozen evidence body SHA-256|eee0347adac15dca9bc31a6d5e5475ce51b539a96772969dbbbdcd609e2af97f|
|Gate 2B-1 input_receipt_manifest_sha256|d47ffe5b7962d8dd232fde8e41f285a2443a3839ffe3892638f287be0e79f840|
|Gate 2A input_manifest_sha256|c7af4639b405347f9db5ff02d972008a96cab3805cffae5af67e99d4ab4f5879|
|Composite code_sha256|2bacdda9090a363306fb27ccb8f467c50b42897f7c6b226b06fd210811a207ff|
|Exact persisted shadow output SHA-256|090f40dc1dee84363acd3c758fc9b857d97437db721eba23fe22228fae73bdca|
|Execution ID / producer receipt ID|producer_execution:89fca2be40187ec90c629899c8c97e0967694f1392e12dafbc75e04313427d77|
|Canonical producer receipt SHA-256|a34638d7f20237858714020522b82a11e39db615a51d1da510cf45e5b8c1f46a|
|forecast_generation_utc|2026-10-03T20:46:20.351313Z|
|producer receipt_created_utc|2026-10-03T20:46:20.352558Z|

The adviser recomputed the frozen body, both input manifests, exact persisted output, canonical code manifest, canonical producer receipt and deterministic execution ID. All matched; producer receipt ID equalled execution ID; sole producer parent equalled the source receipt above.

Product dr002_integrity_shadow_weather; gate post_event; lane shadow_execution_only. Source scope: event 2026_1295_azerbaijan_baku_baku / meeting 1295 / session 11371. engine_implementation, engine_receipt_id and engine_result_sha256 all null.

binding_status=UNBOUND; production_authenticated=false; historical_availability_proven=false; dr002_activated=false.

## Limits

No historical blind forecast, production authentication, stable-engine execution or predictive accuracy is proven. GitHub artifact storage is not an established durable authenticated production store. No source bytes or runtime artifacts are copied into this repository checkpoint. DR-002 remains PROPOSED — NOT ACTIVATED. This Gate 2B-4 task did not rerun the workflow or call OpenF1.
