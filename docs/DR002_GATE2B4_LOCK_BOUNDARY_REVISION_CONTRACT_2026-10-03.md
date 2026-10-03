# Gate 2B-4 offline lock / boundary / revision contract

DR-002 remains PROPOSED — NOT ACTIVATED. Offline contracts and synthetic tests only; no production activation, workflow, network call, real forecast lock or live outcome/revision capture occurred.

Starting main: 8d164fce63aea97aee7c2db71b6eb23d8f5e2055; no intervening movement.
Branch: dr002-gate2b4-lock-boundary-revision-20261003. GitHub records the final PR head (embedding this file's own commit hash would be self-referential).

Exactly four new files:
- scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py
- tests/test_dr002_lock_boundary_revision_v1.py
- docs/DR002_GATE2B3B2_LIVE_SHADOW_EXECUTION_CHECKPOINT_2026-10-03.md
- docs/DR002_GATE2B4_LOCK_BOUNDARY_REVISION_CONTRACT_2026-10-03.md

## Contract

build_forecast_lock binds exact caller-supplied bytes to the existing producer payload hash, scope, execution identity and unchanged Gate 2A input manifest. lock_utc is explicit, distinct from generation and receipt creation; generation <= lock <= creation. storage_ref is explicit, not independently proven durable. stored_payload_sha256 equals the exact byte hash; no serialization substitute or file mtime exists. Receipt identity binds type/scope/parent/hash/time/storage, without hashing itself.

build_outcome_boundary requires a separate valid parentless source_capture, explicit outcome session and policy reference. It rejects input capture IDs and input source IDs. Its boundary equals only outcome first_observed_utc, never event/publisher/scheduled time. The outcome session must already be target or explicitly allowed under the unchanged Gate 2B-1 graph contract. This layer does not broaden MANIFEST_KEYS or invent race policy. An unrelated outcome session requires a separately reviewed future contract rather than silent acceptance.

build_revision requires explicit captures matching one original source ID, URI and session, with different content hashes and valid observation chronology. Identical content is not a revision. Deterministic revision IDs and declared entries bind the source parent and forecast identity. Duplicate captures/observations fail closed. Revision receipts record observations; they never decide scoring or mutate prior artifacts.

complete_forecast_record deep-copies the forecast and fills only lock/boundary proof fields and sorted revisions. All MANIFEST_KEYS remain unchanged; input_manifest_sha256 must still equal the executed producer's value. No normalization or engine receipt is emitted.

verify_and_classify validates the new construction bindings, then calls unchanged verify_receipt_chain and classify_forecast. It requires external bindings supplied by the caller; the builder never manufactures them. Only successful graph verification provides execution records to Gate 2A. Tests may create explicitly synthetic bindings outside the builder.

Gate 2A remains the sole classification authority: otherwise valid no-revision forecasts can be VALID_LOCKED; unincorporated pre-deadline revisions can SUPERSEDE; after-deadline revisions remain separate POST_CUTOFF_REVISION events; exactly-at-deadline returns HOLD / revision_at_deadline_policy_unresolved; incorporated-after-cutoff returns HOLD; late lock returns MISSED_DEADLINE; post_event remains OUTCOME_AWARE_EVALUATION_ONLY. These are fixture outcomes, not production forecast validity claims.

## Trust and validation

External binding interface != production authentication. Receipt existence, identity/hash checks and explicit timestamps do not prove truthful clocks, storage immutability, source completeness, policy authority or historical availability. The lock constructor binds supplied bytes; it does not persist them or operate a production lock store. A locked UNBOUND chain remains UNBOUND.

binding_status=UNBOUND; production_authenticated=false; historical_availability_proven=false; dr002_activated=false. No trust upgrade.

47 focused deterministic offline tests pass, zero failures/errors, including positive full receipt graphs with/without revisions, missing binding failure, exact byte tampering, all deadline classifications, separate outcome enforcement and boundary tampering. Existing Gate 2A/Gate 2B-1 imports provide compatibility; no existing implementation/schema changed.

Command: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_lock_boundary_revision_v1.py' -v`.
Cheap AST/import checks passed. No unrelated suite was run.

Stable engine, production producer, model/scoring/gates, canonical workbook, schedules, latest/history/ledger artifacts and Pipedream untouched. Forecast gate OFF; promotion NOT ALLOWED. No prediction generated. Gate 1 production provenance defects remain OPEN. Next planned stage: separately authorized Gate 2B-5 full shadow assessment, not begun here.

Rollback: revert this isolated PR; no production/data migration. Review by Science / Architecture Adviser before merge.
