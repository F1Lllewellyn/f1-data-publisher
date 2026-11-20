#!/usr/bin/env python3
"""Shared direct-route scientific boundary; read-only candidate assessment.

No approved protected-engine executable/external execution binding is available.
Candidate manifests describe claims, not trust. This module never authenticates a
self-supplied receipt, activates DR-002, invokes a model, or creates a prediction.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re

GATES = ['pre_weekend', 'post_fp3', 'post_qualifying', 'race_result', 'post_event']
LANES = ['stable_baseline', 'control_room_overlay', 'experimental_challenger']
SOURCE_PATTERNS = ['latest/forecasts/{event_id}/{gate}/{lane}/forecast_rows.csv',
                   'latest/forecast_outputs/{event_id}/{gate}/{lane}/forecast_rows.csv',
                   'latest/method_e_control_room/forecasts/{event_id}/{gate}/{lane}.csv']
REQUIREMENTS = [
    'independently authenticated original engine executable and invocation contract',
    'verified original run/head/attempt and source bytes with observation clocks',
    'official FIA final/revised grid authority when required by the product',
    'explicit evidence cutoff, generation deadline and outcome boundary',
    'independently verified execution/input/output receipt bindings',
    'separate prospective execution and immutable-lock authorization',
]

class ScientificHold(RuntimeError):
    pass


def now_utc():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')


def identity(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',value):
        raise ScientificHold('HOLD_INVALID_FORECAST_IDENTITY')
    return value


def clock(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z',value):
        raise ScientificHold('HOLD_SOURCE_AVAILABILITY_CLOCK_NOT_RETAINED')
    try:return dt.datetime.fromisoformat(value[:-1]+'+00:00')
    except ValueError as exc:raise ScientificHold('HOLD_INVALID_FORECAST_CLOCK') from exc


def contained(root, relative):
    root=root.resolve(); path=root/relative
    if (Path(relative).is_absolute() or '..' in Path(relative).parts
            or not path.resolve().is_relative_to(root)
            or any(p.is_symlink() for p in (path,*path.parents))):
        raise ScientificHold('HOLD_FORECAST_PATH_CUSTODY')
    return path


def digest(raw):return hashlib.sha256(raw).hexdigest()


def require_forecast_authority(event_id, gate, lane):
    """No flag, lane label, local receipt or environment variable grants authority.

    The missing trust adapter cannot safely be invented under Issue367. A future
    reviewed implementation must authenticate the accepted original model and
    independent receipt bindings before replacing this explicit boundary.
    """
    identity(event_id)
    if gate not in GATES or lane not in LANES:
        raise ScientificHold('HOLD_INVALID_FORECAST_PRODUCT')
    if gate in {'race_result','post_event'}:
        raise ScientificHold('HOLD_POST_OUTCOME_NOT_PROSPECTIVE')
    if lane=='stable_baseline':
        raise ScientificHold('HOLD_STABLE_ENGINE_NOT_EXECUTED')
    raise ScientificHold('HOLD_FORECAST_EXECUTION_AUTHORITY_MISSING')


def inspect_candidate(repo, source, event_id, gate, lane, now=None):
    """Check bytes and chronology only. Never confers scientific eligibility."""
    identity(event_id)
    source=contained(repo,str(source.relative_to(repo)))
    manifest=source.with_name('forecast_execution_manifest.json')
    if not source.is_file() or not manifest.is_file():
        raise ScientificHold('HOLD_ORIGINAL_EXECUTION_CUSTODY_NOT_RETAINED')
    contained(repo,str(manifest.relative_to(repo)))
    raw=source.read_bytes(); receipt_raw=manifest.read_bytes()
    try:doc=json.loads(receipt_raw)
    except (ValueError,UnicodeError) as exc:raise ScientificHold('HOLD_EXECUTION_MANIFEST_MALFORMED') from exc
    if (doc.get('schema')!='f1-forecast-execution-candidate-v1'
            or any(doc.get(k)!=v for k,v in dict(event_id=event_id,gate=gate,engine_lane=lane).items())):
        raise ScientificHold('HOLD_FORECAST_EVENT_MODEL_IDENTITY')
    for key in ('meeting_key','session_key'):
        if type(doc.get(key)) is not int or doc[key]<=0:raise ScientificHold('HOLD_FORECAST_SESSION_IDENTITY')
    origin=doc.get('capture_origin',{})
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',str(origin.get('repository','')))
            or not re.fullmatch(r'[0-9a-f]{40}',str(origin.get('head_sha','')))
            or not str(origin.get('run_id','')).isdigit() or int(origin['run_id'])<=0
            or not str(origin.get('run_attempt','')).isdigit() or int(origin['run_attempt'])<=0):
        raise ScientificHold('HOLD_ORIGINAL_RUN_IDENTITY')
    invocation=doc.get('invocation',{})
    if (not invocation.get('execution_id') or not invocation.get('engine_implementation')
            or not re.fullmatch(r'[0-9a-f]{64}',str(invocation.get('engine_code_sha256','')))):
        raise ScientificHold('HOLD_ENGINE_INVOCATION_IDENTITY')
    cutoff=clock(doc.get('evidence_cutoff_utc')); generation=clock(doc.get('forecast_generation_utc'))
    started=clock(invocation.get('started_utc')); completed=clock(invocation.get('completed_utc'))
    deadline=clock(doc.get('forecast_deadline_utc')); outcome=clock(doc.get('outcome_boundary_utc'))
    observed_now=clock(now or now_utc())
    if not cutoff<=started<=completed<=generation<=observed_now<deadline<=outcome:
        raise ScientificHold('HOLD_FORECAST_TEMPORAL_ELIGIBILITY')
    inputs=doc.get('inputs'); hashes={}
    if not isinstance(inputs,list) or not inputs:raise ScientificHold('HOLD_FORECAST_INPUTS_MISSING')
    for source_input in inputs:
        relative=source_input.get('path','');path=contained(repo,relative)
        if (relative in hashes or not path.is_file() or not source_input.get('source_id')
                or source_input.get('meeting_key')!=doc['meeting_key']
                or source_input.get('session_key') not in doc.get('allowed_session_keys',[])):
            raise ScientificHold('HOLD_FORECAST_INPUT_IDENTITY')
        if clock(source_input.get('observed_at_utc'))>cutoff:
            raise ScientificHold('HOLD_SOURCE_AVAILABLE_AFTER_CUTOFF')
        hashes[relative]=digest(path.read_bytes())
        if hashes[relative]!=source_input.get('sha256'):raise ScientificHold('HOLD_FORECAST_INPUT_BYTES')
    if invocation.get('input_manifest_sha256')!=digest(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()):
        raise ScientificHold('HOLD_INVOCATION_INPUT_MANIFEST')
    if doc.get('forecast_sha256')!=digest(raw) or invocation.get('output_sha256')!=digest(raw):
        raise ScientificHold('HOLD_FORECAST_OUTPUT_BYTES')
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    roster=doc.get('driver_numbers',[])
    if not roster or any(type(d) is not int or d<=0 for d in roster) or len(roster)!=len(set(roster)):
        raise ScientificHold('HOLD_FORECAST_DRIVER_ROSTER')
    if len(rows)!=len(roster):raise ScientificHold('HOLD_FORECAST_ROW_COVERAGE')
    drivers=[]
    for row in rows:
        if any(row.get(k)!=v for k,v in dict(event_id=event_id,gate=gate,engine_lane=lane,forecast_timestamp_utc=doc['forecast_generation_utc']).items()):
            raise ScientificHold('HOLD_FORECAST_ROW_IDENTITY_OR_CLOCK')
        if row.get('forecast_lock_utc'):raise ScientificHold('HOLD_EXISTING_LOCK_CANNOT_BE_RELOCKED')
        if not str(row.get('driver_number','')).isdigit():raise ScientificHold('HOLD_FORECAST_DRIVER_IDENTITY')
        drivers.append(int(row['driver_number']))
    if set(drivers)!=set(roster) or len(drivers)!=len(set(drivers)):raise ScientificHold('HOLD_FORECAST_DRIVER_IDENTITY')
    return dict(manifest=doc,source_path=str(source.relative_to(repo)),source_sha256=digest(raw),
                manifest_sha256=digest(receipt_raw),input_fingerprints=hashes,
                forecast_eligible=False,production_authenticated=False)


def verify_candidate(repo, source, event_id, gate, lane, now=None):
    require_forecast_authority(event_id,gate,lane)
    # Unreachable until a separately reviewed trust adapter exists. No local
    # manifest is accepted as the external authority required above.
    return inspect_candidate(repo,source,event_id,gate,lane,now)


def immutable_directory(path, files):
    """Exact duplicate is a no-op; collision cannot overwrite any existing byte."""
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ScientificHold('HOLD_IMMUTABLE_OUTPUT_PATH')
    if path.exists():
        if not path.is_dir() or any(p.is_symlink() for p in path.rglob('*')):
            raise ScientificHold('HOLD_IMMUTABLE_OUTPUT_PATH')
        actual={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}
        if actual!=files:raise ScientificHold('HOLD_IMMUTABLE_FORECAST_COLLISION')
        return False
    for name,raw in files.items():
        if not isinstance(raw,bytes) or Path(name).name!=name or name in {'.','..'}:
            raise ScientificHold('HOLD_IMMUTABLE_OUTPUT_PATH')
    path.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive directory claim prevents concurrent replacement. Partial work is
    # retained on failure and is a HOLD on restart, never overwritten/backfilled.
    path.mkdir()
    for name,raw in files.items():
        with (path/name).open('xb') as handle:handle.write(raw)
    return True


def hold_report(repo,event_id,gate,lane,reason):
    report=dict(status='HOLD',reason=reason,event_id=event_id,gate=gate,lane=lane,
        observed_at_utc=now_utc(),stable_engine_executed=False,prediction_locked=False,
        blind_validation_eligible=False,forecast_eligible=False,production_authenticated=False,
        dr002_activated=False,promotion_allowed=False,requirements=REQUIREMENTS)
    # Artifact-only diagnostics; no latest/history/source/forecast mutation.
    raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode()
    target=contained(repo,'_runtime/forecast_scientific_hold/'+digest(raw)+'.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        with target.open('xb') as handle:handle.write(raw)
    print(json.dumps(report,indent=2))
    return 2


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',default='.')
    ap.add_argument('--event-id',required=True)
    ap.add_argument('--gate',default='all',choices=GATES+['all'])
    ap.add_argument('--lane',default='all',choices=LANES+['all'])
    ap.add_argument('--strict',action='store_true')
    ap.add_argument('--preflight-only',action='store_true')
    args=ap.parse_args();repo=Path(args.repo).resolve()
    gate=GATES[0] if args.gate=='all' else args.gate
    lane=LANES[0] if args.lane=='all' else args.lane
    try:require_forecast_authority(args.event_id,gate,lane)
    except ScientificHold as exc:return hold_report(repo,args.event_id,args.gate,args.lane,str(exc))
    raise ScientificHold('HOLD_NO_APPROVED_EXECUTION_ADAPTER')

if __name__=='__main__':raise SystemExit(main())
