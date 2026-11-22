#!/usr/bin/env python3
"""Immutable Git receipts for Peak -> v22; never grant forecast authority.

Original committed bytes are the authority for an already consumed completion.
The working tree and 90-minute freshness gate remain mandatory for NEW processing.
Git history is read only; legacy receipts are verified in place, never rewritten.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

STATUS = 'latest/peak_elite/orchestrator_status.json'
CONSUMED = 'latest/1b_output_contract/verified_context_custody.json'

def git(repo, *args):
    p = subprocess.run(['git', *args], cwd=repo, capture_output=True, timeout=30)
    if p.returncode:
        raise ValueError('HOLD_GIT_CUSTODY_UNAVAILABLE')
    return p.stdout


def identity(value, consumer=False):
    keys = ('upstream_run_id','upstream_run_attempt') if consumer else ('github_run_id','github_run_attempt')
    pair = tuple(str(value.get(k,'')) for k in keys)
    if not all(re.fullmatch(r'[1-9][0-9]*', v) for v in pair):
        raise ValueError('HOLD_RECEIPT_IDENTITY_INVALID')
    return pair


def receipt_path(pair, consumer=False):
    root = '1b_output_contract_receipts' if consumer else 'peak_elite_receipts'
    return f'history/{root}/{pair[0]}/{pair[1]}/receipt.json'


def append_receipt(repo, value, consumer=False):
    path = repo / receipt_path(identity(value, consumer), consumer)
    raw = (json.dumps(value, indent=2, sort_keys=True)+'\n').encode()
    if path.exists() or path.is_symlink():
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError('HOLD_IMMUTABLE_RECEIPT_COLLISION')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)


def read_at(repo, commit, path):
    if (not isinstance(path,str) or Path(path).is_absolute() or '..' in Path(path).parts
            or not path.startswith(('latest/','history/'))):
        raise ValueError('HOLD_RECEIPT_UNSAFE_PATH')
    entry = git(repo, 'ls-tree', commit, '--', path).decode()
    if not entry.startswith('100644 blob ') or not entry.rstrip().endswith('\t'+path):
        raise ValueError('HOLD_RECEIPT_BLOB_MISSING_OR_UNSAFE')
    raw = git(repo, 'show', f'{commit}:{path}')
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError('HOLD_RECEIPT_BYTE_LIMIT')
    return raw


def find(repo, pair, consumer=False, since=None):
    """Find exact original bytes, including deployed pre-receipt Git publications."""
    immutable = receipt_path(pair, consumer)
    revisions = git(repo, 'log', '-2', '--format=%H', '--', immutable).decode().splitlines()
    if revisions:
        if len(revisions) != 1:
            raise ValueError('HOLD_IMMUTABLE_RECEIPT_HISTORY_MUTATION')
        raw = read_at(repo, revisions[0], immutable)
        if not (repo/immutable).is_file() or (repo/immutable).is_symlink() or (repo/immutable).read_bytes()!=raw:
            raise ValueError('HOLD_IMMUTABLE_RECEIPT_CHANGED_OR_MISSING')
        value = json.loads(raw)
        if identity(value,consumer)!=pair:
            raise ValueError('HOLD_IMMUTABLE_RECEIPT_IDENTITY')
        return revisions[0], value
    legacy = CONSUMED if consumer else STATUS
    found = None
    # Bounded compatibility reader. New receipts never require a historical scan.
    limits = ['--since='+since] if since else []
    for commit in git(repo,'log','-64','--format=%H',*limits,'--',legacy).decode().splitlines():
        value = json.loads(read_at(repo,commit,legacy))
        try:
            matches = identity(value,consumer)==pair
        except ValueError:
            continue
        if found and not matches:
            break
        if matches:
            if found and value != found[1]:
                raise ValueError('HOLD_LEGACY_RECEIPT_MUTATION')
            found = (commit,value)
    return found


def snapshot(repo, commit, status, destination, receipt=None):
    bindings = status.get('handoff_fingerprints')
    if not isinstance(bindings,dict) or not bindings:
        raise ValueError('HOLD_SOURCE_RECEIPT_MISSING_BINDINGS')
    bindings = dict(bindings)
    if receipt:
        if receipt.get('consumed_fingerprints') != status.get('handoff_fingerprints'):
            raise ValueError('HOLD_RECEIPT_INPUT_BINDINGS_CHANGED')
        bindings.update(receipt.get('output_fingerprints',{}))
    if len(bindings)>256:
        raise ValueError('HOLD_RECEIPT_PATH_LIMIT')
    total=0
    for path,sha in bindings.items():
        if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):
            raise ValueError('HOLD_RECEIPT_INVALID_DIGEST')
        raw=read_at(repo,commit,path); total+=len(raw)
        if total>64*1024*1024 or hashlib.sha256(raw).hexdigest()!=sha:
            raise ValueError('HOLD_ORIGINAL_BYTES_CHANGED_OR_MISSING')
        if path.startswith('history/'):
            if hashlib.sha256(read_at(repo,'HEAD',path)).hexdigest()!=sha:
                raise ValueError('HOLD_HISTORICAL_BYTES_CHANGED_OR_MISSING')
            sparse=git(repo,'ls-files','-v','--',path).startswith(b'S ')
            if (not sparse or (repo/path).exists()) and (not (repo/path).is_file() or (repo/path).is_symlink()
                    or hashlib.sha256((repo/path).read_bytes()).hexdigest()!=sha):
                raise ValueError('HOLD_HISTORICAL_BYTES_CHANGED_OR_MISSING')
        out=destination/path; out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(raw)
    selector=json.loads((destination/'latest/latest_manifest.json').read_text())
    ledger=str(Path(selector['latest_session_data_processor_manifest']).with_name('forecast_bundle_ledger_snapshot.json'))
    if ledger not in bindings:
        # Legacy receipts predate explicit ledger binding. Use only the same
        # original Git tree; the existing verifier still checks every identity.
        raw=read_at(repo,commit,ledger)
        out=destination/ledger;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw)
    schedule=selector.get('session_schedule_snapshot')
    if schedule:
        raw=read_at(repo,commit,schedule)
        if hashlib.sha256(raw).hexdigest()!=selector.get('session_schedule_sha256'):
            raise ValueError('HOLD_SCHEDULE_BINDING_CHANGED')
        out=destination/schedule;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw)
    for path,value in ((STATUS,status),(CONSUMED,receipt)):
        if value is not None:
            out=destination/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(value))


def diagnostic(action, reasons, status=None, **extra):
    state=(status or {}).get('latest_state',{})
    return dict(action=action, status='HOLD' if action=='HOLD' else 'VERIFIED_CONTEXT_ONLY' if action in
                ('PROCESS','NOOP_ALREADY_VERIFIED') else 'SOURCE_HOLD',
        operational_status='OPERATIONAL_FAIL' if action=='HOLD' else 'OPERATIONAL_PASS',
        source_status='VERIFIED' if action in ('PROCESS','NOOP_ALREADY_VERIFIED') else 'HOLD',
        scientific_status='HOLD_STABLE_ENGINE_NOT_EXECUTED', reasons=reasons, reason_codes=reasons,
        original_run_id=(status or {}).get('github_run_id'),
        upstream_run_id=(status or {}).get('github_run_id'),
        upstream_run_attempt=(status or {}).get('github_run_attempt'),
        upstream_head_sha=(status or {}).get('workflow_head_sha'),
        event_id=state.get('event_id'),session_key=state.get('session_key'),
        promotion_allowed=False,scientific_eligible=False,stable_engine_executed=False,prediction_locked=False, **extra)


def reconcile(repo, peak, now):
    status={}
    try:
        latest=peak.read_json(repo/STATUS,{})
        native=os.environ.get('GITHUB_EVENT_NAME')=='workflow_run'
        pair=(os.environ.get('UPSTREAM_RUN_ID',''),os.environ.get('UPSTREAM_RUN_ATTEMPT','')) if native else identity(latest)
        if not all(re.fullmatch(r'[1-9][0-9]*',p) for p in pair):
            raise ValueError('HOLD_RECEIPT_IDENTITY_INVALID')
        original=find(repo,pair)
        if original is None:
            # No capture was published (e.g. scheduled admission NOOP). Authenticate
            # the native event; absence of a receipt can never admit a consumer.
            if not native:
                raise ValueError('HOLD_ORIGINAL_RECEIPT_MISSING')
            info=peak.fetch_original_run(pair[0])
            status=dict(github_run_id=pair[0],github_run_attempt=pair[1],workflow_head_sha=os.environ.get('UPSTREAM_HEAD_SHA'),created_utc=info.get('run_started_at'))
            with tempfile.TemporaryDirectory() as t:
                root=Path(t);peak.write_json(root/STATUS,status)
                check=peak.verify_bridge_origin(root,now,input_result={'reasons':[]})
            if check['reasons']:
                return diagnostic('HOLD',check['reasons'],status)
            return diagnostic('NOOP_NO_ELIGIBLE_CAPTURE',['HOLD_NO_ORIGINAL_CAPTURE_RECEIPT'],status)
        commit,status=original
        for field,env in (('github_run_id','UPSTREAM_RUN_ID'),('github_run_attempt','UPSTREAM_RUN_ATTEMPT'),('workflow_head_sha','UPSTREAM_HEAD_SHA')):
            if (native or os.environ.get(env)) and str(status.get(field))!=os.environ.get(env):
                raise ValueError('HOLD_UPSTREAM_RUN_MISMATCH:'+field)
        # Current status for this same run is a view of its original receipt.
        if (str(latest.get('github_run_id')),str(latest.get('github_run_attempt')))==pair and latest!=status:
            raise ValueError('HOLD_ORIGINAL_STATUS_VIEW_CHANGED')
        created=dt.datetime.fromisoformat(status['created_utc'].replace('Z','+00:00'))
        if created.tzinfo is None or created>now:
            raise ValueError('HOLD_ORIGINAL_REPORT_CLOCK_INVALID')
        prior=find(repo,pair,consumer=True,since=(created-dt.timedelta(minutes=5)).isoformat())
        with tempfile.TemporaryDirectory(prefix='f1-receipt-') as t:
            root=Path(t)
            snapshot(repo,prior[0] if prior else commit,status,root,prior[1] if prior else None)
            origin=peak.verify_bridge_origin(root,now,input_result={'reasons':[]})
            if origin['reasons']:
                return diagnostic('HOLD',origin['reasons'],status)
            if prior:
                receipt=prior[1]
                current=peak.read_json(repo/CONSUMED,{})
                if (str(current.get('upstream_run_id')),str(current.get('upstream_run_attempt')))==pair:
                    if current!=receipt or peak.byte_fingerprints(repo,receipt.get('output_fingerprints',{}))!=receipt.get('output_fingerprints'):
                        raise ValueError('HOLD_ACCEPTED_RECEIPT_OR_OUTPUT_CHANGED')
                # Historical acceptance time is evidence for an old acceptance,
                # NEVER a replacement clock for a new forecast/capture/consumer.
                times=[dt.datetime.fromisoformat(json.loads((root/p).read_text())['generated_at_utc'].replace('Z','+00:00')) for p in receipt.get('output_fingerprints',{})]
                accepted=max(times)
                if accepted>now:
                    raise ValueError('HOLD_RECEIPT_ACCEPTANCE_IN_FUTURE')
                marker=root/'_runtime/1b_output_contract/start.marker';marker.parent.mkdir(parents=True);marker.touch();os.utime(marker,(1,1))
                check=peak.verify_bridge_output(root,accepted)
                if check['reasons'] or receipt.get('status')!='VERIFIED_CONTEXT_ONLY' or receipt.get('reasons')!=[] or any(receipt.get(k) is not False for k in ('promotion_allowed','stable_engine_executed','prediction_locked')):
                    return diagnostic('HOLD',check['reasons'] or ['HOLD_INVALID_ACCEPTED_RECEIPT'],status)
                return diagnostic('NOOP_ALREADY_VERIFIED',[],status,original_publication_commit=prior[0])
            if status.get('failed_steps')!=[]:
                return diagnostic('HOLD',['HOLD_ORIGINAL_STAGE_FAILED'],status)
            if status.get('downstream_current') is not True:
                return diagnostic('NOOP_NO_ELIGIBLE_CAPTURE',['HOLD_ORIGINAL_SOURCE_NOT_ELIGIBLE'],status,source_hold_reasons=status.get('dashboard_readiness_reasons',[]))
        # A never-consumed completion must still be fresh, current and unchanged.
        check=peak.verify_bridge_origin(repo,now)
        if check['reasons']:
            if check['reasons']==['HOLD_UPSTREAM_TIME_INVALID_OR_STALE']:
                return diagnostic('NOOP_NO_ELIGIBLE_CAPTURE',check['reasons'],status)
            return diagnostic('HOLD',check['reasons'],status)
        return diagnostic('PROCESS',[],status,original_publication_commit=commit)
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as exc:
        reason=str(exc) if isinstance(exc,ValueError) and str(exc).startswith('HOLD_') else 'HOLD_RECEIPT_VERIFICATION:'+type(exc).__name__
        return diagnostic('HOLD',[reason],status)
