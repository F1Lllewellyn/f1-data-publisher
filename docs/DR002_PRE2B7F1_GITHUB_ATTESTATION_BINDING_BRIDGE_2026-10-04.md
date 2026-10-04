# DR-002 pre-2B-7F1 — GitHub attestation to Gate 2B-1 receipt-binding bridge

Work order: `F1-WO-DR002-PRE2B7F1-001` / Issue #152.  
Status: implementation complete, pending independent Science / Architecture Adviser review.  
DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate OFF. Promotion NOT ALLOWED.

## Purpose

This checkpoint adds an isolated, deterministic, offline adapter that projects an **externally cryptographically verified GitHub attestation result** into the unchanged Gate 2B-1 `verified_receipt_bindings` trust interface.

The adapter does not perform cryptographic verification and does not authenticate the external verifier provider. That remains an explicit caller trust boundary, consistent with Gate 2B-1's existing external-binding design.

No production caller is activated.

## Exact delta

Added exactly:

- `scripts/forecast_bundles/dr002_github_attestation_binding_v1.py`
- `tests/test_dr002_github_attestation_binding_v1.py`
- `docs/DR002_PRE2B7F1_GITHUB_ATTESTATION_BINDING_BRIDGE_2026-10-04.md`

No existing Gate 2A, Gate 2B-1, capture, producer, model, workflow, protected stable-engine, workbook, ledger, `latest/**`, `history/**`, promotion or forecast-gate file is changed.

Accepted PR #151 was already merged unchanged as `966de2157a71c9efebb63d3b8a99ad93184daec0`.

## Dependency state

Relevant dependency blobs at implementation:

- Gate 2B-1 verifier/helper: `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae`
- capture implementation: `b9b1f9acc1be30d5b7cdf42424853e3d652b9466`
- capture workflow: `883fcbc1a00ec9ae1dd6dd40423a03af05ae1fe3`
- pre-2B-7E1 checkpoint: `f37e72326864f4dcb485025b1a85ae20c33bb7f5`
- pre-2B-7E2 checkpoint: `e96c7c37a6dbbd57818f49e117f44b90139d97e0`
- handoff contract after work-credit repair: `85ce44807ef159b5ba5d3bfd543ea1f945097f77`

## Bridge semantics

The adapter requires explicit:

- exact receipt bytes;
- saved Sigstore attestation bundle bytes;
- externally supplied verification result marked `VERIFIED` from the approved GitHub CLI attestation-verifier boundary;
- expected GitHub repository/workflow/ref/source and signer commit/runner/trigger/run-attempt identity;
- durable GitHub attestation URL.

A successful bridge requires the receipt to be a valid parentless Gate 2B-1 `source_capture` receipt and, critically, requires:

`exact receipt bytes == Gate 2B-1 canonical_json_bytes(receipt)`

The attested subject must be exactly `source_capture_receipt.json`, its SHA-256 must equal the exact receipt-file SHA-256, and therefore that exact-file hash must equal unchanged Gate 2B-1 `receipt_sha256(receipt)`.

Noncanonical receipt bytes fail closed. The adapter never silently reserializes an attested file.

The external verifier's returned bundle must be JSON-equivalent to the exact saved bundle bytes, and the saved bundle's decoded DSSE statement must exactly equal the statement returned by the external verified-result boundary. The verified result must also match the expected GitHub repository, signer workflow, `refs/heads/main`, source/signer commit, GitHub-hosted runner, `workflow_dispatch` trigger, exact run/attempt URI and GitHub OIDC issuer.

At least one externally verified Tlog timestamp is required. The earliest verified Tlog timestamp is used only as an upper bound proving the exact attested receipt bytes existed **no later than** that time. It does not authenticate the receipt's internal `first_observed_utc`.

## Successful output

Success returns:

- `status = VERIFIED_GITHUB_PROVENANCE_BINDING`;
- exactly one `verified_receipt_bindings` entry in the unchanged Gate 2B-1 shape;
- receipt ID;
- canonical and exact receipt SHA-256 values;
- `attested_receipt_existed_by_utc`;
- the internal `first_observed_utc` claim;
- `trust_scope = GITHUB_EXECUTION_PROVENANCE_ONLY`.

The following remain false:

- `first_observed_clock_authenticated`
- `publisher_authenticated`
- `production_authenticated`
- `historical_availability_proven`
- `observation_completeness_proven`
- `dr002_activated`

No new DR-002 scientific receipt is created and the source-capture receipt is not mutated.

## Focused validation

Command:

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_github_attestation_binding_v1.py' -v`

Result: **26 tests PASS; 0 failures/errors**.

Coverage includes:

- canonical success and unchanged Gate 2B-1 binding-shape acceptance;
- noncanonical/malformed/wrong-type/parented receipt HOLD;
- missing/failed verifier result HOLD;
- subject count/name/hash mismatch HOLD;
- statement/predicate/build-type mismatch HOLD;
- repository/workflow/ref/source and signer commit/runner/trigger/run-attempt/OIDC mismatch HOLD;
- missing or too-early Tlog timestamp HOLD;
- malformed durable verification reference HOLD;
- exact/canonical equality proved rather than assumed;
- false trust ceilings retained;
- deterministic/pure/offline implementation checks;
- exact saved-bundle equality with the external verifier result;
- bundle statement must match the externally verified statement.

No workflow, OpenF1 request, cryptographic verifier, or unrelated suite was executed by the focused test run.

## Accepted #150 live compatibility projection

A separate read-only local compatibility check used the **already accepted exact #150 artifact bytes** from artifact `11312353979`; it did not redownload a source, dispatch a workflow, or rerun cryptographic verification.

Inputs included exact:

- `source_capture_receipt.json` bytes;
- `github_attestation.bundle.json` bytes;
- previously accepted external GitHub CLI verification facts for attestation `52636060`.

Output:

```json
{
  "status": "VERIFIED_GITHUB_PROVENANCE_BINDING",
  "verified_receipt_bindings": {
    "source_capture:c4564601dd7a9c75648a0fc6594088f2339ed404d5cce721658f50de3190929b": {
      "receipt_sha256": "3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69",
      "verification_ref": "https://github.com/F1Lllewellyn/f1-data-publisher/attestations/52636060"
    }
  },
  "canonical_receipt_sha256": "3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69",
  "exact_receipt_sha256": "3d928c6f1cbf89ee24e15594a8b74573877591ab0be4b128ebde1ceee558ce69",
  "attested_receipt_existed_by_utc": "2026-10-04T19:42:36Z",
  "internal_first_observed_utc": "2026-10-04T19:42:34.866980Z",
  "trust_scope": "GITHUB_EXECUTION_PROVENANCE_ONLY",
  "first_observed_clock_authenticated": false,
  "publisher_authenticated": false,
  "production_authenticated": false,
  "historical_availability_proven": false,
  "observation_completeness_proven": false,
  "dr002_activated": false
}
```

The emitted binding entry was accepted by unchanged Gate 2B-1 external-binding semantics.

## Required conclusions

1. **Can accepted GitHub-attested canonical source receipt bytes be mapped into existing Gate 2B-1 `verified_receipt_bindings` without changing Gate 2B-1? YES.**
2. **Is exact-byte == canonical-byte equality required for this v1 bridge? YES.**
3. **Does the binding authenticate the OpenF1 publisher? NO.**
4. **Does it authenticate the internal `first_observed_utc` clock? NO.**
5. **Does verified Tlog time prove the exact receipt bytes existed no later than that time? YES, conditional on the externally verified attestation boundary.**
6. **Does it prove earliest or historical availability? NO.**
7. **Does it prove observation completeness? NO.**
8. **Is a new scientific receipt created? NO.**
9. **Is any production caller activated? NO.**
10. **Is DR-002 or Gate 2B-7 activated? NO.**
11. **#150 compatibility result:** PASS; exact accepted receipt projects to one Gate 2B-1 binding and the verified existence upper bound is `2026-10-04T19:42:36Z`.
12. **Next if accepted:** choose the smallest production-safe consumer of this verified binding or address the next remaining proof gap under a separate authorized work order. Acceptance does not automatically authorize Gate 2B-7.

## Trust ceiling

This bridge establishes a mechanically usable relationship between already verified GitHub execution provenance and the existing Gate 2B-1 caller-supplied binding interface. It does not upgrade source-publisher trust, clock trust, historical availability, completeness, stable-engine execution, blind predictive eligibility, live lock/outcome/revision proof, production readiness or predictive accuracy.
