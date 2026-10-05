# DR-002 pre-2B-7F2 — offline verified-source consumer composition

Work order: [#154](https://github.com/F1Lllewellyn/f1-data-publisher/issues/154), `F1-WO-DR002-PRE2B7F2-001`.

Result: implementation complete; independent Adviser review pending.
DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate OFF. Promotion NOT ALLOWED.

## Predecessor and scope

Accepted PR #153 was checked at reviewed head `6af22e6734b8c9c62234ed3c184216dc4c76db5b`, with exactly its three authorized additions and expected blobs, then merged unchanged as `04fedda42b2b65f790d22814c7ff7252b03a1e43`.

Starting observed main was `0c112fb06778091b5b6cbc246b9f11fbdf114402`. Its delta from the work order's observed main contained 202 files, all under `latest/` or `history/`; declared dependencies matched. Implementation baseline after Part A: `04fedda42b2b65f790d22814c7ff7252b03a1e43`.

This Work Result adds exactly:

- `scripts/forecast_bundles/dr002_verified_source_consumer_v1.py`
- `tests/test_dr002_verified_source_consumer_v1.py`
- `docs/DR002_PRE2B7F2_VERIFIED_SOURCE_CONSUMER_2026-10-04.md`

No existing file changes. Earlier unpublished local F1 work was not reused over the independently completed and accepted PR #153. The current GitHub work order and its exact accepted dependencies govern this implementation.

## API and composition

`consume_verified_source(*, receipt_bytes, source_bytes, request_scope, bridge_result)` accepts exact bytes and explicit in-memory inputs. `request_scope` contains exactly `event_id`, `meeting_id` and `allowed_session_ids`. No paths, network clients, environment secrets, clock, subprocess or producer are accepted or invoked.

Validation is sequential and fail-closed:

1. Strictly parse receipt JSON, rejecting duplicate keys and nonfinite values; use unchanged Gate 2B-1 envelope and temporal helpers; require a parentless `source_capture`.
2. Require exact receipt bytes equal unchanged canonical bytes and independently compute canonical/exact receipt SHA-256. Separately hash exact source bytes and match `payload.source_sha256`.
3. Validate explicit request shape and event/meeting/session allowance against the receipt.
4. Require the exact successful F1 output envelope, including its schema version, status, GitHub-only trust scope, matching receipt/hash fields, exactly one binding and all six ceiling values strictly boolean false. Missing or extra fields HOLD as ambiguous.
5. Pass the supplied binding through unchanged Gate 2B-1 `_external_binding`. Preserve its values in a new output dictionary. Require the internal observation claim to equal the receipt claim and the existence bound to be a valid UTC value no earlier than receipt creation.
6. Invoke the unchanged frozen-evidence builder using two fixed dictionary tokens (`receipt`, `source`) and an explicitly supplied dictionary reader. Unknown tokens raise; there is no filesystem fallback or discovery.
7. Validate the returned manifest through the existing validator, then explicitly require its trust block to contain exactly `binding_status=UNBOUND`, `production_authenticated=false`, `historical_availability_proven=false`. Return it unchanged.

The success status is `OFFLINE_VERIFIED_SOURCE_CONSUMER_VALIDATED`. Output includes the complete existing frozen-evidence result (body and hash), the separate single binding, receipt ID, exact/canonical/source hashes, GitHub-only binding trust scope, existence upper bound, internal observation claim, `frozen_manifest_binding_status=UNBOUND`, and all six false ceilings. HOLD returns no manifest and an empty binding map. No input or returned builder manifest is rewritten.

## Trust boundary

The successful F1 bridge result remains a **caller-supplied trust interface**. Its fields cannot prove their own origin. The caller must obtain it through the accepted F1 bridge and approved external cryptographic-verifier boundary. This consumer neither re-verifies signatures nor authenticates arbitrary JSON presented with a success label.

The verified binding is a separate companion projection. It does not replace the frozen manifest's trust block, and the manifest's existing content hash and receipt-set hash retain their original meanings. Acceptance of a binding by `_external_binding` proves interface/hash consistency, not a complete forecast chain or production admission.

The carried attested existence time remains only an upper bound conditional on the upstream verification. The internal first-observed timestamp remains an unauthenticated receipt claim. No publisher authenticity, earliest/historical availability or observation completeness is inferred.

The imported accepted builder/bridge retain their existing import setup and optional CLI/filesystem facilities. This consumer invokes only their in-memory helpers and explicitly overrides the builder's default reader. It adds no CLI or production caller.

## Focused evidence

Command from repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_verified_source_consumer_v1.py' -v
```

**19 test methods PASS; zero failures/errors**, with matrix/subtests covering all 16 required categories. Tests call the accepted F1 bridge using its existing synthetic fixture, adjusted to hash explicit synthetic source bytes. These fixtures assert a synthetic external-verifier boundary; they do not claim valid signatures or live capture.

Coverage includes:

- Exact successful envelope, unchanged Gate 2B-1 binding acceptance, unchanged builder output equality and manifest validation.
- UNBOUND manifest trust and separate companion binding; source hash distinguished from receipt hash.
- Noncanonical/malformed/parented/valid non-source receipt HOLD; source mismatch and malformed bytes HOLD.
- Event, meeting, session and malformed request HOLD.
- Bridge status, schema, trust scope, missing/extra/wrong binding, receipt/hash field and every false-ceiling mismatch HOLD, including nonboolean false-like values.
- Observation-claim mismatch and malformed/too-early existence bound HOLD.
- Corrupt builder hashes and attempted manifest trust upgrades HOLD without repair or mutation.
- No input mutation, repeated-call equality, output alias isolation, blocked file/network calls, closed reader behavior and static absence of new I/O/clock/subprocess/environment imports.
- Exact Git blob hashes for all six declared dependencies.

Synthetic demonstration values:

| Field | Observed value |
|---|---|
| Receipt ID | `source_capture:test-fixture` |
| Exact/canonical receipt SHA-256 | `95181ceaf4dcc025567fb8010a391ac9bd5868a0396eed3ce146ce8539850fdb` |
| Exact source SHA-256 | `c6aa9983480bd6fe313b0b12ba90aa30e44378e3a08b381829efef0bbfbe4f08` |
| Frozen manifest SHA-256 | `8972241276c998222be8377e913efc0e8ce3398d30f83dfb3891d57f47dd61c6` |
| Receipt-set SHA-256 | `da8f72c3862ad56818cdafacea8b2d653e2a7db3f044180e974a1c70b98b6fe8` |
| Synthetic existence-bound value | `2026-10-04T19:42:36Z` |
| Synthetic internal observation claim | `2026-10-04T19:42:34.100000Z` |
| Frozen manifest binding status | `UNBOUND` |
| Companion binding trust scope | `GITHUB_EXECUTION_PROVENANCE_ONLY` |

The synthetic attestation reference is a fixture URL, not evidence of a real attestation. No live #150 artifact was redownloaded or cryptographically reverified. No unchanged predecessor suite was rerun as ceremony; only fixture functions were reused to exercise this new composition.

## Dependency fingerprints

All six matched after Part A and in the focused local byte checks:

| Path | Git blob SHA |
|---|---|
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| `scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py` | `8dfd855184b172ce88235ee7de3ea33a68031b2e` |
| `scripts/forecast_bundles/dr002_github_attestation_binding_v1.py` | `215f012b79aa9e6f33aff6ad62ca7efba53a9627` |
| `tests/test_dr002_github_attestation_binding_v1.py` | `1d764c840202463e091110132521f23f34853ad0` |
| `docs/DR002_PRE2B7F1_GITHUB_ATTESTATION_BINDING_BRIDGE_2026-10-04.md` | `0ebbfe417cc460ad87ad5efcfd8535d282d2419b` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

## Required conclusions

- **YES:** a successful F1 binding can be consumed alongside exact source bytes by the existing frozen-evidence path without changing Gate 2B-1.
- **NO:** the existing frozen manifest itself does not become authenticated or bound.
- **YES:** the verified binding is preserved separately.
- **YES:** OpenF1 publisher authentication, internal clock authentication, historical availability and observation completeness remain unproven.
- **NO:** no producer, protected stable engine, live lock/outcome/revision or production caller is activated or executed by this work.
- **NO:** DR-002 / Gate 2B-7 is not activated.

No scope deviation or remaining implementation HOLD. No source request, dispatch/rerun, workflow/model/workbook/ledger/latest/history mutation, accuracy claim, Pipedream or Gmail. The next decision is independent Adviser acceptance or HOLD of this delta. Completion does not authorize merge, a successor, activation or promotion.
