"""Offline as-of evidence audit, separate from unchanged Gate 2A classification.

All data is explicitly supplied. External bindings remain a caller trust interface;
matching synthetic bindings proves checks, not production authentication. No I/O.
"""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forecast_integrity_contract_v1 import classify_forecast, _time as parse_utc
from verify_forecast_integrity_receipts_v1 import (
    ReceiptError, canonical_json_bytes, receipt_sha256, sha256,
    validate_receipt_envelope, verify_temporal_bindings,
)
from dr002_lock_boundary_revision_v1 import TRUST

LEGACY_ROOT = ('history/forecast_bundles/2026_1295_azerbaijan_baku_baku/'
               '20260925T150434Z/post_qualifying/stable_baseline/')
LEGACY_BLOBS = {
    'bundle_lock_manifest.json': '0e5d8b62625f5a35d35914b6451e6d85cb73e7df',
    'source_snapshot_manifest.csv': '64fda6e9dbced3daa4141b343a6d71fad4ba897e',
    'engine_lane_config.json': '2c82835c2025113c4e9b3fe817fbf847552d947b',
    'forecast_rows.csv': '74b26427d606e53ac91212b52887b844a9bf4d8e',
}
PROJECTION_FIELDS = ('source_id', 'source_uri', 'source_sha256', 'event_time_utc',
                     'publisher_time_utc', 'first_observed_utc', 'ingested_utc')
OUTCOME_KINDS = frozenset(('outcome', 'race_result', 'post_event'))


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def evaluate_as_of(record, *, captures, content_by_receipt_id,
                   evidence_kinds, verified_receipt_bindings=None,
                   verified_execution_records=None):
    """Audit exact source provenance without relabelling replay as blind.

    captures are explicit source_capture dicts; content is exact byte data keyed
    by receipt ID. evidence_kinds explicitly declares predictive/outcome role.
    No binding is built here. AS_OF_CONTRACT_CLEAN is conditional on supplied
    external bindings, never a production authentication or historical claim.
    """
    classification = classify_forecast(record, verified_execution_records=verified_execution_records)
    findings = []
    def add(status, code, source_id=None):
        findings.append(dict(status=status, code=code, source_id=source_id))
    try:
        if not isinstance(record, dict) or not isinstance(captures, list):
            raise ValueError('malformed_inputs')
        evidence = record.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            add('UNPROVEN', 'missing_source_evidence')
            evidence = []
        cutoff = record.get('evidence_cutoff_utc')
        indexed = {}
        for receipt in captures:
            if isinstance(receipt, dict) and receipt.get('receipt_type') == 'source_capture' and isinstance(receipt.get('payload'), dict) and not receipt['payload'].get('first_observed_utc'):
                add('UNPROVEN', 'source_first_observation_missing', receipt['payload'].get('source_id'))
                continue
            validate_receipt_envelope(receipt)
            if receipt['receipt_type'] != 'source_capture' or receipt['parent_receipt_ids']:
                raise ValueError('not_parentless_source_capture')
            rid = receipt['receipt_id']
            if rid in indexed:
                raise ValueError('duplicate_capture_id')
            indexed[rid] = receipt
        used = set()
        source_ids = set()
        for e in evidence:
            sid = e['source_id']
            if sid in source_ids:
                raise ValueError('duplicate_evidence_source')
            source_ids.add(sid)
            kind = evidence_kinds.get(sid)
            if kind in OUTCOME_KINDS:
                add('INELIGIBLE', 'outcome_evidence_in_predictive_input', sid)
            elif kind != 'predictive':
                add('UNPROVEN', 'evidence_role_unproven', sid)
            rid = e.get('capture_evidence_ref')
            receipt = indexed.get(rid)
            if receipt is None:
                add('UNPROVEN', 'missing_source_capture', sid)
                continue
            used.add(rid)
            p, scope = receipt['payload'], receipt['scope']
            if any(k not in e or e[k] is None for k in ('source_uri', 'source_sha256', 'first_observed_utc', 'ingested_utc')):
                add('UNPROVEN', 'source_provenance_missing', sid)
                continue
            if any(e.get(k) != p[k] for k in PROJECTION_FIELDS):
                add('HOLD', 'receipt_evidence_projection_mismatch', sid)
                continue
            allowed = record.get('allowed_session_ids')
            allowed = [record.get('session_id')] if allowed is None else allowed
            if (not isinstance(allowed, list) or not allowed or len(set(allowed)) != len(allowed)
                    or any(scope[k] != record.get(k) or e.get(k) != scope[k]
                           for k in ('event_id', 'meeting_id'))
                    or scope['session_id'] not in allowed or e.get('session_id') != scope['session_id']):
                add('HOLD', 'source_scope_mismatch', sid)
            content = content_by_receipt_id.get(rid)
            if not isinstance(content, bytes) or sha256(content) != p['source_sha256']:
                add('HOLD', 'missing_or_mismatched_exact_source_bytes', sid)
            binding = (verified_receipt_bindings or {}).get(rid)
            if binding is None:
                add('UNPROVEN', 'missing_external_capture_binding', sid)
            elif (not isinstance(binding, dict) or set(binding) != {'receipt_sha256', 'verification_ref'}
                    or binding['receipt_sha256'] != receipt_sha256(receipt)
                    or not isinstance(binding['verification_ref'], str) or not binding['verification_ref'].strip()):
                add('HOLD', 'external_capture_binding_mismatch', sid)
            required = e.get('ingestion_required_at_cutoff')
            if not isinstance(required, bool):
                add('UNPROVEN', 'ingestion_policy_missing', sid)
            try:
                if cutoff is None:
                    add('UNPROVEN', 'evidence_cutoff_missing', sid)
                else:
                    verify_temporal_bindings(receipt, cutoff=cutoff, ingestion_required=required is True)
            except ReceiptError as exc:
                status = 'INELIGIBLE' if exc.code in ('first_observed_after_cutoff', 'ingested_after_cutoff') else 'HOLD'
                add(status, exc.code, sid)
        if used != set(indexed):
            add('HOLD', 'undeclared_capture')
        required_ids = record.get('mandatory_source_ids')
        if isinstance(required_ids, list) and (len(set(required_ids)) != len(required_ids) or not all(isinstance(x, str) and x.strip() for x in required_ids)):
            add('HOLD', 'ambiguous_mandatory_sources')
        if not isinstance(required_ids, list) or not required_ids or not set(required_ids).issubset(source_ids):
            add('UNPROVEN', 'mandatory_sources_unproven')
        if classification['state'] == 'OUTCOME_AWARE_EVALUATION_ONLY':
            # Replay/evaluation precedence is preserved; not_before_outcome is
            # reported by Gate 2A itself for otherwise prospective records.
            forecast_note = 'replay_or_outcome_aware_not_historical_blind_prediction'
        else:
            forecast_note = 'forecast_classification_is_separate_from_input_cleanliness'
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
        add('HOLD', str(exc))
        forecast_note = 'malformed_or_unverifiable_input'
    statuses = {f['status'] for f in findings}
    state = next((s for s in ('HOLD', 'INELIGIBLE', 'UNPROVEN') if s in statuses), 'AS_OF_CONTRACT_CLEAN')
    temporal = []
    if isinstance(record, dict):
        boundary = record.get('outcome_availability_boundary_utc')
        for key in ('forecast_generation_utc', 'forecast_lock_utc'):
            try:
                if boundary is None or record.get(key) is None:
                    temporal.append(dict(field=key, status='UNPROVEN', reason='missing_time_or_outcome_boundary'))
                elif parse_utc(record[key]) >= parse_utc(boundary):
                    temporal.append(dict(field=key, status='INELIGIBLE', reason='not_before_outcome'))
                else:
                    temporal.append(dict(field=key, status='CONTRACT_CHECK_PASSED', reason='before_declared_outcome_boundary'))
            except (ValueError, TypeError, AttributeError):
                temporal.append(dict(field=key, status='HOLD', reason='malformed_explicit_time'))
    return dict(schema_version='dr002-replay-leakage-evidence-v1',
                forecast_temporal_findings=temporal,
                evidence_as_of_state=state, findings=sorted(findings, key=lambda f: (f['code'], str(f['source_id']))),
                forecast_classification=classification, forecast_note=forecast_note,
                production_blind_eligibility_certified=False,
                engine_execution='NOT_PROVEN',
                trust=dict(TRUST),
                claim_limit='Source binding checks are conditional on externally supplied bindings; no production authentication established.',
                observed_input_violation=any(f['status'] == 'INELIGIBLE' for f in findings))


def audit_legacy_baku(explicit_files):
    """Audit exactly the four pinned history bytes; do not discover or rewrite."""
    try:
        if set(explicit_files) != set(LEGACY_BLOBS):
            raise ValueError('missing_or_extra_legacy_file')
        for name, expected in LEGACY_BLOBS.items():
            data = explicit_files[name]
            if not isinstance(data, bytes) or git_blob_sha(data) != expected:
                raise ValueError('legacy_blob_mismatch:' + name)
        manifest = json.loads(explicit_files['bundle_lock_manifest.json'])
        lane = json.loads(explicit_files['engine_lane_config.json'])
        sources = list(csv.DictReader(io.StringIO(explicit_files['source_snapshot_manifest.csv'].decode())))
        rows = list(csv.DictReader(io.StringIO(explicit_files['forecast_rows.csv'].decode())))
        legacy_record = copy.deepcopy(manifest)
        legacy_record['legacy'] = True
        result = classify_forecast(legacy_record)
        return dict(audit_result='COMPLETED', legacy_path=LEGACY_ROOT,
                    exact_blob_checks='PASS', forecast_classification=result,
                    temporal_eligibility='UNPROVEN', actual_leakage_proven=None,
                    conclusion='Leakage cannot be ruled out / temporal eligibility is unproven; this does not prove leakage occurred.',
                    observed=dict(bundle_status=manifest.get('bundle_status'),
                                  legacy_blind_flag=manifest.get('blind_validation_eligible'),
                                  forecast_lock_utc=manifest.get('forecast_lock_utc'),
                                  engine_lane_config=lane.get('engine_lane_config'),
                                  forecast_row_count=len(rows), source_snapshot_rows=sources,
                                  bundled_forecast_rows_sha256=sha256(explicit_files['forecast_rows.csv'])),
                    missing=['upstream_source_capture_receipts', 'source_first_observed_utc',
                             'authenticated_capture_bindings', 'frozen_forecast_input_manifest',
                             'producer_and_distinct_engine_execution_proof',
                             'authenticated_lock_and_outcome_boundary_proof'],
                    engine_execution='NOT_PROVEN', production_blind_eligibility_certified=False,
                    trust=dict(TRUST), gate2b7_ready=False)
    except (KeyError, TypeError, ValueError, UnicodeError, csv.Error) as exc:
        return dict(audit_result='HOLD', reason=str(exc), production_blind_eligibility_certified=False,
                    actual_leakage_proven=None, trust=dict(TRUST), gate2b7_ready=False)
