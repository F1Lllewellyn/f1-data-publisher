"""Isolated retrospective weather execution shadow. NOT A PREDICTION; UNBOUND."""
import argparse
from datetime import datetime
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_forecast_integrity_receipts_v1 import (canonical_json_bytes, sha256,
    receipt_sha256, validate_receipt_envelope, verify_temporal_bindings, VERSION)
from dr002_frozen_evidence_manifest_v1 import (build_frozen_evidence_manifest,
    validate_frozen_evidence_manifest, strict_json)
from forecast_integrity_contract_v1 import input_manifest_sha256

IMPLEMENTATION = 'scripts/forecast_bundles/dr002_shadow_producer_execution_v1.py'
CODE_PATHS = tuple(sorted((IMPLEMENTATION,
    'scripts/forecast_bundles/dr002_frozen_evidence_manifest_v1.py',
    'scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py',
    'scripts/forecast_bundles/forecast_integrity_contract_v1.py')))
SCOPE = dict(event_id='2026_1295_azerbaijan_baku_baku', meeting_id='1295', session_id='11371')
SOURCE = 'openf1:weather:1295:11371'
URI = 'https://api.openf1.org/v1/weather?session_key=11371'
PINS = dict(source_sha256='bdd5e108329c896f2e1b7bded170e00ff3dbecb7ec76663e7d86f7bb87aeeae6',
    receipt_sha256='1cae5a9cf6a10491b88cc05221db65d5790fdc1128cd5c58909cd097a389e42d',
    receipt_id='source_capture:5b0c88919ac0fa608e4b6f00ab801742e36c0e6c00acaeee183a30576e5ec9d9')
PRODUCT = dict(product_id='dr002_integrity_shadow_weather',
    product_contract_id='dr002-shadow-weather-execution-v1', gate='post_event', lane_name='shadow_execution_only')
TRUST = dict(binding_status='UNBOUND', production_authenticated=False,
    historical_availability_proven=False, dr002_activated=False)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def utc(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z', value), 'invalid_utc')
    return datetime.fromisoformat(value[:-1] + '+00:00')


def clock():
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def code_manifest(paths, reader):
    require(set(paths) == set(CODE_PATHS), 'wrong_code_files')
    return [dict(path=p, sha256=sha256(reader(paths[p]))) for p in CODE_PATHS]


def execution_identity(payload):
    keys = ('implementation', 'git_commit', 'code_sha256', 'input_manifest_sha256',
            'input_receipt_manifest_sha256', 'forecast_payload_sha256', 'forecast_generation_utc')
    return 'producer_execution:' + sha256(canonical_json_bytes({k:payload[k] for k in keys}))


def execute(receipt_path, content_path, capture_manifest_path, *, git_commit, run_id,
            runtime_root=Path('_runtime/dr002_gate2b3b_shadow'), clock_fn=clock,
            reader=lambda p: Path(p).read_bytes(), writer=write,
            publisher=lambda a,b: a.rename(b), code_paths=None,
            _capture_pins=PINS):
    """Explicit offline inputs. Synthetic pins are test injection, not authentication.

    CLI has no pin override. Output must be a new runtime directory. Git SHA is
    supplied execution context, not independently authenticated here.
    """
    require(re.fullmatch('[0-9a-f]{40}', git_commit or '') is not None, 'invalid_git_commit')
    require(re.fullmatch('[A-Za-z0-9_-]+', run_id or '') is not None, 'invalid_run_id')
    root = Path(runtime_root) / run_id
    require('_runtime' in root.parts and not root.exists(), 'new_runtime_directory_required')
    root.mkdir(parents=True)
    final = root / 'receipts/producer_execution_receipt.json'
    try:
        receipt_bytes = reader(receipt_path)
        raw = reader(content_path)
        capture = strict_json(reader(capture_manifest_path))
        receipt = strict_json(receipt_bytes)
        validate_receipt_envelope(receipt); verify_temporal_bindings(receipt)
        require(receipt['receipt_type'] == 'source_capture' and receipt['parent_receipt_ids'] == [], 'wrong_capture_type')
        require(receipt['scope'] == SCOPE, 'wrong_scope')
        p = receipt['payload']
        require(p['source_id'] == SOURCE and p['source_uri'] == URI, 'wrong_source')
        require(p['event_time_utc'] is None and p['publisher_time_utc'] is None, 'invented_source_time')
        require(receipt['receipt_id'] == _capture_pins['receipt_id'], 'wrong_receipt_id')
        require(sha256(raw) == p['source_sha256'] == _capture_pins['source_sha256'], 'wrong_source_hash')
        require(receipt_sha256(receipt) == _capture_pins['receipt_sha256'], 'wrong_receipt_hash')
        require(capture['validation_status'] == 'CAPTURED_UNBOUND', 'capture_not_successful')
        for k,v in {**SCOPE, **TRUST, 'source_sha256':p['source_sha256'],
                    'receipt_sha256':receipt_sha256(receipt)}.items():
            require(capture.get(k) == v and (not isinstance(v,bool) or capture.get(k) is v), 'capture_mismatch_' + k)
        require(capture['first_observed_utc'] == p['first_observed_utc'] == capture['response_completed_utc'], 'observation_mismatch')
        require(capture['ingested_utc'] == p['ingested_utc'] and capture['receipt_created_utc'] == receipt['receipt_created_utc'], 'capture_time_mismatch')
        require(utc(capture['request_started_utc']) <= utc(p['first_observed_utc']), 'capture_time_order')
        require(capture['readback_verified'] is True and capture['readback_sha256'] == sha256(raw), 'capture_readback_mismatch')
        rows = strict_json(raw)
        require(isinstance(rows,list) and bool(rows) and all(isinstance(r,dict) for r in rows), 'invalid_weather_list')
        for row in rows:
            require(str(row.get('session_key')) == SCOPE['session_id'] and str(row.get('meeting_key')) == SCOPE['meeting_id'], 'weather_scope_mismatch')
        require(capture['byte_count'] == len(raw) and capture['row_count'] == len(rows), 'capture_count_mismatch')
        # Frozen builder reads only this pair. Reuse verified in-memory bytes to
        # avoid time-of-check/time-of-use changes in source files.
        supplied = {str(receipt_path):receipt_bytes, str(content_path):raw}
        frozen = build_frozen_evidence_manifest(dict(event_id=SCOPE['event_id'], meeting_id=SCOPE['meeting_id'],
            allowed_session_ids=['11371'], captures=[dict(receipt_path=str(receipt_path), content_path=str(content_path))]),
            read_bytes=lambda path:supplied[path])
        require(validate_frozen_evidence_manifest(frozen) is True, 'invalid_frozen_manifest')
        generation = clock_fn()
        require(utc(generation) >= utc(receipt['receipt_created_utc']), 'generation_before_capture')
        forecast_id = 'shadow_weather:' + sha256(canonical_json_bytes(dict(run_id=run_id, source_receipt_id=receipt['receipt_id'], **PRODUCT)))
        evidence = {k:p[k] for k in ('source_id','source_uri','source_sha256','event_time_utc','publisher_time_utc','first_observed_utc','ingested_utc')}
        evidence.update(SCOPE, ingestion_required_at_cutoff=False, capture_evidence_ref=receipt['receipt_id'])
        contract = dict(forecast_id=forecast_id, **PRODUCT, **SCOPE, allowed_session_ids=['11371'],
            evidence_cutoff_utc=p['first_observed_utc'], forecast_deadline_utc=generation,
            mandatory_source_ids=[SOURCE], revision_policy='none', evidence=[evidence])
        input_hash = input_manifest_sha256(contract)
        require(input_hash == sha256(canonical_json_bytes(contract)), 'input_manifest_hash_mismatch')
        repo_root = Path(__file__).resolve().parents[2]
        paths = code_paths if code_paths is not None else {x:repo_root/x for x in CODE_PATHS}
        codes = code_manifest(paths, reader)
        code_hash = sha256(canonical_json_bytes(codes))
        output = dict(schema_version='dr002-shadow-producer-output-v1',
            status='SHADOW_EXECUTION_ONLY_NOT_A_PREDICTION', integrity_classification='OUTCOME_AWARE_EVALUATION_ONLY',
            execution_mode='retrospective_shadow', contract_approved=False, **PRODUCT, **SCOPE,
            frozen_evidence_manifest_sha256=frozen['frozen_evidence_manifest_sha256'],
            input_receipt_manifest_sha256=frozen['manifest']['input_receipt_manifest_sha256'],
            input_manifest_sha256=input_hash, source_id=SOURCE, source_sha256=p['source_sha256'],
            source_row_count=len(rows), source_first_observed_utc=p['first_observed_utc'],
            production_forecast_generated=False, stable_engine_executed=False, dr002_activated=False)
        def persist(relative, value):
            data=canonical_json_bytes(value); path=root/relative
            writer(path,data); require(reader(path)==data, 'readback_mismatch_' + relative)
            return data
        persist('source/frozen_evidence_manifest.json', frozen)
        persist('contract/shadow_input_manifest.json', contract)
        persist('implementation/code_manifest.json', codes)
        encoded = persist('output/shadow_producer_output.json', output)
        payload = dict(implementation=IMPLEMENTATION, git_commit=git_commit, code_sha256=code_hash,
            forecast_generation_utc=generation, input_manifest_sha256=input_hash,
            input_receipt_manifest_sha256=output['input_receipt_manifest_sha256'], forecast_payload_sha256=sha256(encoded),
            engine_implementation=None, engine_receipt_id=None, engine_result_sha256=None)
        payload['execution_id']=execution_identity(payload)
        created = clock_fn()
        require(utc(created)>=utc(generation), 'receipt_before_generation')
        produced=dict(schema_version=VERSION, receipt_id=payload['execution_id'], receipt_type='producer_execution',
            receipt_created_utc=created, scope=dict(**SCOPE, **{k:PRODUCT[k] for k in ('product_id','gate','lane_name')},forecast_id=forecast_id),
            parent_receipt_ids=[receipt['receipt_id']], payload=payload)
        require(validate_receipt_envelope(produced) is True, 'invalid_producer_receipt')
        verify_temporal_bindings(produced)
        persist('receipts/receipt_candidate.diagnostic.json', produced)
        manifest=dict(schema_version='dr002-shadow-execution-manifest-v1', status='SHADOW_EXECUTION_ONLY_NOT_A_PREDICTION',
            run_id=run_id, execution_mode='retrospective_shadow', contract_approved=False, **TRUST,
            integrity_classification='OUTCOME_AWARE_EVALUATION_ONLY', forecast_generation_utc=generation,
            receipt_sha256=receipt_sha256(produced), producer=payload,
            frozen_evidence_manifest_sha256=frozen['frozen_evidence_manifest_sha256'])
        persist('execution_manifest.json', manifest)
        writer(root/'shadow_report.md', b'# Outcome-aware execution shadow\n\nNOT A PREDICTION. UNBOUND. No authentication or historical availability proof.\nShadow execution boundary only; not a historical prediction deadline.\n')
        publisher(root/'receipts/receipt_candidate.diagnostic.json', final)
        return manifest
    except Exception as exc:
        # Diagnostics are best effort; never convert failure into success.
        try: writer(root/'hold.diagnostic.json', canonical_json_bytes(dict(status='HOLD', reason=str(exc))))
        except Exception: pass
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('source-receipt','raw-source','capture-manifest','implementation-git-sha','run-id'):
        parser.add_argument('--'+arg,required=True)
    args=parser.parse_args()
    try:
        execute(args.source_receipt,args.raw_source,args.capture_manifest,git_commit=args.implementation_git_sha,run_id=args.run_id)
    except Exception as exc:
        print('HOLD: '+str(exc),file=sys.stderr); return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
