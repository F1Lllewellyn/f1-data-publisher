# DR-002 pre-2B-7E1 — GitHub-attested source-capture capability

Work order: [F1-WO-DR002-PRE2B7E1-001 / Issue #148](https://github.com/F1Lllewellyn/f1-data-publisher/issues/148).
Recorded: 2026-10-04; the 2026-10-03 filename is the authorized checkpoint identifier.
Status: capability implemented and tested offline; pending independent Adviser review.
DR-002 remains **PROPOSED — NOT ACTIVATED**. Gate 2B-7 enforcement has not begun.

## Accepted predecessor and observed baseline

PR #147 was already merged before this execution began, at merge commit
`d0566e3a42e54f2b92ac8fd9b9251c856698b25a` (2026-10-04T11:18:36Z).
Fresh API inspection verified its reviewed head
`7d6f318ba95e0e45873b7d4ca4e96f90a7ca143b`, one added documentation file,
228 additions / 0 deletions, and expected landed blob
`d07a0ff228227378af863313a487e6d64c21fd50`.
Part A was therefore already satisfied; this execution did not perform another merge.
The accepted live synthetic shadow and its cryptographic verification were not rerun.

Observed starting main: `30498f9355f49b816729a204809e64cbae2e27ba`.
Open issue enumeration returned exactly one authorized issue, #148, with no comments.
The suggested branch already contained partial workflow-only commit
`0f3fc83edfd62005a5a7bb505c9b1e7030fc2d15`, created at 2026-10-04T11:19:10Z
from PR #147's merge. No Work Result PR existed for it at inspection.
This execution completes that branch with an ordinary descendant commit,
preserving the partial work's history. It strengthens packaging checks and uses
the unchanged canonical receipt hash helper instead of conflating that hash
with the exact file-byte attestation digest. The branch's earlier baseline
does not require replaying unrelated scheduled generated-artifact movement.
All declared relevant dependency Git blobs matched at this main commit:

| Path | Git blob |
|---|---|
| `.github/workflows/dr002-capture-provenance-pilot.yml` | `b37a3d1562be9b1dbd7842c6b719b09865fa5fc7` |
| `scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py` | `b9b1f9acc1be30d5b7cdf42424853e3d652b9466` |
| `tests/test_dr002_capture_provenance_pilot_v1.py` | `fa11b27c7e32638985944f404815a1a7fe04e4a2` |
| `docs/DR002_GATE2B2A_CAPTURE_PROVENANCE_PILOT_2026-10-03.md` | `675f6884b631dbc5cd158195ea41005b3252e741` |
| `docs/DR002_GATE2B2B_LIVE_CAPTURE_CHECKPOINT_2026-10-03.md` | `ba08ea34754af1a3d09c2a1751618474bbf7a954` |
| `docs/DR002_PRE2B7D2_LIVE_GITHUB_ATTESTED_SHADOW_2026-10-03.md` | `d07a0ff228227378af863313a487e6d64c21fd50` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `91dfffd80635f643a2f605f75422c6311e93a9c6` |

Additional required helper: `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py`
has Git blob `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae`, identical to the accepted
Gate 2B-2 live capture head `5f25e048edeb6e46a5a77e70c5c97857a59f6bb6`.
Fetched file bytes were independently Git-blob hashed locally. The helper,
capture script, existing tests and accepted checkpoints remain unchanged.

## Exact implementation delta

Only three paths:

1. MODIFY `.github/workflows/dr002-capture-provenance-pilot.yml`.
2. ADD `tests/test_dr002_capture_attestation_v1.py`.
3. ADD this checkpoint.

The workflow remains workflow_dispatch-only, with one unchanged capture-script
invocation and one fixed OpenF1 weather request, no application retry, no extra
source request, no repository commit/push, and runtime-only artifact output.
The job is restricted to `refs/heads/main`; checkout pins `${{ github.sha }}`
and retains `persist-credentials: false`.

Permissions are exactly `contents: read`, `id-token: write`, `attestations: write`.
There is no artifact-metadata permission or other write permission.
First-party `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6` (v4.2.2)
uses file-subject mode with both `push-to-registry: false` and
`create-storage-record: false`. Its action.yml at that immutable commit was
inspected for these inputs and the bundle-path / attestation-id / attestation-url outputs.

## Subject and packaging consistency

The sole attestation subject, after successful capture, is:

```text
_runtime/dr002_gate2b2_capture_pilot/gha-${{ github.run_id }}-${{ github.run_attempt }}/source_capture_receipt.json
```

The capture CLI returns nonzero on HOLD and publishes the receipt last on success.
The attestation and packaging steps retain implicit success() conditions.
No auxiliary step reconstructs, rewrites or modifies receipt bytes.

Inline packaging code reuses the unchanged Gate 2B-1 structural, temporal,
canonical JSON and receipt hash helpers. Before metadata publication it checks:

- CAPTURED_UNBOUND status and implementation Git SHA equal to the run head;
- fixed source URI, source identity, event/meeting/session scope, parentless
  source_capture type, implementation and run-specific receipt/raw paths;
- canonical receipt_sha256 against the capture manifest, independently of the
  exact receipt byte digest used for attestation;
- exact raw response bytes against both receipt.payload.source_sha256 and
  capture_manifest.source_sha256, plus byte count and read-back claims;
- observation/ingestion/receipt timestamps across receipt and manifest and the
  accepted deterministic observation-specific receipt identity;
- UNBOUND / false trust flags and absent publisher/event time claims;
- decoded DSSE subject count, filename and exact receipt SHA-256;
- required action outputs and repository/workflow/main-ref identity.

The action bundle-path bytes are copied unchanged into
`github_attestation.bundle.json` and read back. Factual
`github_attestation_metadata.json` records schema version, attestation ID/URL,
exact subject path/hash, repository, workflow path/name/ref, head, run/attempt,
receipt ID, source URI/hash, scope, capture_ref, first observation and ingestion,
and unchanged UNBOUND / false trust ceilings. New output files use exclusive
creation; existing evidence cannot be silently overwritten. The auxiliary code
does not read, persist or log OIDC/GitHub token values.

These checks establish packaging consistency only. Decoding unsigned DSSE JSON
is not signature verification. No external verified_receipt_bindings is created.
The original source_capture receipt is the only scientific receipt in the package;
the bundle and auxiliary metadata are not additional DR-002 receipts.

Any attestation or packaging error fails the job. Existing always-upload retains
diagnostics without continue-on-error, error suppression or a success conversion.

## Focused offline validation

Executed:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_capture_attestation_v1.py' -v
```

Result: **38 tests PASS**, zero failures/errors. Separate PyYAML BaseLoader parsing
checked the six-step structure, triggers, exact permissions, main restriction,
checkout, attestation inputs and success/always conditions. Both inline Python
and test syntax passed AST parsing.

Tests execute the actual inline packaging code against temporary synthetic
packages from the unchanged capture function with injected transport and clocks.
Socket connection is blocked during packaging tests. Mock bundles are explicitly
unsigned; they test exact-byte handling and rejection, not cryptography.
Cases include altered raw bytes, receipt/manifest hash disagreement, HOLD status,
wrong head/scope/URI/path/observation/receipt identity, invalid and missing bundles,
wrong DSSE digest/name/subject count, unsupported trust flags (including non-boolean
false substitutes), output mismatches, persistence failures and overwrite rejection.
Positive cases prove exact bundle copying, receipt immutability, exact metadata,
token non-persistence and canonical versus exact-byte hashing separation.
Static checks cover single unchanged invocation, immutable action pin, no added
source request/retry/downstream invocation, failure propagation and unchanged
accepted dependency bytes.

No unrelated or accepted predecessor test suite was rerun. No workflow was
dispatched, no live OpenF1 request occurred, and no new signature verification
was performed. No CI success or live attestation success is claimed.

## Required conclusions

| Question | Answer |
|---|---|
| GitHub attestation capability installed on manual source capture? | YES, in this proposed PR; not yet merged or exercised live. |
| Subject exactly source_capture_receipt.json? | YES, the exact run-specific file only. |
| Receipt exact bytes bind source URI/hash/observation/scope? | YES, structurally/hash-wise; existing receipt semantics retained. |
| Bundle and factual metadata preserved? | YES, implemented and verified with offline fixtures; no new live bundle exists. |
| Workflow still one request, manual-only and production-inactive? | YES. |
| New live source capture in this work order? | NO. |
| OpenF1 publisher authenticity proven? | NO. |
| Earliest/historical availability proven? | NO. |
| Observation completeness proven? | NO. |
| Stable engine / blind / lock / outcome / revision proven? | NO. |
| DR-002 or Gate 2B-7 activated? | NO. |
| Next if accepted? | Separately authorize exactly one manual attested live source capture and independent artifact/Sigstore verification. |

## Trust ceiling and review boundary

A separately authorized future live run, if independently cryptographically
verified, may associate exact source_capture_receipt bytes with verified GitHub
repository/workflow/ref/head provenance. Those bytes hash-bind the independently
inspected raw response. GitHub transparency evidence may supply a verified
signing/logging time after capture. It does not authenticate the OpenF1 publisher's
payload cryptographically or establish the truth of every workflow-authored fact.

Earliest-ever availability, historical availability before first_observed_utc,
global observation completeness, protected stable-engine execution, blind
eligibility, production lock/outcome/revision and production readiness remain unproven.
binding_status=UNBOUND; production_authenticated=false;
historical_availability_proven=false; dr002_activated=false.

No capture-script, receipt-contract, producer, model, production workflow,
orchestrator, stable-engine, workbook or ledger modification. No new receipt type,
live lock/outcome/revision proof, Pipedream or Gmail use. Forecast gate remains OFF;
promotion remains NOT ALLOWED. Completion is not Adviser acceptance or activation.
This Part B PR must remain unmerged. Rollback: revert this isolated three-file
change; no production or data migration is involved.
