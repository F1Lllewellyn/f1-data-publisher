# DR-002 Gate 2A checkpoint

Status: PROPOSED — NOT ACTIVATED. Isolated contract and acceptance tests only.

Fresh main baseline: `19a13debc3dbc92b18b4efbe27ad56d0e6856151`.
The unrelated `dr002-gate2a-integrity-contract-20260927` branch was not used.
Gate 1 audit baseline: `b4c46c2643dc5762512bc04bd630a96f20ea1326`.
Relevant producer, writer, locker, orchestrator, source collector, readiness,
grid-provenance and temporal-harness files were unchanged at the fresh baseline.

## Scope and exact changed-file list

All six files are additions:

- `scripts/forecast_bundles/forecast_integrity_contract_v1.py`
- `schemas/forecast_integrity_contract_v1.schema.json`
- `tests/fixtures/dr002_integrity_v1.json`
- `tests/test_forecast_integrity_contract_v1.py`
- `.github/workflows/dr002-integrity-contract-tests.yml`
- `docs/DR002_GATE2A_CHECKPOINT_2026-09-27.md`

The module is a pure, deterministic, standard-library-only assessor. It has no
filesystem/network writes, wall-clock reads, production imports or live callers.
The new workflow is pull-request-only, read-only, and runs offline tests. No
scheduled production workflow changes. Revert this isolated PR to roll back.

## Contract and trust boundary

`classify_forecast(record, verified_execution_records=...)` returns the state,
derived blind flag, sorted reason codes and separate revision events. The input
JSON Schema describes fields; runtime semantic checks are implemented in Python
without a JSON Schema dependency. Extra input keys are ignored and confer no
eligibility (in particular `source_found` and historical blind flags).

Lane name and implementation are independent. An execution receipt must match
implementation, Git commit, code hash, invocation ID, canonical input-manifest
hash, forecast-payload hash and engine implementation. A non-null engine claim
also requires matching engine_execution_id, engine_code_sha256 and
engine_execution_proof_ref in the trusted receipt. It must come from a
separate trusted verifier. Stable-engine attribution cannot be inferred from the
lane or self-asserted engine label. The input-manifest hash binds scope, contract,
cutoff, deadline and consumed evidence; the classifier recalculates that hash.

This layer verifies consistency of supplied evidence, not authenticity of an
external capture, execution or durable-lock receipt. Production adapters must
authenticate those references and bytes before supplying them. A synthetic
receipt in tests proves validator behaviour, not real stable-engine execution.
No live VALID_LOCKED claim or historical migration is made by this PR.

All consumed evidence, including optional evidence, must match event/meeting and
the explicit session allowlist; absent allowlist means target session only.
Empty or duplicate allowlists and duplicate source IDs fail closed. Mandatory
source IDs must be nonempty and complete. A source ID identifies one required
capture slot; future multi-version requirements need distinct declared IDs.

First observation and ingestion are separate required UTC timestamps. First
observation must be at/before cutoff. Ingestion must follow observation and
precede generation; a contract flag additionally requires ingestion by cutoff.
Event/publisher times may be null and never substitute for observed availability.
Event time may describe a future scheduled event; it is not an availability test.

Cutoff <= generation <= lock, cutoff <= deadline < outcome boundary, and
cutoff/generation/lock < outcome boundary are required. The outcome boundary
needs its own evidence reference; later local discovery is not proof of earlier
unavailability. Lock requires a separate receipt reference. Exactly-at-deadline
lock is permitted; exactly-at-outcome is not blind. Missing times are never
filled from lock time or the current clock.

## State precedence and revisions

1. Known evaluation gates always return OUTCOME_AWARE_EVALUATION_ONLY.
2. Legacy/unknown schema is TEMPORAL_ELIGIBILITY_UNPROVEN and is never upgraded.
3. Replay/manual-validation executions cannot become blind forecasts.
4. Unsupported gates, missing contracts/provenance, malformed inputs or scope
   ambiguity return HOLD. Demonstrable outcome-aware timing returns evaluation.
5. A verified, relevant, unincorporated revision first observed before the
   deadline under the explicit supersession policy returns SUPERSEDED.
6. Otherwise an eligible input set locked late returns MISSED_DEADLINE.
7. Otherwise return VALID_LOCKED. Only this state sets blind eligibility true.

ForecastState and RevisionEventState are separate machine-readable vocabularies.
The top-level `state` uses only the six forecast classifications; entries in
`revision_events` use `event_state`, whose sole value is POST_CUTOFF_REVISION.
POST_CUTOFF_REVISION is a separate event classification nested in the result,
not a destructive replacement for VALID_LOCKED. A relevant revision observed
after deadline leaves the original classification intact. This resolves the
design's distinction between forecast state and external-event state.
Exactly-at-deadline revision observation is unresolved and returns HOLD with an
explicit reason, rather than silently choosing a boundary rule.

No final_pre_race gate is added. Revision semantics are tested against a synthetic
contract using an existing gate name. This is not approval of live gate offsets,
mandatory-source requirements, scoring selection or revision policy. A late
replacement is MISSED_DEADLINE; the superseded prior record remains superseded.
There is no fallback-selection or scoring code in this layer.

## Evidence, validation and ownership

Run: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_forecast_integrity_contract_v1.py' -v`

41 offline unittest methods pass, including subcases for scope dimensions and
evaluation gates. Fixtures are explicitly synthetic, not fabricated historical
observations. Tests cover every requested acceptance case, input-hash tampering,
missing execution proof, malformed UTC, exact lock boundaries, legacy handling,
and input immutability. No production producer or historical bundle is executed
or rewritten by the tests.

Existing owners remain: lightweight source closure collects evidence; the
producer generates rows; writer normalizes; locker stores history; session
processor owns grid/readiness safeguards. This module does not replace or invoke
any of them. Gate 1's source_found/blind defect, mislabeled stable lineage,
cross-meeting inputs and unsupported locker argument remain live open defects
until separately authorized integration/operational PRs.

## Protected decisions and next gate

No stable-engine/workbook changes; no coefficients, prediction values, outputs,
gate definitions, promotion rules or scheduled workflows changed. Historical
bundles remain byte-for-byte intact. No dependency removals, including Pipedream.
No branch-protection changes. DR-002 is not activated.

Next action is review of this Gate 2A PR. Gate 2B is not authorized. Before live
integration, approve concrete product contracts and implement authenticated
receipt adapters. Existing unproven history must remain unproven, with any later
assessment stored separately. Never use later API responses to backdate evidence.


## PR #122 bounded amendment

Amendment parent: `1e60373d3b0dfadff51aa4fe9bf5717e7b47ce42`.
Only five existing PR files changed: classifier, schema, synthetic fixture,
acceptance tests and this checkpoint. The PR-only/read-only CI file is unchanged.

The engine proof is separate from producer-wrapper lineage. Matching an engine
name string alone fails closed. A generic wrapper's code hash cannot be reused
as the hash of a differently identified engine. Hash sharing is supported only
when the declared producer and engine implementation identities are the same
and the trusted receipt matches. No engine code is executed by these tests.
Null engine implementation with null engine-provenance fields remains valid;
orphan engine provenance without an engine claim is rejected.

The schema defines forecast_classification_state and revision_event_state
separately and binds them to top-level state and nested event_state respectively.
Exactly-at-deadline revision observation still fails closed. No new boundary
policy or production gate was introduced. All prior acceptance cases remain in
the full 41-method suite, supplemented by engine identity/hash/proof mismatch,
missing fields, wrapper-hash misuse, and null-engine tests. External receipt
authentication remains outside this isolated consistency checker.

This amendment does not merge PR #122, activate DR-002 or authorize Gate 2B.
