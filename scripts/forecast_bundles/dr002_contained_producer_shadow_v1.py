"""Pinned current producer mechanics in disposable, explicit-input shadow only.

No CLI, discovery, production entry point or persistent output. The only disk
materialization is caller-supplied CSV bytes in a disposable temporary directory.
This is byte-identity/containment evidence, not runtime authentication.
"""
import hashlib
from pathlib import Path
import sys
import tempfile
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_forecast_integrity_receipts_v1 import canonical_json_bytes, sha256, _time as parse_utc
from dr002_frozen_evidence_manifest_v1 import build_frozen_evidence_manifest

IMPLEMENTATION = 'scripts/forecast_bundles/dr002_contained_producer_shadow_v1.py'
PRODUCER_IMPLEMENTATION = 'scripts/forecasts/produce_actual_forecast_rows_v1.py'
PRODUCER_BLOB_SHA = '05296f3e9b0aa433b2679864fef5bb7276e44627'
STATUS = 'CONTAINED_CURRENT_PRODUCER_SHADOW_ONLY_NOT_A_PRODUCTION_FORECAST'


class ShadowError(ValueError):
    """Fail closed: no successful shadow result."""


def require(ok, reason):
    if not ok:
        raise ShadowError(reason)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def load_current_producer():
    """Load only the fixed, fingerprinted implementation, into a fresh namespace.

    This is not a sandbox for arbitrary code. Only accepted pinned bytes may run;
    a future producer implementation requires a new review/fingerprint.
    """
    code_path = Path(__file__).resolve().parents[1] / 'forecasts' / 'produce_actual_forecast_rows_v1.py'
    code = code_path.read_bytes()
    require(git_blob_sha(code) == PRODUCER_BLOB_SHA, 'current_producer_fingerprint_changed')
    module = types.ModuleType('dr002_isolated_current_producer')
    module.__file__ = str(code_path)
    exec(compile(code, PRODUCER_IMPLEMENTATION, 'exec'), module.__dict__)
    return module, code


def run_contained_shadow(*, sources, event_id, meeting_id, session_id,
                         gate, lane, forecast_generation_utc, race_name='Synthetic shadow event'):
    """Return canonicalizable shadow facts; do not persist output or receipts.

    sources: explicit list of {source_name, source_id, content: bytes,
    source_sha256, optional receipt: source_capture dict}. No paths are accepted.
    Unbound receipt scope is validated if supplied; absence is openly recorded.
    """
    require(all(text(v) for v in (event_id, meeting_id, session_id, race_name)), 'missing_scope_or_name')
    parse_utc(forecast_generation_utc)
    producer, code = load_current_producer()
    require(gate in producer.GATES and lane in producer.LANES, 'invalid_gate_or_lane')
    require(isinstance(sources, list) and bool(sources), 'empty_or_malformed_frozen_sources')
    names, ids, manifest, capture_inputs, capture_bytes = set(), set(), [], [], {}
    explicit = {}
    for source in sources:
        require(isinstance(source, dict) and set(source) in (
            {'source_name', 'source_id', 'content', 'source_sha256'},
            {'source_name', 'source_id', 'content', 'source_sha256', 'receipt'}), 'malformed_source')
        name, sid, content, digest = (source[k] for k in ('source_name', 'source_id', 'content', 'source_sha256'))
        require(text(name) and name in producer.SOURCE_FILES, 'unknown_source_name')
        require(text(sid) and name not in names and sid not in ids, 'duplicate_or_ambiguous_source')
        require(isinstance(content, bytes) and bool(content) and sha256(content) == digest, 'missing_or_mismatched_exact_bytes')
        names.add(name); ids.add(sid); explicit[name] = content
        receipt = source.get('receipt')
        if 'receipt' in source:
            require(isinstance(receipt, dict) and isinstance(receipt.get('payload'), dict), 'malformed_source_receipt')
            require(receipt['payload'].get('source_id') == sid, 'source_receipt_identity_mismatch')
            capture_inputs.append(dict(receipt_path='receipt:' + name, content_path='content:' + name))
            capture_bytes['receipt:' + name] = canonical_json_bytes(receipt)
            capture_bytes['content:' + name] = content
        manifest.append(dict(source_name=name, source_id=sid, source_sha256=digest,
                             receipt_id=receipt.get('receipt_id') if receipt else None,
                             provenance_status='UNBOUND_CAPTURE_SUPPLIED' if receipt else 'NO_CAPTURE_RECEIPT'))
    frozen = None
    if capture_inputs:
        frozen = build_frozen_evidence_manifest(dict(event_id=event_id, meeting_id=meeting_id,
            allowed_session_ids=[session_id], captures=capture_inputs), read_bytes=capture_bytes.__getitem__)
    with tempfile.TemporaryDirectory(prefix='dr002-contained-shadow-') as directory:
        root = Path(directory)
        paths = {}
        counts = {name: 0 for name in producer.SOURCE_FILES}
        for name in sorted(explicit):
            path = root / (name + '.csv')
            path.write_bytes(explicit[name])
            require(path.read_bytes() == explicit[name], 'materialized_bytes_readback_mismatch')
            paths[name] = path
            parsed = producer.read_csv(path)
            counts[name] = len(parsed)
            # When scope-bearing columns exist, enforce their declared scope too.
            for row in parsed:
                for field, expected in (('event_id', event_id), ('meeting_key', meeting_id),
                                        ('meeting_id', meeting_id), ('session_key', session_id), ('session_id', session_id)):
                    if field in row:
                        require(str(row[field]).strip() == expected, 'csv_row_scope_mismatch')
        drivers = producer.build_driver_universe(paths)
        grid = producer.starting_grid_map(paths)
        require(bool(drivers), 'no_explicit_driver_universe')
        readiness = producer.source_readiness_score(counts, gate)
        original_clock = producer.utc_now
        try:
            producer.utc_now = lambda: forecast_generation_utc
            rows = producer.produce_rows(event_id, race_name, gate, lane, drivers, grid, counts, paths)
        finally:
            producer.utc_now = original_clock
        require(bool(rows) and all(r['forecast_generation_utc'] == forecast_generation_utc for r in rows), 'unexpected_row_generation')
    for entry in manifest:
        entry['row_count'] = counts[entry['source_name']]
    body = dict(schema_version='dr002-contained-producer-shadow-v1', status=STATUS,
                adapter_implementation=IMPLEMENTATION, producer_implementation=PRODUCER_IMPLEMENTATION,
                producer_git_blob_sha=git_blob_sha(code), producer_code_sha256=sha256(code),
                input_sources=sorted(manifest, key=lambda e:e['source_name']),
                absent_source_names=sorted(set(producer.SOURCE_FILES) - names), source_counts=counts,
                event_id=event_id, meeting_id=meeting_id, session_id=session_id, gate=gate, lane=lane,
                forecast_generation_utc=forecast_generation_utc, generated_row_count=len(rows),
                driver_universe=drivers, starting_grid={str(k):v for k,v in sorted(grid.items())},
                source_readiness_score=readiness, rows=rows, frozen_receipt_evidence=frozen,
                receipt_bound_source_names=sorted(s['source_name'] for s in sources if 'receipt' in s),
                containment=dict(explicit_bytes_only=True, discovery_bypassed=True,
                                 production_entry_point_bypassed=True, production_writes_bypassed=True,
                                 temporary_inputs_disposed=True),
                engine_implementation=None, engine_execution='NOT_PROVEN', stable_engine_executed=False,
                production_forecast_generated=False, blind_validation_eligible=False,
                trust=dict(binding_status='UNBOUND', production_authenticated=False,
                           historical_availability_proven=False, dr002_activated=False),
                claim_limit='Stable lane/config label != stable engine execution proof. Internal rows are unchanged generic-producer shadow rows, not a production forecast.')
    return dict(result=body, canonical_shadow_output_sha256=sha256(canonical_json_bytes(body)))
