# DR-002 Gate 2B-3A — frozen evidence containment

DR-002 remains **PROPOSED — NOT ACTIVATED**. This is offline containment
infrastructure only. Starting fresh main:
`5f25e048edeb6e46a5a77e70c5c97857a59f6bb6`.
Branch: `dr002-gate2b3a-frozen-evidence-containment-20261003`.

## Purpose and existing boundary

The reviewed current producer discovers broad latest/history candidates, uses
recursive discovery and candidate priority, and assembles drivers from discovered
files. That existing path is unchanged; it is not proven to obey this contract.
No forecast producer ran in this gate. No forecast consumes the new manifest.
No engine proof or execution claim exists. No producer_execution or
engine_execution receipt is generated. No weights, gates, driver universe,
scoring, promotion, workbook, collector or production workflow changes.

## Explicit input and deterministic output

`build_frozen_evidence_manifest(request)` accepts exactly event_id, meeting_id,
allowed_session_ids and captures, each naming exactly receipt_path/content_path.
The CLI takes `--request` and writes canonical JSON to stdout; failure writes
HOLD diagnostics to stderr and returns nonzero. Paths are resolved as supplied
from cwd, without fallback or discovery. No repository writes occur.

Every input receipt must pass unchanged Gate 2B-1 envelope validation, have type
source_capture, have no parents and have consistent observation/ingestion/creation
times. Event and meeting match exactly; session belongs to the explicit allowlist.
Receipt IDs and source IDs must both be unique. Every content file is read as
exact bytes and hashed before comparison with source_sha256. One bad input rejects
the entire set. Duplicate JSON keys, nonfinite JSON, extra/trust fields and ambiguous
request identity fail closed. No revision/multi-version model is introduced.

Output wrapper:

- manifest: deterministic body with schema_version `dr002-frozen-evidence-v1`,
  scope, evidence, input_receipt_manifest_sha256 and fixed UNBOUND trust.
- frozen_evidence_manifest_sha256: SHA-256 of canonical body, outside the body.

Evidence contains source_id/source_uri, receipt_id/receipt_sha256, source_sha256,
session_id, event/publisher/observation/ingestion timestamps and logical refs.
Sessions are sorted; evidence is sorted by source_id, session_id, receipt_id.
No clock/random/UUID or input ordering contributes to the result.

### Reference semantics and relocation

Filesystem locations are not evidence identities. supplied_content_ref is
`sha256:<source_sha256>`, identifying the exact supplied bytes. capture_ref is
`receipt-sha256:<receipt_sha256>#/payload/capture_ref`, an explicit pointer to the
original capture_ref field in the bound canonical receipt. It is not the original
machine-local path and does not assert that a content-addressed store exists.
The original receipt is unchanged and its hash binds that original field.
Relocating unchanged receipt/content files cannot change the manifest hash.
Changing receipt contents (including its capture_ref) changes the receipt hash,
as it must; this is not file relocation. No absolute filesystem paths or temporary
folder names are added to the manifest body.

### Four hash meanings

1. source_sha256 binds exact source bytes, never normalized substitutes.
2. receipt_sha256 uses committed Gate 2B-1 canonical receipt hashing.
3. input_receipt_manifest_sha256 calls committed Gate 2B-1 helper: sort objects
   `{receipt_id, receipt_sha256}` by receipt_id, canonicalize, SHA-256.
4. frozen_evidence_manifest_sha256 binds the canonical frozen set body.

This is NOT Gate 2A's future forecast input_manifest_sha256. That separately
scoped forecast/product/deadline/evidence contract has not been built here.

`validate_frozen_evidence_manifest()` checks strict output fields, timestamps,
ordering, duplicates, logical references, scope, trust and both set hashes. It is
structural/internal validation, not independent proof of receipt/content bytes.
The builder performs those byte checks; no self-consistent JSON authenticates itself.

## Trust and next gate

binding_status = UNBOUND; production_authenticated = false;
historical_availability_proven = false. Freezing unbound evidence never upgrades
trust. No verified_receipt_bindings, production issuer trust, historical first
availability or cutoff eligibility is asserted. A frozen set can still contain
untrue unauthenticated claims; containment does not establish observation honesty.

Next proposed step: Gate 2B-3B shadow producer execution adapter, separately
reviewed/authorized. It has NOT begun. The current producer contamination risk and
all production integrity defects remain open. Engine_2026-06-07_STABLE untouched;
forecast gate OFF; promotion NOT ALLOWED; canonical workbook untouched;
no forecast generated; Pipedream not used.

## Validation, file scope and rollback

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_frozen_evidence_manifest_v1.py' -v
PYTHONDONTWRITEBYTECODE=1 python -c "import ast,pathlib; [ast.parse(p.read_text()) for p in [pathlib.Path('scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py'), pathlib.Path('tests/test_dr002_frozen_evidence_manifest_v1.py')]]"
```

**34 test methods passed**, zero failures/errors. Cheap syntax/import validation
passed. Synthetic fixtures only; no network, OpenF1, workflow dispatch or unrelated
suites. Gate 2B-1 helper compatibility is checked directly by the new suite.

Exactly four additions:

- scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py
- tests/test_dr002_frozen_evidence_manifest_v1.py
- docs/DR002_GATE2B2B_LIVE_CAPTURE_CHECKPOINT_2026-10-03.md
- docs/DR002_GATE2B3A_FROZEN_EVIDENCE_CONTAINMENT_2026-10-03.md

Rollback: revert this isolated PR; no migration or live caller dependency.
