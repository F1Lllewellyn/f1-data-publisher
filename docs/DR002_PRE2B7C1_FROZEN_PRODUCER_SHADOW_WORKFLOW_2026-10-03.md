# DR-002 pre-2B-7C1 — Manual synthetic frozen-producer shadow path

Work order **F1-WO-DR002-PRE2B7C1-001**, issue #140. Part A: accepted PR #139 landed unchanged at `4f3d322478083d20f1a1c63be96a17a4f78bcdbd`. Starting main for Part B is the same commit. Nine relevant dependency fingerprints plus the two other accepted PR #139 blobs matched before mutation. Branch: `dr002-pre2b7c1-frozen-producer-shadow-workflow-20261003`.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Gate 2B-7 enforcement is not begun. This PR installs a manual path only; **no GitHub workflow has been dispatched by this work order**. Offline local subprocess unit tests are synthetic mechanics evidence, not a live GitHub pilot result.

## Fixed interface and containment

The new wrapper invokes the actual accepted producer as a separate Python CLI process. It neither imports the producer nor copies its scoring functions. Pin: Git blob `af27586668c767de126af829c1131c6bae4634ad`; exact producer code SHA-256 `8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564`. Both code bytes and unchanged pin are checked; changed code fails before execution, and a post-execution byte check detects changes during the bounded call. Hashes are byte identity, not a security sandbox or production attestation.

The wrapper packages fixed exact synthetic CSV bytes: drivers 10 / Synthetic Ten / Ferrari and 20 / Synthetic Twenty / McLaren; starting grid 20=1, 10=2; one weather row with air_temperature=25. Each carries synthetic event/meeting/session columns. Scope is `synthetic_dr002_frozen_producer_v1 / synthetic-meeting / synthetic-session`. Source IDs begin `synthetic:dr002:`. Manifest `dr002-frozen-producer-input-v1` binds each exact file and SHA, and is canonical packaging JSON. Its **exact file hash** is not Gate 2A input_manifest_sha256 or Gate 2B-1 receipt-manifest hashing. Inputs do not represent actual F1 source facts.

CLI passes --frozen-input-manifest, --event-id, --meeting-id, --session-id, --race-name, --gate post_qualifying, --lane stable_baseline, --strict-source and --repo-root pointing to a newly created disposable sandbox. No generation timestamp is supplied. The producer's real runtime supplies generation time. Lane is a label, not protected-engine provenance. The predictive gate tests synthetic CLI mechanics and does not establish prospective blind validity.

Existing producer latest/history/runtime and compatibility-mirror writes occur **only in the disposable sandbox**. No checked-out latest/history/ledger/workbook output root is passed. The wrapper verifies explicit output paths derived from the producer's stdout run ID, without scanning. It checks persisted audit equals stdout, frozen-mode/hash/scope/source identity/count bindings, false trust/promotion flags, two synthetic drivers/grid, expected readiness, generation-time syntax, source snapshot bindings and byte-equality across latest/history/mirrors. A failed check is HOLD; there is no retry.

After verification, exact evidence bytes are copied/read back under `_runtime/dr002_pre2b7c_frozen_producer_shadow/<run-id>/evidence/`. With default weather included, nine evidence files are preserved: frozen_input_manifest.json, drivers.csv, starting_grid.csv, weather.csv, producer_code.py, producer_audit.json, source_snapshot_manifest.csv, forecast_rows.csv, forecast_metadata.json. No scientific receipt is emitted. Sandbox disposal occurs before success publication. shadow_report.md is persisted before execution_manifest.json, which is published last. Failure removes any success manifest and preserves a HOLD report when possible; partial evidence is not success. Existing attempts cannot be overwritten.

Execution manifest schema `dr002-frozen-producer-shadow-pilot-v1` records implementation SHA supplied by workflow, producer Git blob/code SHA, exact input-manifest SHA, scope, sources and row counts, gate/lane, row count/readiness, producer run ID/runtime generation time/exit code and exact copied evidence hashes. It records synthetic_inputs=true, producer_audit_broad_discovery_used=false, sandbox disposed=true, checkout_production_outputs_written=false, production_forecast_generated=false, production_authenticated=false, historical_availability_proven=false, stable_engine_execution_proven=false, blind_validation_eligible=false, dr002_activated=false.

The outer status is **SHADOW_EXECUTION_ONLY_NOT_A_PRODUCTION_FORECAST**. Copied producer rows/metadata retain their original generic producer strings, including legacy blind-validity wording; they are inspection evidence only. The outer shadow ceiling must not be discarded to republish them as forecasts. No engine/producer execution, normalization, lock, outcome or revision receipt/binding is fabricated.

## Workflow and activation boundary

New workflow is workflow_dispatch only, job restricted to refs/heads/main, contents:read, checkout exact github.sha with persist-credentials:false. It uses Python 3.12 and runs this fixed wrapper once, passing GitHub SHA and gha-run/attempt ID through environment variables. Upload-artifact publishes only the dedicated runtime directory. No schedule/workflow_call, production secret, repository-write permission, git commit/push, API capture, stable engine or production workflow/orchestrator call. Existing workflows/config/orchestrator remain byte-for-byte unchanged. The new path is inactive until separately authorized manual dispatch after review/merge.

## Twelve scientific conclusions

1. OBSERVED IMPLEMENTATION FACT: a manual GitHub path capable of invoking frozen-mode producer is installed by this PR; live GitHub execution is **not yet demonstrated**.
2. EXECUTED OFFLINE TEST FACT: the real producer CLI runs; no scoring implementation is copied/imported into the wrapper.
3. EXECUTED OFFLINE TEST FACT: latest/history/runtime outputs occur in a temporary sandbox, are checked, and the sandbox is disposed. No checked-out production output is written.
4. OBSERVED IMPLEMENTATION FACT: input bytes and scope are explicit and synthetic.
5. EXECUTED OFFLINE TEST FACT: audit proves frozen mode/broad_discovery_used=false for tested executions; rogue latest/history/adjacent files cannot alter the accepted result.
6. OBSERVED WORKFLOW FACT: workflow is manual-only and remains undispatched in this work order.
7. Source authentication proven? **No.**
8. Stable-engine execution proven? **No.**
9. Blind historical forecasting proven? **No.**
10. Live lock/outcome/revision proven? **No.**
11. DR-002 or Gate 2B-7 activated? **No.**
12. RECOMMENDATION: Adviser delta review; if accepted, separately authorize merge and **exactly one** manual GitHub shadow dispatch followed by independent artifact inspection. This recommendation does not authorize either action.

## Validation / scope / rollback

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_frozen_producer_shadow_pilot_v1.py' -v`

**33 focused offline tests pass; zero failures/errors.** Cheap AST/import and YAML-text checks pass. Tests execute real CLI calls, exercise pins, explicit scope/command, synthetic counts/grid/readiness, real runtime time, rogue inputs, sandbox lifecycle, exact evidence hashes, trust ceilings, tampering, diagnostic failure/no success, duplicate attempts, no retry and manual workflow boundaries. No unrelated suite ran; the accepted predecessor's 45 tests were not redundantly rerun. No CI success is claimed.

Exactly four additions: workflow, wrapper, focused tests, this checkpoint. Accepted producer is unchanged, as are every existing workflow, orchestrator, policy, DR-002 implementation/contract, engine, workbook and production artifact. Forecast gate OFF; promotion NOT ALLOWED; no production forecast generated or committed. Pipedream/Gmail not used. No accuracy claim. Rollback: revert this isolated PR; no data migration. Return to Adviser review; do not merge or dispatch here.
