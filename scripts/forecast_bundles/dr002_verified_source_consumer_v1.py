"""Pure offline composition; a GitHub binding never upgrades frozen-manifest trust.

The bridge result is a caller-supplied trust interface, not self-authenticating
JSON. Callers must obtain it from the accepted F1 bridge and approved external
verifier boundary. This consumer checks composition, not signatures or origin.
"""
from . import verify_forecast_integrity_receipts_v1 as receipts
from . import dr002_frozen_evidence_manifest_v1 as frozen
from . import dr002_github_attestation_binding_v1 as bridge


class ConsumerError(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise ConsumerError(reason)


def consume_verified_source(*, receipt_bytes, source_bytes, request_scope, bridge_result):
    """Compose one explicit receipt/content pair with its separate F1 binding.

request_scope contains exactly event_id, meeting_id and allowed_session_ids.
No paths are accepted: the existing builder receives a closed in-memory reader.
HOLD never returns a partial manifest or binding. Inputs are not mutated.
"""
    try:
        return _consume(receipt_bytes, source_bytes, request_scope, bridge_result)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError,
            OverflowError, RecursionError) as exc:
        return dict(status='HOLD', reason_codes=[getattr(exc, 'code', None) or str(exc)
                                              or 'malformed_consumer_input'],
                    verified_receipt_bindings={}, **bridge.HOLD_TRUST)


def _consume(receipt_bytes, source_bytes, scope, binding_result):
    _require(type(receipt_bytes) is bytes and type(source_bytes) is bytes,
             'exact_bytes_required')
    receipt = frozen.strict_json(receipt_bytes)
    receipts.validate_receipt_envelope(receipt)
    _require(receipt['receipt_type'] == 'source_capture'
             and receipt['parent_receipt_ids'] == [], 'parentless_source_capture_required')
    receipts.verify_temporal_bindings(receipt)
    _require(receipt_bytes == receipts.canonical_json_bytes(receipt),
             'noncanonical_receipt_bytes')
    exact_digest = receipts.sha256(receipt_bytes)
    canonical_digest = receipts.receipt_sha256(receipt)
    _require(exact_digest == canonical_digest, 'canonical_exact_digest_mismatch')
    source_digest = receipts.sha256(source_bytes)
    _require(source_digest == receipt['payload']['source_sha256'], 'source_hash_mismatch')

    _require(isinstance(scope, dict) and set(scope) ==
             {'event_id', 'meeting_id', 'allowed_session_ids'}, 'malformed_request_scope')
    # Fixed tokens are dictionary keys, never filesystem locations or discovery.
    request = {**scope, 'captures': [{'receipt_path': 'receipt', 'content_path': 'source'}]}
    frozen.validate_request(request)
    _require(scope['event_id'] == receipt['scope']['event_id'], 'event_mismatch')
    _require(scope['meeting_id'] == receipt['scope']['meeting_id'], 'meeting_mismatch')
    _require(receipt['scope']['session_id'] in scope['allowed_session_ids'], 'session_mismatch')

    fields = {'status', 'schema_version', 'verified_receipt_bindings', 'receipt_id',
              'canonical_receipt_sha256', 'exact_receipt_sha256',
              'attested_receipt_existed_by_utc', 'internal_first_observed_utc',
              'trust_scope'} | set(bridge.HOLD_TRUST)
    _require(isinstance(binding_result, dict) and set(binding_result) == fields,
             'ambiguous_bridge_envelope')
    _require(binding_result['status'] == 'VERIFIED_GITHUB_PROVENANCE_BINDING'
             and binding_result['schema_version'] == bridge.VERSION
             and binding_result['trust_scope'] == bridge.TRUST_SCOPE,
             'bridge_status_or_scope_mismatch')
    _require(all(binding_result[key] is False for key in bridge.HOLD_TRUST),
             'bridge_trust_ceiling_mismatch')
    rid = receipt['receipt_id']
    _require(binding_result['receipt_id'] == rid
             and binding_result['canonical_receipt_sha256'] == canonical_digest
             and binding_result['exact_receipt_sha256'] == exact_digest,
             'bridge_receipt_identity_mismatch')
    bindings = binding_result['verified_receipt_bindings']
    _require(isinstance(bindings, dict) and set(bindings) == {rid}, 'single_binding_required')
    binding = receipts._external_binding(receipt, bindings)
    observed = receipt['payload']['first_observed_utc']
    _require(binding_result['internal_first_observed_utc'] == observed,
             'internal_observation_claim_mismatch')
    existed_by = binding_result['attested_receipt_existed_by_utc']
    _require(receipts._time(existed_by) >= receipts._time(receipt['receipt_created_utc']),
             'existence_bound_before_creation')

    memory = {'receipt': receipt_bytes, 'source': source_bytes}
    manifest = frozen.build_frozen_evidence_manifest(request, read_bytes=memory.__getitem__)
    frozen.validate_frozen_evidence_manifest(manifest)
    trust = manifest['manifest']['trust']
    _require(set(trust) == {'binding_status', 'production_authenticated',
                           'historical_availability_proven'}
             and trust['binding_status'] == 'UNBOUND'
             and trust['production_authenticated'] is False
             and trust['historical_availability_proven'] is False,
             'frozen_manifest_trust_changed')
    return dict(status='OFFLINE_VERIFIED_SOURCE_CONSUMER_VALIDATED',
                frozen_evidence_manifest=manifest,
                verified_receipt_bindings={rid: dict(binding)}, receipt_id=rid,
                canonical_receipt_sha256=canonical_digest, exact_receipt_sha256=exact_digest,
                source_sha256=source_digest, binding_trust_scope=bridge.TRUST_SCOPE,
                attested_receipt_existed_by_utc=existed_by,
                internal_first_observed_utc=observed, frozen_manifest_binding_status='UNBOUND',
                **bridge.HOLD_TRUST)
