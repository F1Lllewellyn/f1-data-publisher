# DR-002 pre-2B-7K3 — OpenF1 live-stream capture shadow capability

Work order: [F1-WO-DR002-PRE2B7K3-001 / Issue #203](https://github.com/F1Lllewellyn/f1-data-publisher/issues/203)  
Recorded: 2026-10-07  
Result: CAPABILITY COMPLETED — NOT DISPATCHED; focused offline tests PASS.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate remains OFF. Promotion remains NOT ALLOWED.

## Capability boundary

K3 adds a manual-only GitHub Actions shadow capability for a future separately authorized run. It can obtain a short-lived OpenF1 token using backend-only secrets, connect to the fixed TLS MQTT endpoint, capture exact payload bytes from one bounded topic, compose them through the accepted K2 stream-version contract, produce a run-scoped execution package, and attest the exact successful manifest.

No workflow was dispatched. No credentials or tokens were accessed. No OpenF1 connection or live capture occurred.

OpenF1 remains an unofficial F1 data provider. Authentication to its API or broker does not establish FIA/F1 official-source authority or cryptographic publisher authenticity for any message.

## Manual workflow controls

`.github/workflows/dr002-openf1-stream-capture-shadow.yml` has only `workflow_dispatch`, runs only when `github.ref == 'refs/heads/main'`, and uses a GitHub-hosted runner. Permissions are exactly:

```yaml
contents: read
id-token: write
attestations: write
```

Checkout disables persisted credentials. Checkout, Python setup, attestation, and artifact upload actions are pinned to immutable commit SHAs. The workflow has no repository write, push, commit, production dispatch, stable-engine execution, workbook/latest/history/ledger write, Pipedream, or Gmail path.

The capability consumes only these GitHub Actions secrets:

- `OPENF1_USERNAME`
- `OPENF1_PASSWORD`

Either missing value fails closed. Neither credential nor the access token is logged, serialized, placed in command-line arguments, or written into runtime evidence.

## Credential and connection handling

Token acquisition is fixed to an HTTPS `POST` at `https://api.openf1.org/token` with `application/x-www-form-urlencoded` username/password data and a default certificate-verifying TLS context. Only the access token and optional declared expiry seconds are parsed. Network, HTTP, and response errors are converted to fixed sanitized reason codes without response bodies, headers, credentials, or tokens.

The access token stays in process memory and is used only as the MQTT password. MQTT uses:

| Field | Fixed value |
|---|---|
| Broker | `mqtt.openf1.org` |
| Port | `8883` |
| TLS | Required with default certificate verification |
| Client username | `f1-data-publisher-shadow` |
| Topic | `v1/weather` |
| Wildcards | None |
| Automatic reconnect | Disabled |
| Maximum window | 180 seconds |
| Maximum messages | 500 |

The capture stops when either bound is reached. Zero messages, connection/auth/subscription failure, malformed bytes, duplicate `_id`, or any K2 `HOLD` produces a capture `HOLD`. Malformed payloads are preserved and assessed rather than silently dropped.

## Exact-byte K2 composition

For every observed MQTT message the capability preserves:

- the exact topic;
- caller/runtime receive-order index;
- exact raw bytes in `messages/message-NNNNNN.bin`; and
- SHA-256 of those exact bytes.

Those same topic/order/byte values are passed to the unchanged K2 `assess_openf1_stream_version_evidence` contract. Shadow success requires `OPENF1_STREAM_VERSION_EVIDENCE_VALIDATED`. K1 is omitted: no schedule coverage is required or fabricated for this continuous-stream pilot.

Runner capture timestamps are recorded only as unauthenticated runtime facts. They are not interpreted as publisher event time or publisher availability.

## Runtime evidence and manifest

A future authorized run writes under:

```text
_runtime/dr002_pre2b7k_openf1_stream_capture_shadow/gha-<run_id>-<attempt>/
```

The package contains:

- `capture_execution_manifest.json`;
- `stream_version_evidence.json`;
- `capture_report.md`;
- deterministic exact payload files under `messages/`; and
- after successful future attestation only, unchanged `github_attestation.bundle.json` and factual `github_attestation_metadata.json`.

The manifest binds exact repository, workflow path/name/ref, branch ref, implementation head, run ID/attempt, provider, broker, port, topic, capture bounds, connection outcome, non-secret declared token expiry, message count, K2 result SHA-256, every raw message path/topic/order/SHA-256, observed `_id` range, receive-order monotonicity, and numeric-gap fact.

## Future attestation boundary

The pinned GitHub attestation action targets exactly the successful `capture_execution_manifest.json`. The preservation step checks that the action-produced bundle has exactly one subject with the manifest's exact SHA-256, then stores the bundle bytes unchanged and writes separate factual metadata.

Local DSSE inspection is consistency only. Independent cryptographic verification and any live-evidence acceptance require a separate authorized work order. A future successful GitHub attestation may establish GitHub execution provenance and an upper bound on existence of exact manifest bytes; it cannot authenticate OpenF1 message truth, completeness, or the internal receive clock.

## Immutable trust ceiling

Every capability/runtime manifest keeps these values false:

```text
openf1_message_publisher_authenticated
openf1_official_f1_source
observation_clock_authenticated
publisher_revision_completeness_proven
global_observation_completeness_proven
message_loss_ruled_out
historical_availability_proven
production_revision_tracking_proven
full_gate2b1_chain_verified
stable_engine_execution_proven
blind_validation_eligible
production_forecast_locked
production_outcome_boundary_proven
dr002_activated
promotion_allowed
```

Caller attempts to assert an unsupported trust field true fail closed.

## Focused verification

All tests used injected synthetic token/MQTT transports or mocked HTTPS responses. No real OpenF1 call occurred.

```text
python3 -m py_compile \
  scripts/forecast_bundles/dr002_openf1_stream_capture_shadow_v1.py \
  tests/test_dr002_openf1_stream_capture_shadow_v1.py

python3 -c "from pathlib import Path; import yaml; yaml.safe_load(Path('.github/workflows/dr002-openf1-stream-capture-shadow.yml').read_text())"

python3 -m unittest -v tests/test_dr002_openf1_stream_capture_shadow_v1.py

Ran 27 tests
OK
```

The suite proves the exact constants, manual/main-only workflow, least permissions, immutable action pins, secret handling, fail-closed credential behavior, fixed token request, sanitized errors, TLS verification, bounded non-reconnecting MQTT behavior, single non-wildcard topic, zero/malformed/duplicate/K2 HOLD handling, exact byte preservation and hashing, successful unchanged-K2 composition, exact manifest/K2 bindings, absence of fabricated K1 coverage, workflow identity, immutable trust ceilings, assertion rejection, exact future attestation subject, prohibited-path absence, offline testing, and unchanged dependencies.

## Accepted dependency pins

| Path | Git blob | Result |
|---|---|---|
| `scripts/forecast_bundles/dr002_openf1_stream_version_evidence_v1.py` | `503f422ca511eff56544a4d66b312c9fbc501dbe` | PASS |
| `tests/test_dr002_openf1_stream_version_evidence_v1.py` | `c0a1a9138e0aa524167b840cc1de136ecb8284d6` | PASS |
| `docs/DR002_PRE2B7K2_OPENF1_STREAM_VERSION_EVIDENCE_CONTRACT_2026-10-07.md` | `49b125855db50c04c628c6c734ef8c94c3701115` | PASS |
| `scripts/forecast_bundles/dr002_observer_coverage_contract_v1.py` | `e0794e3c901b70a636b5d552ffd673576aeea412` | PASS |
| `docs/DR002_PRE2B7K1_OBSERVER_COVERAGE_COMPLETENESS_CONTRACT_2026-10-07.md` | `63d5e579ed7c95a74e0fdf878bb37c366b90c9e3` | PASS |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` | PASS |

## Claim ceiling and repository delta

K3 proves only that a credential-safe, bounded, manual-only capability exists for a future separately authorized OpenF1 live-stream shadow capture, exact-byte K2 composition, and GitHub attestation packaging.

K3 does not prove a live connection or run, credential/subscription availability, real capture, official-source authority, publisher authenticity, authenticated receive time, absence of message loss, publisher/global completeness, production tracking/enforcement, stable-engine execution, blind eligibility, accuracy, activation, or promotion.

This Work Result adds exactly:

- `.github/workflows/dr002-openf1-stream-capture-shadow.yml`;
- `scripts/forecast_bundles/dr002_openf1_stream_capture_shadow_v1.py`;
- `tests/test_dr002_openf1_stream_capture_shadow_v1.py`; and
- `docs/DR002_PRE2B7K3_OPENF1_LIVE_STREAM_CAPTURE_SHADOW_CAPABILITY_2026-10-07.md`.

No existing file changed. No workflow was dispatched.
