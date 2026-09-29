# DR-002 Gate 2B-1 checkpoint — 2026-09-29

DR-002 remains **PROPOSED — NOT ACTIVATED**.
Gate 2B-1 is offline receipt/verifier infrastructure only. No live caller depends
on it; no production receipt, capture pilot, shadow assessment or enforcement is
created. No historical forecast is upgraded. No accuracy or promotion claim is made.

## Baseline and bounded branch

Started: `2026-09-29T09:02:17Z`.
Fresh main: `88fb46938aef323f56636933fe42d09193cd090d`.
Branch: `dr002-gate2b1-offline-receipts-20260929`.
Implementation head/PR/CI evidence is recorded below after publication. The final
checkpoint-containing head is available from the PR; a commit cannot embed its
own SHA. This branch was newly created from fresh main. Neither Gate 2A branch
was reused or deleted. The unfinished September 27 draft remains separate and
is not part of this PR; its proposed HMAC approach is not used here.

Five commits intervened after reviewed `fe0b293bfa71f53baae7e097f9415b283e387fe5`:

| Commit | Classification |
| --- | --- |
| `e0b7a6e147c59e528644a3bfe707838dd572c5af` | Generated source-backed workbook KPI handoff artifacts |
| `7969e5a6b102c65103f7be038b569155cfcb9fa5` | Generated readiness dashboard/context artifacts |
| `39fb754c5018a9088a2f676a94912a30f29aac3e` | Generated auto-repair status/history artifacts |
| `3eb7cd7c22e9576d2da08233c3267bec8ec6b021` | Generated sandbox workbook KPI refresh artifacts |
| `88fb46938aef323f56636933fe42d09193cd090d` | Generated consumer/context/trigger/workbook persistence artifacts |

The comparison contained only history/latest artifacts. None of the eleven
implementation/contract paths in the authorization changed. Gate 2A's original
41 tests passed before implementation; no Gate 2A classifier/schema/test/fixture
file is changed by this PR.

## Exact file boundary

Five additions:

- `schemas/forecast_integrity_receipt_v1.schema.json`
- `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py`
- `tests/fixtures/dr002_receipts_v1.json`
- `tests/test_forecast_integrity_receipts_v1.py`
- `docs/DR002_GATE2B1_CHECKPOINT_2026-09-29.md`

One modification:

- `.github/workflows/dr002-integrity-contract-tests.yml`

No other repository files are authorized. The workflow remains pull-request-only,
`contents: read`, checkout `persist-credentials: false`, with no scheduled/manual
trigger, production credentials, repository-write step or network-dependent test.
It runs the existing suite unchanged and the receipt suite as separate steps.

## Shared receipt and graph model

One strict envelope contains schema_version, receipt_id, receipt_type,
receipt_created_utc, scope, parent_receipt_ids and a typed payload. Receipt creation
is assembly time, never source observation, publication, ingestion or lock time.
Source captures require event/meeting/session identity, but do not invent product,
forecast, gate or lane identity. Other types require all seven identity dimensions.
Unscoped sources cannot be represented as scoped evidence by filling fake IDs.

| Type | Parents and bindings |
| --- | --- |
| source_capture | No parents; source ID/URI/hash, event and publisher times nullable, first observation, ingestion, capture reference/implementation |
| engine_execution | Source capture parents; engine identity, code hash, invocation, repository commit when repository-backed, input manifests and result |
| producer_execution | All consumed source parents and optionally one engine; actual implementation/commit/code/execution, generation, frozen input hash, output hash |
| normalization | Exactly one producer or preceding normalizer; implementation/commit/code/execution, exact different input/output hashes and completion |
| forecast_lock | Exactly one producer or normalizer; locked and stored payload hashes must match its output; explicit lock_utc and durable storage reference |
| outcome_boundary | Exactly one evidence-bearing source capture; explicit policy reference, product contract, source/hash and supplied boundary |
| revision | Exactly one revised capture; affected forecast/product/scope, source/hash and matching first observation |

Engine, normalization and revision are conditional. A no-engine producer and a
direct producer-to-lock chain are valid. Multiple genuine normalizations are
supported. Engine result bytes may differ from wrapper forecast bytes: the
producer's separate engine_result_sha256 binds that result without redefining
forecast_payload_sha256. Engine code cannot borrow a differently named wrapper's
hash. No stable-engine code is loaded or executed.

Input order is irrelevant. Duplicate IDs/parents, missing/unknown parents,
self-parenting, cycles, wrong parent types and unrelated receipts fail closed.
Outcome and revision receipts are associated evidence branches, never ancestors
that rewrite the original lock. Revision state/scoring decisions remain Gate 2A
or later-policy responsibilities; this verifier emits no forecast state.

## Hashes and trust boundary

Canonical receipt JSON uses sorted keys, compact separators, ASCII escaping and
finite numbers only. SHA-256 is calculated over the entire receipt. Hashing is
content identity, NOT cryptographic provenance or proof of an honest clock.

`verified_receipt_bindings` is a separate mapping:
`receipt_id -> {receipt_sha256, verification_ref}`. The verifier checks its digest
against the receipt. It does not create, sign or authenticate this mapping. A
future production adapter must independently authenticate the binding provider
and authorize issuer, code, policy and time claims before supplying it. Passing
a caller-created mapping does not become production authentication. Self-asserted
trust/proof fields inside receipts fail the strict schema; absent bindings fail.

Synthetic verified receipts prove deterministic verifier behavior only.
They do not prove production authentication, real stable-engine execution,
historical first observation, or live forecast validity.

Results always retain `production_authenticated: false` and
`trust_scope: EXTERNAL_BINDING_INTERFACE_ONLY`. VERIFIED_BINDINGS means only that
the supplied external expectations, bytes and semantic graph agree. MALFORMED and
UNVERIFIABLE return no execution projection. The standard-library module performs
no network/filesystem I/O, wall-clock reads, signing, HMAC, PKI or mutation.

Backdating tests prove that later receipt alteration cannot retain the old external
hash binding. They do not prove capture-system honesty. Event/publisher/Git/history
or receipt-creation times never fill missing first_observed_utc. Observation must
precede ingestion; consumed evidence must pass the explicit cutoff/ingestion rules.
A stored-payload hash and signed-looking URI alone do not prove durable storage;
that remains the future lock adapter's responsibility.

The Gate 2A input_manifest_sha256 retains its exact existing field set and canonical
encoding. A separate input_receipt_manifest_sha256 binds the sorted consumed
source receipt ID/digest list. These are different hashes with different meanings.
The Gate 2A projection is built only after complete binding/graph validation. Engine
proof references come from the engine receipt's external verification_ref, never
from a lane or wrapper label. Synthetic no-engine and distinct-engine projections
are accepted by the unchanged Gate 2A classifier in offline compatibility tests.

Scope and limits: one forecast/producer chain per call; permitted evidence sessions
are explicit. The verifier checks only revisions supplied in that chain; it cannot
prove a production observer has discovered every revision. Boundary policy meaning,
issuer authorization and actual storage immutability are external obligations.
No product cutoff, deadline, outcome boundary or gate is invented or approved.

## Existing ownership and defects remain open

- Experimental FastF1 live capture already records run/session/timing/package
  metadata. Recording start is not every datum's first observation; ZIP SHA is
  not a raw-feed payload receipt. No live-capture adapter is added here.
- Lightweight OpenF1 closure owns request logs, session queries, aggregate CSV
  hashes and history. Aggregate-source contamination remains unresolved; a
  season-wide file must not be relabeled as a single-session payload.
- Session Data Processor remains the strongest future capture-adapter candidate:
  HTTP/normalized hashes, scope, paths, validation and grid provenance are useful.
  Existing official_final_grid_verified=false safeguards remain untouched.
- Generic producer lineage remains path/count based without authenticated input,
  execution or separate-engine capture. Stable-lane attribution is still defective.
- Source writer performs actual normalization; future receipts should bind it
  conditionally, not duplicate or replace it.
- Bundle source_timestamp_utc remains lock/copy time; source_found still does not
  prove blind eligibility. Legacy/evaluation bundles are not upgraded by this PR.
- Both f1-forecast-gate-source-writer-v1.yml and f1-forecast-bundle-locker-v1.yml
  pass --commit-outputs while their invoked scripts do not define that argument.
  These pre-existing workflow/script mismatches require separate bounded repairs.
- Gate 2B-1 alone closes none of these live production provenance defects.

## Validation and rollback

Commands (offline, no production execution):

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_forecast_integrity_contract_v1.py' -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_forecast_integrity_receipts_v1.py' -v
```

Gate 2A: 41 passing methods, zero failures/errors.
Gate 2B-1: 75 passing methods, including subcases covering the required matrix,
zero failures/errors. Repeated and reordered verification is explicitly tested.
Complete suites are rerun before publication; PR-only CI evidence is recorded below.

No production caller imports the new verifier. No synthetic receipt is placed in
latest/history. No engine/workbook/model/gate/forecast/promotion/scoring/schedule,
historical bundle, Pipedream route or branch protection is changed. Uploaded
workbooks are not used as repository baselines or modified.

Rollback: revert this isolated PR. No production/data migration is required.

## Later sequence — review only

1. Gate 2B-1: offline receipt/verifier contract — this PR, not merged.
2. Gate 2B-2: capture provenance pilot — not started.
3. Gate 2B-3: containment + execution shadow adapter.
4. Gate 2B-4: lock/outcome-boundary/revision proofs.
5. Gate 2B-5: full shadow integrity assessment.
6. Gate 2B-6: replay + leakage evidence.
7. Gate 2B-7: separately approved production enforcement.

Return this PR to the Science / Architecture Adviser. Merge and Gate 2B-2 require
separate authorization. DR-002 remains PROPOSED — NOT ACTIVATED.
