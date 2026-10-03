# DR-002 Gate 2B-2A — isolated source-capture provenance pilot

DR-002 remains **PROPOSED — NOT ACTIVATED**. Gate 2B-2 is not production-active.

Starting fresh main: `0e7ab8782b266ac186a4577038e0bd0b38f72e07`.
Branch: `dr002-gate2b2a-capture-provenance-pilot-20261003`.

This PR implements the isolated capture primitive and offline tests only. No live
pilot has yet been executed by this PR. After review and merge, the next action
requires separate authorization: one manually invoked Gate 2B-2B live capture.

## Fixed scope and ownership

Session Data Processor owns this isolated pilot. Normal
`session_data_processor_loop_v1.py` behavior is unchanged. The existing processor's
weather required columns are session_key, meeting_key and date; the pilot applies
those requirements to every row, rejects duplicate/invalid rows and requires a
finite weather measurement. It does not import the processor's wall-clock-aware
analyzer or retrying JSON fetcher: those would lose exact bytes or conflate timing.
The committed Gate 2B-1 canonical JSON, hash, envelope and temporal validators are
reused unchanged. No Gate 2A or Gate 2B-1 semantic change is required.

The sole target is OpenF1 weather for Baku Practice 2:

- event_id: `2026_1295_azerbaijan_baku_baku`
- meeting_id: `1295`
- session_id: `11371`
- URI: `https://api.openf1.org/v1/weather?session_key=11371`

## Observation and persistence contract

One invocation attempts one request without application retries. Request start
is recorded separately. The transport reads the complete HTTP body as bytes;
only then is response completion sampled and used as first_observed_utc. These
are observer-clock claims, not authenticated publication times.

Exact body bytes are written without reserialization and read back. Ingestion is
sampled only after the read-back SHA-256 matches the in-memory source hash.
Raw persistence occurs before JSON parsing, retaining failed-response diagnostics
where possible. A separate canonical diagnostic representation has its own hash;
that hash never replaces source_sha256 and is not a normalization receipt.

The Gate 2B-1 source_capture envelope has no parents. event_time_utc and
publisher_time_utc remain null. Receipt identity is derived from fixed scope and
raw content hash. Identical source bytes can have the same content identity across
attempts; receipt contents, observation timestamps, receipt hash and run package
remain distinct. This ID is not proof of earliest-ever observation.

All successful receipt publication requires:
request_started_utc <= response_completed_utc = first_observed_utc <= ingested_utc
<= receipt_created_utc. A diagnostic receipt candidate is read back before the
receipt filename is published. HTTP/schema/scope/JSON/persistence/hash/time errors
produce HOLD diagnostics and no successful source_capture receipt. Existing run
packages cannot be overwritten. If diagnostic storage itself is unavailable,
the process fails rather than claiming success.

## Runtime and trust boundary

CLI output root is fixed to `_runtime/dr002_gate2b2_capture_pilot/<run_id>/`:
raw response, normalized diagnostics, capture manifest, source receipt (success
only), and pilot report. Tests inject temporary directories, clocks, transport and
filesystem operations. No latest/history/ledger/workbook output is written.

Every manifest declares:

- binding_status: `UNBOUND`
- production_authenticated: `false`
- historical_availability_proven: `false`
- dr002_activated: `false`

No production authentication exists. No external verified binding is generated.
No historical availability is proven. Clock accuracy, observer honesty, issuer
trust and durable lock authentication remain unresolved. A future live run proves
only observation of the then-current API body; older row dates cannot backdate it.
No forecast consumes these receipts. No production provenance/leakage defect is
closed by this PR. No engine execution, prediction, accuracy or promotion claim.

## Manual workflow and validation

The new workflow is workflow_dispatch only, contents: read, checkout credentials
not persisted, and uploads runtime artifacts even after HOLD. It has no schedule,
repository writes, git staging/commits/pushes or downstream/forecast invocation.
It has not been dispatched in this task. Offline tests perform no network I/O.

Commands run:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_capture_provenance_pilot_v1.py' -v
PYTHONDONTWRITEBYTECODE=1 python -c "import ast,pathlib; [ast.parse(p.read_text()) for p in [pathlib.Path('scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py'), pathlib.Path('tests/test_dr002_capture_provenance_pilot_v1.py')]]"
```

Results: **36 test methods passed**, zero failures/errors. Receipt compatibility
is exercised against the unchanged committed Gate 2B-1 validators in the new
suite. No unrelated suites or live OpenF1 pilot were run.

Exactly four additions:

1. `scripts/session_data_processor/dr002_capture_provenance_pilot_v1.py`
2. `tests/test_dr002_capture_provenance_pilot_v1.py`
3. `.github/workflows/dr002-capture-provenance-pilot.yml`
4. `docs/DR002_GATE2B2A_CAPTURE_PROVENANCE_PILOT_2026-10-03.md`

Rollback: revert this isolated PR; no production/data migration required.
Engine_2026-06-07_STABLE and canonical workbook untouched; forecast gate OFF,
promotion NOT ALLOWED. Existing CLI defects, source contamination, legacy blind
eligibility and misleading stable attribution remain open and out of scope.
