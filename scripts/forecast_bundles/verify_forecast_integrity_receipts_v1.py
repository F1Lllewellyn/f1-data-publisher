"""Offline DR-002 receipt/graph verifier; no I/O, clock or production caller.

External bindings are a TRUST INTERFACE, not authenticated by this module. The
caller must obtain them independently; a receipt cannot bind or trust itself.
Synthetic fixtures establish deterministic behavior only, not capture honesty,
production authentication, policy approval or real engine execution.
"""
from datetime import datetime
import hashlib
import json
import re

VERSION = 'dr002-receipt-v1'
SCOPE = ('event_id', 'meeting_id', 'session_id')
PRODUCT = ('product_id', 'forecast_id', 'gate', 'lane_name')
MANIFEST_KEYS = ('forecast_id', 'product_id', 'product_contract_id', 'gate', 'lane_name',
                 'event_id', 'meeting_id', 'session_id', 'allowed_session_ids',
                 'evidence_cutoff_utc', 'forecast_deadline_utc', 'mandatory_source_ids',
                 'revision_policy', 'evidence')
PRODUCER_KEYS = ('implementation', 'git_commit', 'code_sha256', 'execution_id',
                 'input_manifest_sha256', 'forecast_payload_sha256', 'engine_implementation')
# Primitive field specifications also generate the committed JSON Schema.
EXECUTION = dict(implementation='text', git_commit='commit', code_sha256='hash', execution_id='text')
PAYLOADS = {
    'source_capture': dict(source_id='text', source_uri='text', source_sha256='hash',
        event_time_utc='nullable_time', publisher_time_utc='nullable_time',
        first_observed_utc='time', ingested_utc='time', capture_ref='text', implementation='text'),
    'engine_execution': dict(engine_implementation='text', engine_execution_id='text',
        engine_code_sha256='hash', repository_backed='boolean', git_commit='nullable_commit',
        producer_execution_id='text', input_manifest_sha256='hash', input_receipt_manifest_sha256='hash',
        result_sha256='hash', completed_utc='time'),
    'producer_execution': dict(EXECUTION, forecast_generation_utc='time', input_manifest_sha256='hash',
        input_receipt_manifest_sha256='hash', forecast_payload_sha256='hash',
        engine_implementation='nullable_text', engine_receipt_id='nullable_text', engine_result_sha256='nullable_hash'),
    'normalization': dict(EXECUTION, input_payload_sha256='hash', output_payload_sha256='hash', completed_utc='time'),
    'forecast_lock': dict(forecast_payload_sha256='hash', stored_payload_sha256='hash',
        lock_utc='time', storage_ref='text'),
    'outcome_boundary': dict(product_contract_id='text', boundary_policy_ref='text',
        outcome_availability_boundary_utc='time', source_id='text', evidence_sha256='hash'),
    'revision': dict(revision_id='text', source_id='text', source_sha256='hash', first_observed_utc='time'),
}
ENVELOPE = {'schema_version', 'receipt_id', 'receipt_type', 'receipt_created_utc',
            'scope', 'parent_receipt_ids', 'payload'}


class ReceiptError(ValueError):
    def __init__(self, code, malformed=False):
        super().__init__(code)
        self.code, self.malformed = code, malformed


def _require(ok, code, malformed=False):
    if not ok:
        raise ReceiptError(code, malformed)


def canonical_json_bytes(value):
    """Sorted compact ASCII JSON, finite numbers only; identical to Gate 2A encoding."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False,
                      ensure_ascii=True).encode('utf-8')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def receipt_sha256(receipt):
    return sha256(canonical_json_bytes(receipt))


def input_receipt_manifest_sha256(receipts):
    """Distinct from Gate 2A's input hash: bind exact source receipt IDs AND contents."""
    manifest = sorted(({'receipt_id': r['receipt_id'], 'receipt_sha256': receipt_sha256(r)}
                       for r in receipts), key=lambda x: x['receipt_id'])
    return sha256(canonical_json_bytes(manifest))


def _time(value):
    _require(isinstance(value, str) and re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value), 'malformed_utc', True)
    return datetime.fromisoformat(value[:-1] + '+00:00')


def _valid(value, kind):
    if kind.startswith('nullable_'):
        return value is None or _valid(value, kind[len('nullable_'):])
    if kind == 'text':
        return isinstance(value, str) and bool(value.strip())
    if kind == 'boolean':
        return isinstance(value, bool)
    if kind in ('hash', 'commit'):
        return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{%d}' % (64 if kind == 'hash' else 40), value) is not None
    if kind == 'time':
        _time(value)
        return True
    return False


def _strings(value):
    return isinstance(value, list) and all(_valid(v, 'text') for v in value) and len(value) == len(set(value))


def validate_receipt_envelope(receipt):
    """Strict structural checks; does not establish trust. Raises ReceiptError."""
    _require(isinstance(receipt, dict) and set(receipt) == ENVELOPE, 'malformed_envelope', True)
    _require(receipt['schema_version'] == VERSION, 'unsupported_version', True)
    kind = receipt['receipt_type']
    _require(isinstance(kind, str) and kind in PAYLOADS, 'unknown_receipt_type', True)
    _require(_valid(receipt['receipt_id'], 'text'), 'missing_receipt_id', True)
    _time(receipt['receipt_created_utc'])
    _require(_strings(receipt['parent_receipt_ids']), 'duplicate_or_malformed_parent', True)
    fields = SCOPE if kind == 'source_capture' else SCOPE + PRODUCT
    scope = receipt['scope']
    _require(isinstance(scope, dict) and set(scope) == set(fields)
             and all(_valid(v, 'text') for v in scope.values()), 'malformed_scope', True)
    payload = receipt['payload']
    _require(isinstance(payload, dict) and set(payload) == set(PAYLOADS[kind]), 'malformed_payload', True)
    for name, spec in PAYLOADS[kind].items():
        _require(_valid(payload[name], spec), 'malformed_' + name, True)
    return True


def _external_binding(receipt, bindings):
    binding = bindings.get(receipt['receipt_id'])
    _require(isinstance(binding, dict) and set(binding) == {'receipt_sha256', 'verification_ref'},
             'missing_or_malformed_verified_binding')
    _require(_valid(binding['receipt_sha256'], 'hash') and _valid(binding['verification_ref'], 'text'),
             'malformed_verified_binding')
    _require(binding['receipt_sha256'] == receipt_sha256(receipt), 'receipt_binding_hash_mismatch')
    return binding


def verify_content_bindings(receipt, objects):
    """Validate supplied payload/code bytes; receipt-parent hash is checked against graph."""
    for name, digest in receipt['payload'].items():
        if name.endswith('sha256') and digest is not None and name != 'input_receipt_manifest_sha256':
            data = objects.get(digest)
            _require(isinstance(data, bytes), 'missing_content_' + name)
            _require(sha256(data) == digest, 'content_hash_mismatch_' + name)
    return True


def verify_scope_bindings(receipt, forecast):
    scope = receipt['scope']
    for name in ('event_id', 'meeting_id'):
        _require(scope[name] == forecast[name], 'scope_mismatch_' + name)
    allowed = forecast['allowed_session_ids']
    allowed = [forecast['session_id']] if allowed is None else allowed
    _require(_strings(allowed) and bool(allowed), 'ambiguous_allowed_sessions')
    # Supporting boundary/revision captures can be target-session evidence;
    # consumed captures are separately restricted to the exact evidence allowlist.
    sessions = set(allowed) | {forecast['session_id']} if receipt['receipt_type'] == 'source_capture' else {forecast['session_id']}
    _require(scope['session_id'] in sessions, 'scope_mismatch_session_id')
    if receipt['receipt_type'] != 'source_capture':
        for name in PRODUCT:
            _require(scope[name] == forecast[name], 'scope_mismatch_' + name)
    return True


def verify_temporal_bindings(receipt, *, cutoff=None, ingestion_required=False):
    p, kind = receipt['payload'], receipt['receipt_type']
    created = _time(receipt['receipt_created_utc'])
    if kind == 'source_capture':
        observed, ingested = _time(p['first_observed_utc']), _time(p['ingested_utc'])
        _require(observed <= ingested <= created, 'inconsistent_capture_times')
        if cutoff is not None:
            _require(observed <= _time(cutoff), 'first_observed_after_cutoff')
            if ingestion_required:
                _require(ingested <= _time(cutoff), 'ingested_after_cutoff')
    time_key = {'producer_execution': 'forecast_generation_utc', 'engine_execution': 'completed_utc',
                'normalization': 'completed_utc', 'forecast_lock': 'lock_utc', 'revision': 'first_observed_utc'}.get(kind)
    if time_key:
        _require(_time(p[time_key]) <= created, 'event_after_receipt_creation')
    # Event/publication times and an explicitly supplied future boundary are not
    # operational availability. No cutoff/deadline/boundary is invented here.
    return True


def _equal(a, b, names, prefix):
    for name in names:
        _require(a[name] == b[name], prefix + name)


def _verify(receipts, objects, forecast, bindings):
    _require(isinstance(receipts, list) and bool(receipts), 'missing_receipts')
    index = {}
    for receipt in receipts:
        validate_receipt_envelope(receipt)
        rid = receipt['receipt_id']
        _require(rid not in index, 'duplicate_receipt_id')
        _require(rid not in receipt['parent_receipt_ids'], 'self_parent')
        index[rid] = receipt
    for r in receipts:
        _require(all(pid in index for pid in r['parent_receipt_ids']), 'unknown_parent')
    pending, visited = set(index), set()
    while pending:
        ready = {rid for rid in pending if set(index[rid]['parent_receipt_ids']) <= visited}
        _require(bool(ready), 'cyclic_receipt_chain')
        pending -= ready
        visited |= ready
    def parents(r):
        return [index[pid] for pid in r['parent_receipt_ids']]
    def typed(kind):
        return [r for r in receipts if r['receipt_type'] == kind]
    def one(kind, ref):
        r = index.get(ref)
        _require(r is not None and r['receipt_type'] == kind, 'missing_' + kind)
        return r
    for r in receipts:
        _external_binding(r, bindings)
        verify_content_bindings(r, objects)
        verify_scope_bindings(r, forecast)
        verify_temporal_bindings(r)
        _require(all(_time(p['receipt_created_utc']) <= _time(r['receipt_created_utc']) for p in parents(r)),
                 'parent_created_after_child')
    for r in typed('source_capture'):
        _require(not parents(r), 'source_capture_has_parents')

    producers = typed('producer_execution')
    _require(len(producers) == 1, 'ambiguous_producer')
    producer, expected = producers[0], forecast['producer']
    p = producer['payload']
    _equal(p, expected, PRODUCER_KEYS, 'producer_mismatch_')
    _require(p['forecast_generation_utc'] == forecast['forecast_generation_utc'], 'generation_time_mismatch')
    manifest = canonical_json_bytes({k: forecast[k] for k in MANIFEST_KEYS})
    _require(objects[p['input_manifest_sha256']] == manifest, 'gate2a_manifest_mismatch')
    evidence = forecast['evidence']
    _require(isinstance(evidence, list) and bool(evidence), 'missing_evidence')
    source_ids = [e['source_id'] for e in evidence]
    required = forecast['mandatory_source_ids']
    _require(_strings(source_ids), 'duplicate_source_id')
    _require(_strings(required) and bool(required) and set(required) <= set(source_ids), 'missing_mandatory_evidence')
    captures = []
    for e in evidence:
        c = one('source_capture', e['capture_evidence_ref'])
        _equal(c['scope'], e, SCOPE, 'capture_scope_mismatch_')
        _equal(c['payload'], e, ('source_id', 'source_uri', 'source_sha256', 'event_time_utc',
                                'publisher_time_utc', 'first_observed_utc', 'ingested_utc'), 'capture_mismatch_')
        allowed = forecast['allowed_session_ids']
        _require(c['scope']['session_id'] in ([forecast['session_id']] if allowed is None else allowed), 'consumed_session_not_allowed')
        _require(isinstance(e['ingestion_required_at_cutoff'], bool), 'invalid_ingestion_policy')
        verify_temporal_bindings(c, cutoff=forecast['evidence_cutoff_utc'], ingestion_required=e['ingestion_required_at_cutoff'])
        _require(_time(e['ingested_utc']) <= _time(p['forecast_generation_utc']), 'ingestion_after_generation')
        captures.append(c)
    capture_ids = {c['receipt_id'] for c in captures}
    _require(len(capture_ids) == len(captures), 'duplicate_capture_slot')
    receipt_manifest = input_receipt_manifest_sha256(captures)
    _require(p['input_receipt_manifest_sha256'] == receipt_manifest, 'input_receipt_manifest_mismatch')
    producer_parent_ids = set(capture_ids)
    engine_projection = dict(engine_execution_id=None, engine_code_sha256=None, engine_execution_proof_ref=None)
    if p['engine_implementation'] is None:
        _require(p['engine_receipt_id'] is None and p['engine_result_sha256'] is None and not typed('engine_execution') and
                 all(expected.get(k) is None for k in engine_projection), 'orphan_engine_claim_or_receipt')
    else:
        _require(p['engine_receipt_id'] is not None and len(typed('engine_execution')) == 1, 'missing_engine_receipt')
        engine = one('engine_execution', p['engine_receipt_id'])
        ep = engine['payload']
        _require(ep['repository_backed'] == (ep['git_commit'] is not None), 'engine_repository_commit_unproven')
        _require(ep['engine_implementation'] == p['engine_implementation'], 'engine_implementation_mismatch')
        _require(ep['producer_execution_id'] == p['execution_id'], 'engine_invocation_mismatch')
        _require(ep['input_manifest_sha256'] == p['input_manifest_sha256'], 'engine_input_manifest_mismatch')
        _require(ep['input_receipt_manifest_sha256'] == receipt_manifest, 'engine_input_receipt_manifest_mismatch')
        _require(set(engine['parent_receipt_ids']) == capture_ids, 'engine_parent_mismatch')
        _require(ep['result_sha256'] == p['engine_result_sha256'], 'engine_result_mismatch')
        _require(_time(ep['completed_utc']) <= _time(p['forecast_generation_utc']), 'engine_after_producer')
        _require(ep['engine_code_sha256'] != p['code_sha256'] or ep['engine_implementation'] == p['implementation'], 'wrapper_hash_is_not_engine_hash')
        engine_projection = dict(engine_execution_id=ep['engine_execution_id'], engine_code_sha256=ep['engine_code_sha256'],
            engine_execution_proof_ref=bindings[engine['receipt_id']]['verification_ref'])
        _equal(engine_projection, expected, tuple(engine_projection), 'engine_mismatch_')
        producer_parent_ids.add(engine['receipt_id'])
    _require(set(producer['parent_receipt_ids']) == producer_parent_ids, 'producer_parent_mismatch')

    # Allow zero or multiple genuine transformations, but only the lock's ancestry.
    def output(r):
        return r['payload']['forecast_payload_sha256'] if r['receipt_type'] == 'producer_execution' else r['payload']['output_payload_sha256']
    def completion(r):
        return r['payload'].get('completed_utc', r['payload'].get('forecast_generation_utc'))
    for norm in typed('normalization'):
        ps = parents(norm)
        _require(len(ps) == 1 and ps[0]['receipt_type'] in ('producer_execution', 'normalization'), 'normalization_parent_mismatch')
        np = norm['payload']
        _require(np['input_payload_sha256'] == output(ps[0]), 'normalization_input_mismatch')
        _require(np['input_payload_sha256'] != np['output_payload_sha256'], 'normalization_without_transformation')
        _require(_time(completion(ps[0])) <= _time(np['completed_utc']), 'normalization_before_parent')
    lock = one('forecast_lock', forecast['lock_receipt_ref'])
    lp, ps = lock['payload'], parents(lock)
    _require(len(ps) == 1 and ps[0]['receipt_type'] in ('producer_execution', 'normalization'), 'lock_parent_mismatch')
    _require(lp['forecast_payload_sha256'] == lp['stored_payload_sha256'] == output(ps[0]), 'lock_payload_mismatch')
    _require(lp['lock_utc'] == forecast['forecast_lock_utc'], 'lock_time_mismatch')
    _require(_time(completion(ps[0])) <= _time(lp['lock_utc']), 'lock_before_payload')
    boundary = one('outcome_boundary', forecast['outcome_boundary_evidence_ref'])
    bp, ps = boundary['payload'], parents(boundary)
    _equal(bp, forecast, ('product_contract_id', 'outcome_availability_boundary_utc'), 'boundary_mismatch_')
    _require(len(ps) == 1 and ps[0]['receipt_type'] == 'source_capture', 'boundary_parent_mismatch')
    _require(bp['source_id'] == ps[0]['payload']['source_id'] and bp['evidence_sha256'] == ps[0]['payload']['source_sha256'], 'boundary_evidence_mismatch')
    # Policy interpretation is external. Merely record its explicit nonempty ref;
    # Gate 2A applies classification using the separately supplied boundary.
    revisions = typed('revision')
    declared = forecast['revisions']
    revision_ids = [r['payload']['revision_id'] for r in revisions]
    declared_ids = [r['revision_id'] for r in declared]
    _require(_strings(revision_ids) and _strings(declared_ids) and set(revision_ids) == set(declared_ids), 'revision_set_mismatch')
    for rev in revisions:
        rp, ps = rev['payload'], parents(rev)
        d = next(x for x in declared if x['revision_id'] == rp['revision_id'])
        _equal(rev['scope'], d, SCOPE + ('forecast_id', 'product_id'), 'revision_scope_mismatch_')
        _equal(rp, d, ('revision_id', 'source_id', 'source_sha256', 'first_observed_utc'), 'revision_mismatch_')
        _require(len(ps) == 1 and ps[0]['receipt_type'] == 'source_capture' and
                 ps[0]['receipt_id'] == d['capture_evidence_ref'], 'revision_parent_mismatch')
        cp = ps[0]['payload']
        _equal(rp, cp, ('source_id', 'source_sha256', 'first_observed_utc'), 'revision_capture_mismatch_')
        _require(any(e['source_id'] == cp['source_id'] and e['source_uri'] == cp['source_uri'] for e in evidence), 'revision_unrelated_source')
    reached, todo = set(), [lock['receipt_id'], boundary['receipt_id']] + [r['receipt_id'] for r in revisions]
    while todo:
        rid = todo.pop()
        if rid not in reached:
            reached.add(rid)
            todo.extend(index[rid]['parent_receipt_ids'])
    _require(reached == set(index), 'unrelated_receipts')
    return {p['execution_id']: {**{k: p[k] for k in PRODUCER_KEYS}, **engine_projection,
                               'verification_ref': bindings[producer['receipt_id']]['verification_ref']}}


def verify_receipt_chain(receipts, *, objects, forecast, verified_receipt_bindings=None):
    """Check graph/bytes against separately verified bindings and expected context.

Does NOT authenticate the binding provider, establish policy approval, classify
forecasts or attest that a timestamp/engine claim reflects a real-world event.
MALFORMED vs UNVERIFIABLE failures never contain an execution projection.
"""
    result = dict(status='UNVERIFIABLE', reason_codes=[], verified_execution_records={},
                  trust_scope='EXTERNAL_BINDING_INTERFACE_ONLY', production_authenticated=False)
    try:
        records = _verify(receipts, objects, forecast, verified_receipt_bindings or {})
        result.update(status='VERIFIED_BINDINGS', verified_execution_records=records)
    except ReceiptError as exc:
        result.update(status='MALFORMED' if exc.malformed else 'UNVERIFIABLE', reason_codes=[exc.code])
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, RecursionError):
        result.update(status='MALFORMED', reason_codes=['malformed_context_or_receipt'])
    return result


def build_verified_execution_records(receipts, *, objects, forecast, verified_receipt_bindings=None):
    """Reverify before projection; return full envelope retaining trust limitations."""
    return verify_receipt_chain(receipts, objects=objects, forecast=forecast,
                                verified_receipt_bindings=verified_receipt_bindings)


def receipt_schema():
    """Shared envelope + seven typed payloads. Structural schema, not authentication."""
    primitives = {
        'text': {'type': 'string', 'minLength': 1, 'pattern': r'\S'},
        'hash': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
        'commit': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
        'time': {'type': 'string', 'format': 'date-time', 'pattern': r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$'},
        'boolean': {'type': 'boolean'},
    }
    def ref(kind):
        return {'$ref': '#/$defs/' + kind}
    for kind in ('text', 'time', 'commit', 'hash'):
        primitives['nullable_' + kind] = {'anyOf': [ref(kind), {'type': 'null'}]}
    def obj(fields):
        return {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}
    primitives['capture_scope'] = obj({k: ref('text') for k in SCOPE})
    primitives['forecast_scope'] = obj({k: ref('text') for k in SCOPE + PRODUCT})
    for kind, fields in PAYLOADS.items():
        primitives[kind] = obj({k: ref(v) for k, v in fields.items()})
    schema = obj(dict(schema_version={'const': VERSION}, receipt_id=ref('text'),
        receipt_type={'enum': list(PAYLOADS)}, receipt_created_utc=ref('time'), scope={},
        parent_receipt_ids={'type': 'array', 'items': ref('text'), 'uniqueItems': True}, payload={}))
    schema.update({'$schema': 'https://json-schema.org/draft/2020-12/schema', '$id': 'urn:f1:dr002:receipt:v1',
        'title': 'DR-002 offline shared receipt envelope',
        'description': 'receipt_created_utc is receipt assembly time, never source availability or lock time. External bindings are required separately; this schema establishes no trust.',
        '$defs': primitives, 'allOf': [
            {'if': {'properties': {'receipt_type': {'const': kind}}},
             'then': {'properties': {'payload': ref(kind), 'scope': ref('capture_scope' if kind == 'source_capture' else 'forecast_scope')}}}
            for kind in PAYLOADS]})
    return schema
