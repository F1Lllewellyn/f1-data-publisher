# DR-002 Gate 2B-3B1 — isolated execution shadow

DR-002 remains PROPOSED — NOT ACTIVATED. This is execution-chain infrastructure only; no live shadow workflow has been dispatched by this PR. Gate 2B-3B2 has not begun.

Starting main: 57f6aa3a071c720744fe321b6ab6cf51569b7472. The intervening main commit since the supplied baseline contained only generated session processor latest/history artifacts.
Branch: dr002-gate2b3b1-shadow-execution-adapter-20261003. The PR head is recorded in GitHub; embedding its own commit SHA here would be self-referential.

Exactly four additions:
- scripts/forecast_bundles/dr002_shadow_producer_execution_v1.py
- tests/test_dr002_shadow_producer_execution_v1.py
- .github/workflows/dr002-shadow-producer-pilot.yml
- docs/DR002_GATE2B3B1_SHADOW_EXECUTION_ADAPTER_2026-10-03.md

## Semantics

Product dr002_integrity_shadow_weather; contract dr002-shadow-weather-execution-v1; gate post_event; lane shadow_execution_only; execution_mode retrospective_shadow; contract_approved false. OUTCOME_AWARE_EVALUATION_ONLY. NOT A PREDICTION. No blind eligibility, forecast eligibility or accuracy claim.

The explicit capture manifest, receipt and exact raw bytes must match the supplied reviewed Baku weather pins, scope and observation times. The CLI offers no pin override. Synthetic tests inject separate pins solely to exercise behavior. These pins bind byte identity, not issuer authentication. No fake verified_receipt_bindings are created.

Exactly one capture is frozen using unchanged Gate 2B-3A helpers. The frozen evidence hash is not input_manifest_sha256. input_receipt_manifest_sha256 uses unchanged Gate 2B-1 sorted receipt-ID/canonical-receipt-hash semantics. input_manifest_sha256 uses unchanged Gate 2A declared forecast scope/cutoff/policy/evidence semantics. Evidence is projected from the receipt, with ingestion_required_at_cutoff=false. The cutoff is the 2026-10-03 observation, never the historical weather-row dates.

forecast_deadline_utc equals forecast_generation_utc: shadow execution boundary only — not a historical prediction deadline. Generation must follow source receipt creation. Identical complete execution facts produce identical canonical output and execution ID; different execution contexts/times can legitimately change the input hash and execution identity.

code_sha256 hashes a canonical, path-sorted four-file code manifest covering the adapter and the frozen-evidence, receipt-verifier and Gate 2A modules. It does not claim to bind Python/OS/runtime dependencies. git_commit is supplied context, not authenticated by this offline module.

forecast_payload_sha256 is the existing Gate 2B-1 field name; here it binds exact persisted/read-back execution-shadow payload bytes, NOT a production race forecast. The source row count is parsed independently. A single structurally validated producer_execution receipt names only the adapter, with the sole source_capture parent. engine_implementation, engine_receipt_id and engine_result_sha256 are all null. No stable engine or production producer executed.

The verified receipt candidate is published LAST, after manifest/report persistence. Failures raise, leave no successful final receipt, and may preserve HOLD diagnostics. Outputs require a fresh run-specific runtime directory. No latest/history/ledger/workbook writes or repository source discovery exist.

## Validation and boundaries

42 focused synthetic offline unittest methods passed, zero failures/errors. Command:
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_shadow_producer_execution_v1.py' -v`
Cheap AST/import checks passed. Gate 2A hashing and Gate 2B-1 structural compatibility exercised through imports; unrelated suites not run.

Workflow is manual-only, main-only, contents: read and actions: read, checkout credentials not persisted. It downloads only run 37133694090 / artifact dr002-weather-capture-37133694090-1, runs once and uploads only runtime shadow evidence. No network source call, repository write or workflow dispatch occurred in implementation.

Source evidence remains UNBOUND; production_authenticated=false; historical_availability_proven=false; dr002_activated=false. No authenticated execution, real stable-engine execution, historical availability or live forecast validity is proven. No forecast consumes these artifacts. Production code, model weights/priors/probabilities, workbook, gates, promotion and Pipedream unchanged. Forecast gate OFF; promotion NOT ALLOWED.

Known production contamination, lineage, blind eligibility and provenance defects remain OPEN. This adapter does not repair or execute the generic producer. Next separately authorized step is one Gate 2B-3B2 live shadow workflow run, after review/merge. Rollback: revert this isolated four-file PR; no migration.
