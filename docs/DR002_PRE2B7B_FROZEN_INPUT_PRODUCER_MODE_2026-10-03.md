# DR-002 pre-2B-7B — Inactive frozen-input producer mode

Work order: F1-WO-DR002-PRE2B7B-001 / issue #138. Part A landed accepted PR #137 unchanged at `27f00889f7432f7f8bd5cf601ed75d21bf2f711d`. Part B starting main is that same commit. Seven declared dependencies and three accepted predecessor blobs matched before mutation. Branch: `dr002-pre2b7b-frozen-input-producer-mode-20261003`.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Installed capability is opt-in; scheduled behavior is unchanged. Forecast gate OFF; promotion NOT ALLOWED. Stable engine and canonical workbook untouched. No live API, workflow dispatch, production forecast commit, receipt creation, authentication or enforcement.

## Input boundary

The real producer now accepts `--frozen-input-manifest PATH`, requiring `--meeting-id` and `--session-id` together with existing `--event-id`. Without the new option, the same find_sources discovery, CLI defaults, scoring, output writers and legacy snapshot schema remain available. No workflow/orchestrator/config invokes the new option.

Manifest schema is `dr002-frozen-producer-input-v1`. Exactly these top-level keys are accepted: schema_version, event_id, meeting_id, session_id, sources. Each source has exactly source_name, source_id, relative_path, source_sha256. Identity values are strings; SHA-256 is lowercase hexadecimal. No trust fields are accepted. Root is the supplied manifest's parent directory. Exact manifest bytes are hashed separately for audit; this is **not** Gate 2A input_manifest_sha256 or Gate 2B-1 input_receipt_manifest_sha256.

All entries validate before scoring. Names must be existing SOURCE_FILES keys. Duplicate names/IDs/paths, missing/empty files, malformed hash/CSV, absolute/non-canonical/traversing paths, symlinks and scope disagreement fail the whole input load. Duplicate JSON keys are rejected. Every present event_id, meeting_id/meeting_key, session_id/session_key CSV column must match explicit scope. Missing row scope is declared scope only, not independently proven provenance.

Only individually named files are read. There is no scan, candidate-priority, glob/rglob or fallback in frozen mode. Validated exact bytes are copied to disposable temporary snapshots and read back; existing read_csv and producer functions consume those snapshots, preventing later original-file alteration from bypassing the checked hash. Temporary paths are omitted from audit/output metadata and cleaned up even on failure. Omitted source types retain zero counts. Source parsing/scoring/universe/grid/readiness/probability algorithms are reused unchanged.

The audit records input_mode=frozen_manifest, schema_version, exact frozen_manifest_sha256, event/meeting/session, sorted source identities/hashes/relative paths/row counts, broad_discovery_used=false, production_authenticated=false, historical_availability_proven=false, stable_engine_execution_proven=false, dr002_activated=false. Frozen-mode source snapshot rows add source_id/source_sha256/relative_path; default snapshot columns remain unchanged. Existing output writers are intentionally retained; this option is not a no-publish switch. A future manual/shadow caller must disable publishing separately.

## Scientific conclusions

1. OBSERVED IMPLEMENTATION FACT: explicit frozen-input mode is part of the real current producer.
2. OBSERVED REPOSITORY FACT: current workflows, orchestrator and policies are byte-for-byte unchanged and do not opt in. Capability is installed but inactive.
3. EXECUTED TEST FACT: frozen mode bypasses discovery; denied find_sources/glob/rglob cannot affect execution. Rogue latest/history and adjacent undeclared sources cannot change the result.
4. EXECUTED TEST FACT: default mode still calls find_sources and preserves default output/snapshot semantics. Existing scoring functions and priors were not changed.
5. Source authentication proven? **No.** Hashes identify bytes only.
6. Protected stable-engine execution proven? **No.** stable_baseline remains a lane label; no engine receipt/proof exists.
7. Live lock/outcome/revision proof established? **No.** No new receipt is produced.
8. RECOMMENDATION: separately authorize a manual/shadow workflow that packages exact inputs and invokes this mode with commit/publish disabled, then separately authorize one evidence-backed live shadow run. Neither is implemented here.

## Compatibility disclosure

The pre-2B-7A adapter deliberately pins the *previous* generic producer Git blob. This authorized producer modification changes that blob. Consequently, running that older adapter against the modified implementation will fail closed with current_producer_fingerprint_changed. Its historical accepted proof remains intact; no pin is silently upgraded and no prior adapter/test is modified. Future use requires separately reviewed compatibility work or the accepted historical commit. This is a deliberate version-bound proof ceiling, not evidence that the stable engine ran.

Original producer row strings (including older blind-validity wording) remain unchanged; this work does not fix those legacy scientific defects. Frozen metadata expressly does not establish blind eligibility, source availability or DR-002 activation.

## Validation / rollback

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_frozen_input_producer_mode_v1.py' -v`

45 focused offline tests pass, zero failures/errors. Syntax/import checks pass. Only synthetic inputs in temporary directories were used; output publication was mocked in CLI tests. No unrelated suite ran. No CI success is claimed.

Exactly three files: modified producer, new focused tests, this checkpoint. No workflow, orchestrator, policy, DR-002 contract, locker/source writer, stable engine, model parameters, workbook, latest/history/ledger or bridge change. Pipedream/Gmail not used. Rollback is reverting this isolated PR; no migration. PR remains for Adviser review, not merged. Gate 2B-7 enforcement has not begun.
