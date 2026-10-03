"""Offline explicit frozen evidence set. Containment is not authentication.

Filesystem paths are transport locations only. Manifest refs are content-addressed
logical references, independent of host paths; capture_ref is a canonical receipt
reference to that field, not a copied machine-local path. The receipt hash still
binds the complete original receipt, including its original capture_ref.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_forecast_integrity_receipts_v1 import (
    canonical_json_bytes, sha256, receipt_sha256, validate_receipt_envelope,
    input_receipt_manifest_sha256, verify_temporal_bindings,
)
VERSION = 'dr002-frozen-evidence-v1'
TRUST = dict(binding_status='UNBOUND', production_authenticated=False,
             historical_availability_proven=False)


class EvidenceError(ValueError):
    """Entire set rejected; no partial manifest is returned."""


def require(ok, reason):
    if not ok:
        raise EvidenceError(reason)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(EvidenceError('nonfinite_json')))


def validate_request(request):
    require(isinstance(request, dict) and set(request) ==
            {'event_id', 'meeting_id', 'allowed_session_ids', 'captures'}, 'malformed_request')
    require(text(request['event_id']) and text(request['meeting_id']), 'missing_scope')
    sessions = request['allowed_session_ids']
    require(isinstance(sessions, list) and bool(sessions) and all(text(x) for x in sessions)
            and len(set(sessions)) == len(sessions), 'ambiguous_allowed_sessions')
    require(isinstance(request['captures'], list) and bool(request['captures']), 'empty_evidence')
    for capture in request['captures']:
        require(isinstance(capture, dict) and set(capture) == {'receipt_path', 'content_path'}
                and all(text(v) for v in capture.values()), 'malformed_capture_input')


def validate_frozen_evidence_manifest(result):
    """Validate strict output and recompute both hashes; does not authenticate it."""
    require(isinstance(result, dict) and set(result) ==
            {'manifest', 'frozen_evidence_manifest_sha256'}, 'malformed_result')
    body = result['manifest']
    require(isinstance(body, dict) and set(body) ==
            {'schema_version', 'scope', 'evidence', 'input_receipt_manifest_sha256', 'trust'}, 'malformed_manifest')
    require(body['schema_version'] == VERSION, 'unsupported_version')
    trust = body['trust']
    require(isinstance(trust, dict) and set(trust) == set(TRUST) and
            trust['binding_status'] == 'UNBOUND' and trust['production_authenticated'] is False
            and trust['historical_availability_proven'] is False, 'unsupported_trust_claim')
    scope = body['scope']
    require(isinstance(scope, dict) and set(scope) ==
            {'event_id', 'meeting_id', 'allowed_session_ids'}, 'malformed_scope')
    validate_request({**scope, 'captures': [{'receipt_path': 'explicit', 'content_path': 'explicit'}]})
    require(scope['allowed_session_ids'] == sorted(scope['allowed_session_ids']), 'noncanonical_sessions')
    evidence = body['evidence']
    require(isinstance(evidence, list) and bool(evidence), 'empty_evidence')
    fields = {'source_id', 'source_uri', 'receipt_id', 'receipt_sha256', 'source_sha256',
              'session_id', 'event_time_utc', 'publisher_time_utc', 'first_observed_utc',
              'ingested_utc', 'capture_ref', 'supplied_content_ref'}
    ids, sources = set(), set()
    for e in evidence:
        require(isinstance(e, dict) and set(e) == fields, 'malformed_evidence')
        require(all(text(e[k]) for k in fields - {'event_time_utc', 'publisher_time_utc'}), 'missing_evidence_field')
        require(e['receipt_id'] not in ids and e['source_id'] not in sources, 'duplicate_evidence')
        ids.add(e['receipt_id']); sources.add(e['source_id'])
        require(e['session_id'] in scope['allowed_session_ids'], 'disallowed_session')
        # Reuse envelope primitive validation for source hash and timestamp types.
        receipt = dict(schema_version='dr002-receipt-v1', receipt_id=e['receipt_id'],
            receipt_type='source_capture', receipt_created_utc=e['ingested_utc'],
            scope=dict(event_id=scope['event_id'], meeting_id=scope['meeting_id'], session_id=e['session_id']),
            parent_receipt_ids=[], payload={k:e[k] for k in
                ('source_id','source_uri','source_sha256','event_time_utc','publisher_time_utc',
                 'first_observed_utc','ingested_utc','capture_ref')})
        receipt['payload']['implementation'] = 'structural-manifest-validator'
        validate_receipt_envelope(receipt); verify_temporal_bindings(receipt)
        require(len(e['receipt_sha256']) == 64 and all(c in '0123456789abcdef' for c in e['receipt_sha256']), 'malformed_receipt_hash')
        require(e['capture_ref'] == 'receipt-sha256:' + e['receipt_sha256'] + '#/payload/capture_ref', 'invalid_capture_reference')
        require(e['supplied_content_ref'] == 'sha256:' + e['source_sha256'], 'invalid_content_reference')
    require(evidence == sorted(evidence, key=lambda e:(e['source_id'],e['session_id'],e['receipt_id'])), 'noncanonical_evidence_order')
    receipt_set = sorted(({'receipt_id':e['receipt_id'], 'receipt_sha256':e['receipt_sha256']} for e in evidence), key=lambda e:e['receipt_id'])
    require(body['input_receipt_manifest_sha256'] == sha256(canonical_json_bytes(receipt_set)), 'receipt_set_hash_mismatch')
    require(result['frozen_evidence_manifest_sha256'] == sha256(canonical_json_bytes(body)), 'frozen_manifest_hash_mismatch')
    return True


def build_frozen_evidence_manifest(request, *, read_bytes=lambda path: Path(path).read_bytes()):
    """Reads ONLY individually supplied files. Raises on any bad capture.

No wall clock, discovery, fallback, execution receipt or trust upgrade. Caller
inputs are not mutated. Relocation of unchanged receipts/content does not matter.
"""
    validate_request(request)
    receipts, evidence, ids, sources = [], [], set(), set()
    for capture in request['captures']:
        receipt = strict_json(read_bytes(capture['receipt_path']))
        validate_receipt_envelope(receipt)
        require(receipt['receipt_type'] == 'source_capture', 'wrong_receipt_type')
        require(receipt['parent_receipt_ids'] == [], 'capture_has_parents')
        verify_temporal_bindings(receipt)
        scope, payload = receipt['scope'], receipt['payload']
        require(scope['event_id'] == request['event_id'], 'wrong_event')
        require(scope['meeting_id'] == request['meeting_id'], 'wrong_meeting')
        require(scope['session_id'] in request['allowed_session_ids'], 'disallowed_session')
        require(receipt['receipt_id'] not in ids, 'duplicate_receipt_id')
        require(payload['source_id'] not in sources, 'duplicate_source_id')
        ids.add(receipt['receipt_id']); sources.add(payload['source_id'])
        content = read_bytes(capture['content_path'])
        require(isinstance(content, bytes) and sha256(content) == payload['source_sha256'], 'source_hash_mismatch')
        digest = receipt_sha256(receipt)
        evidence.append({**{k:payload[k] for k in ('source_id','source_uri','source_sha256',
            'event_time_utc','publisher_time_utc','first_observed_utc','ingested_utc')},
            'receipt_id':receipt['receipt_id'], 'receipt_sha256':digest, 'session_id':scope['session_id'],
            'capture_ref':'receipt-sha256:' + digest + '#/payload/capture_ref',
            'supplied_content_ref':'sha256:' + payload['source_sha256']})
        receipts.append(receipt)
    body = dict(schema_version=VERSION, scope=dict(event_id=request['event_id'],
        meeting_id=request['meeting_id'], allowed_session_ids=sorted(request['allowed_session_ids'])),
        evidence=sorted(evidence, key=lambda e:(e['source_id'],e['session_id'],e['receipt_id'])),
        input_receipt_manifest_sha256=input_receipt_manifest_sha256(receipts), trust=dict(TRUST))
    result = dict(manifest=body, frozen_evidence_manifest_sha256=sha256(canonical_json_bytes(body)))
    validate_frozen_evidence_manifest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, help='Explicit request JSON; paths resolved as supplied from cwd')
    args = parser.parse_args()
    try:
        result = build_frozen_evidence_manifest(strict_json(Path(args.request).read_bytes()))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({'status':'HOLD','reason':str(exc)}), file=sys.stderr)
        return 1
    print(canonical_json_bytes(result).decode())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
