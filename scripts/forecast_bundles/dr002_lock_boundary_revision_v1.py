"""Offline lock/outcome/revision contracts. No authentication or trust upgrade."""
from copy import deepcopy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_forecast_integrity_receipts_v1 import (canonical_json_bytes, sha256,
    receipt_sha256, validate_receipt_envelope, verify_temporal_bindings,
    verify_receipt_chain, MANIFEST_KEYS, PRODUCER_KEYS, SCOPE, PRODUCT, VERSION)
from forecast_integrity_contract_v1 import input_manifest_sha256, classify_forecast

TRUST = dict(binding_status='UNBOUND', production_authenticated=False,
             historical_availability_proven=False, dr002_activated=False)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def time(value):
    # Use the unchanged envelope's UTC validation rather than accepting local time.
    from verify_forecast_integrity_receipts_v1 import _time
    return _time(value)


def scope(forecast):
    return {k:forecast[k] for k in SCOPE + PRODUCT}


def capture(receipt):
    validate_receipt_envelope(receipt); verify_temporal_bindings(receipt)
    require(receipt['receipt_type']=='source_capture' and receipt['parent_receipt_ids']==[], 'invalid_source_capture')
    return receipt['payload']


def receipt(kind, forecast, parent, payload, created):
    identity=dict(receipt_type=kind, scope=scope(forecast), parent_receipt_ids=[parent], payload=payload)
    result=dict(schema_version=VERSION, receipt_id=kind+':'+sha256(canonical_json_bytes(identity)),
        receipt_created_utc=created, **identity)
    validate_receipt_envelope(result); verify_temporal_bindings(result)
    return result


def build_forecast_lock(forecast, producer, payload_bytes, *, lock_utc, receipt_created_utc, storage_ref):
    validate_receipt_envelope(producer); verify_temporal_bindings(producer)
    require(producer['receipt_type']=='producer_execution', 'wrong_producer_type')
    require(producer['scope']==scope(forecast), 'producer_scope_mismatch')
    p=producer['payload']
    require(all(forecast['producer'][k]==p[k] for k in PRODUCER_KEYS), 'producer_identity_mismatch')
    require(forecast['forecast_generation_utc']==p['forecast_generation_utc'], 'generation_mismatch')
    require(input_manifest_sha256(forecast)==p['input_manifest_sha256'], 'input_manifest_mismatch')
    require(isinstance(payload_bytes,bytes) and sha256(payload_bytes)==p['forecast_payload_sha256'], 'exact_payload_mismatch')
    require(time(p['forecast_generation_utc'])<=time(lock_utc)<=time(receipt_created_utc), 'invalid_lock_order')
    require(time(producer['receipt_created_utc'])<=time(receipt_created_utc), 'parent_after_child')
    payload=dict(forecast_payload_sha256=sha256(payload_bytes),stored_payload_sha256=sha256(payload_bytes),
                 lock_utc=lock_utc,storage_ref=storage_ref)
    return receipt('forecast_lock',forecast,producer['receipt_id'],payload,receipt_created_utc)


def build_outcome_boundary(forecast, producer, outcome_capture, *, outcome_session_id,
                           boundary_policy_ref, receipt_created_utc):
    p=capture(outcome_capture)
    require(outcome_capture['scope']==dict(event_id=forecast['event_id'],meeting_id=forecast['meeting_id'],session_id=outcome_session_id), 'outcome_scope_mismatch')
    # Gate 2B-1 currently requires supporting outcome capture to be target or
    # explicitly allowed session. Do not silently broaden the forecast manifest.
    allowed=forecast['allowed_session_ids'] or [forecast['session_id']]
    require(outcome_session_id in set(allowed)|{forecast['session_id']}, 'outcome_session_not_permitted')
    require(outcome_capture['receipt_id'] not in producer['parent_receipt_ids'], 'input_capture_is_not_outcome')
    require(p['source_id'] not in [e['source_id'] for e in forecast['evidence']], 'input_source_is_not_outcome')
    require(time(outcome_capture['receipt_created_utc'])<=time(receipt_created_utc), 'parent_after_child')
    payload=dict(product_contract_id=forecast['product_contract_id'],boundary_policy_ref=boundary_policy_ref,
        outcome_availability_boundary_utc=p['first_observed_utc'],source_id=p['source_id'],evidence_sha256=p['source_sha256'])
    return receipt('outcome_boundary',forecast,outcome_capture['receipt_id'],payload,receipt_created_utc)


def build_revision(forecast, revised_capture, *, receipt_created_utc):
    p=capture(revised_capture);sc=revised_capture['scope']
    require(sc['event_id']==forecast['event_id'] and sc['meeting_id']==forecast['meeting_id'], 'revision_scope_mismatch')
    matches=[e for e in forecast['evidence'] if e['source_id']==p['source_id']]
    require(len(matches)==1,'revision_source_ambiguous')
    original=matches[0]
    require(p['source_uri']==original['source_uri'] and sc['session_id']==original['session_id'], 'revision_source_scope_mismatch')
    require(p['source_sha256']!=original['source_sha256'], 'identical_bytes_are_not_revision')
    require(revised_capture['receipt_id']!=original['capture_evidence_ref'], 'revision_reuses_original_capture')
    require(time(p['first_observed_utc'])>=time(original['first_observed_utc']), 'revision_before_original')
    require(time(revised_capture['receipt_created_utc'])<=time(receipt_created_utc), 'parent_after_child')
    identity=dict(forecast_id=forecast['forecast_id'],capture_receipt_id=revised_capture['receipt_id'],
        source_id=p['source_id'],source_sha256=p['source_sha256'],first_observed_utc=p['first_observed_utc'])
    rid='revision:'+sha256(canonical_json_bytes(identity))
    payload=dict(revision_id=rid,source_id=p['source_id'],source_sha256=p['source_sha256'],first_observed_utc=p['first_observed_utc'])
    result=receipt('revision',forecast,revised_capture['receipt_id'],payload,receipt_created_utc)
    declared={k:forecast[k] for k in SCOPE+('forecast_id','product_id')}
    declared.update(payload,capture_evidence_ref=revised_capture['receipt_id'])
    return result,declared


def complete_forecast_record(base, producer, lock, boundary, revisions):
    """Copy non-manifest proof fields only. Revalidate constructed proof bindings."""
    for r in (lock,boundary):
        validate_receipt_envelope(r);verify_temporal_bindings(r)
        require(r['scope']==scope(base),'proof_scope_mismatch')
    require(lock['receipt_type']=='forecast_lock' and lock['parent_receipt_ids']==[producer['receipt_id']], 'wrong_lock_parent')
    require(lock['payload']['forecast_payload_sha256']==lock['payload']['stored_payload_sha256']==producer['payload']['forecast_payload_sha256'], 'lock_hash_mismatch')
    require(boundary['receipt_type']=='outcome_boundary' and boundary['payload']['product_contract_id']==base['product_contract_id'], 'wrong_boundary')
    result=deepcopy(base)
    result.update(forecast_lock_utc=lock['payload']['lock_utc'],lock_receipt_ref=lock['receipt_id'],
        outcome_availability_boundary_utc=boundary['payload']['outcome_availability_boundary_utc'],
        outcome_boundary_evidence_ref=boundary['receipt_id'],revisions=deepcopy(sorted(revisions,key=lambda r:r['revision_id'])))
    require(len({r['revision_id'] for r in revisions})==len(revisions), 'duplicate_revision')
    require(all(result[k]==base[k] for k in MANIFEST_KEYS), 'manifest_changed')
    require(input_manifest_sha256(result)==producer['payload']['input_manifest_sha256'], 'completed_manifest_mismatch')
    return result


def build_proof_package(base, producer, payload_bytes, outcome_capture, *, lock_utc,
                        lock_receipt_created_utc, storage_ref, outcome_session_id,
                        boundary_policy_ref, boundary_receipt_created_utc,
                        revision_captures=(), revision_receipt_created_utc=None):
    lock=build_forecast_lock(base,producer,payload_bytes,lock_utc=lock_utc,
        receipt_created_utc=lock_receipt_created_utc,storage_ref=storage_ref)
    boundary=build_outcome_boundary(base,producer,outcome_capture,outcome_session_id=outcome_session_id,
        boundary_policy_ref=boundary_policy_ref,receipt_created_utc=boundary_receipt_created_utc)
    revisions=[];declared=[];seen=set();states=set()
    for c in revision_captures:
        require(c['receipt_id'] not in seen, 'duplicate_revision_capture');seen.add(c['receipt_id'])
        state=(c['payload']['source_id'],c['payload']['source_sha256'],c['payload']['first_observed_utc'])
        require(state not in states,'duplicate_revision_observation');states.add(state)
        r,d=build_revision(base,c,receipt_created_utc=revision_receipt_created_utc)
        revisions.append(r);declared.append(d)
    completed=complete_forecast_record(base,producer,lock,boundary,declared)
    return dict(forecast=completed, receipts=[lock,boundary]+sorted(revisions,key=lambda r:r['receipt_id']),trust=dict(TRUST))


def verify_and_classify(package, receipts, *, objects, verified_receipt_bindings):
    """Caller supplies external bindings. Never fabricates or authenticates them."""
    # Apply the new stricter observation rules before the unchanged graph verifier.
    # A caller must not bypass them by supplying an altered boundary receipt.
    try:
        index={r['receipt_id']:r for r in receipts}
        require(len(index)==len(receipts), 'duplicate_receipt')
        f=package['forecast']
        producers=[r for r in receipts if r['receipt_type']=='producer_execution']
        require(len(producers)==1, 'ambiguous_producer')
        producer=producers[0]
        lock=index[f['lock_receipt_ref']]
        rebuilt=build_forecast_lock(f,producer,objects[producer['payload']['forecast_payload_sha256']],
            lock_utc=lock['payload']['lock_utc'],receipt_created_utc=lock['receipt_created_utc'],storage_ref=lock['payload']['storage_ref'])
        require(rebuilt==lock, 'noncanonical_lock_receipt')
        boundary=index[f['outcome_boundary_evidence_ref']]
        outcome=index[boundary['parent_receipt_ids'][0]]
        rebuilt=build_outcome_boundary(f,producer,outcome,outcome_session_id=outcome['scope']['session_id'],
            boundary_policy_ref=boundary['payload']['boundary_policy_ref'],receipt_created_utc=boundary['receipt_created_utc'])
        require(rebuilt==boundary,'boundary_not_observation_bound')
        for r in receipts:
            if r['receipt_type']=='revision':
                rebuilt,declared=build_revision(f,index[r['parent_receipt_ids'][0]],receipt_created_utc=r['receipt_created_utc'])
                require(rebuilt==r and declared in f['revisions'], 'revision_not_capture_bound')
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        return dict(verification=dict(status='UNVERIFIABLE',reason_codes=[str(exc)],verified_execution_records={},
            production_authenticated=False,trust_scope='EXTERNAL_BINDING_INTERFACE_ONLY'),classification=None,trust=dict(TRUST))
    result=verify_receipt_chain(receipts,objects=objects,forecast=package['forecast'],
        verified_receipt_bindings=verified_receipt_bindings)
    classification=None
    if result['status']=='VERIFIED_BINDINGS':
        classification=classify_forecast(package['forecast'],verified_execution_records=result['verified_execution_records'])
    return dict(verification=result,classification=classification,trust=dict(TRUST))
