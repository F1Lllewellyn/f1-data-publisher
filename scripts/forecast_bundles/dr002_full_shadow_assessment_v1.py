"""Read-only assessment of accepted live evidence; no production enforcement.

PROVEN_LIVE means the accepted adviser-inspected predecessor evidence, confirmed
against current GitHub metadata. It does not mean this module downloaded ZIPs,
authenticated issuers or established prospective forecast eligibility.
"""
import ast
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_forecast_integrity_receipts_v1 import canonical_json_bytes, sha256
from forecast_integrity_contract_v1 import classify_forecast
from dr002_lock_boundary_revision_v1 import TRUST

STATUSES=frozenset(('PROVEN_LIVE','CONTRACT_PROVEN_OFFLINE','NOT_PROVEN','HOLD','NOT_APPLICABLE'))
CHECKPOINT_SHA256='1df8cfba0a5aca49b5bca1fb054ec772614b7ce8bdab405fcdce4b7dcde605af'
ARTIFACTS={
 37133694090:dict(id=11277594100,name='dr002-weather-capture-37133694090-1',digest='sha256:df9ced90ba0df602d4e896c48292964ff812880f9a38dd5b4f0867da88ff6b6d'),
 37152568516:dict(id=11284482487,name='dr002-shadow-execution-37152568516-1',digest='sha256:92df37ad1a0c292b32f3f823ac5ae080399495a2251b75c1477b3967b12db507')}
HEADS={37133694090:'5f25e048edeb6e46a5a77e70c5c97857a59f6bb6',37152568516:'8d164fce63aea97aee7c2db71b6eb23d8f5e2055'}
PRODUCER_PATH='scripts/forecasts/produce_actual_forecast_rows_v1.py'
LOCKER_PATH='scripts/forecast_bundles/create_forecast_bundles_v1.py'
LAYERS=('source capture','temporal observation','event/session containment','frozen evidence','producer execution',
 'engine execution','forecast lock','outcome boundary','revision handling','blind eligibility',
 'external binding/authentication','historical availability','stable-engine provenance',
 'current production-producer containment','readiness for production enforcement')


def require(ok,reason):
    if not ok:raise ValueError(reason)


def blob_sha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def inspect_production(producer_bytes,locker_bytes):
    """Inspect AST only; never import or execute production code."""
    pt=ast.parse(producer_bytes);lt=ast.parse(locker_bytes)
    discovery=[];labels=[];blind=[]
    for node in ast.walk(pt):
        if isinstance(node,ast.FunctionDef) and node.name=='find_sources':
            discovery=[dict(function=node.name,line=c.lineno,operation='rglob') for c in ast.walk(node)
                if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='rglob']
    for node in ast.walk(lt):
        if isinstance(node,ast.Dict):
            for key,value in zip(node.keys,node.values):
                if isinstance(key,ast.Constant) and key.value=='stable_baseline' and isinstance(value,ast.Constant):
                    labels.append(dict(line=key.lineno,label=value.value))
                if isinstance(key,ast.Constant) and key.value=='blind_validation_eligible' and isinstance(value,ast.Name) and value.id=='source_found':
                    blind.append(dict(line=key.lineno,assignment='source_found'))
    return dict(broad_discovery=discovery,lane_labels=labels,source_found_blind=blind)


def assess(*, checkpoint_bytes, artifacts, runs, dependency_bytes, dependency_fingerprints,
           observed_main_sha, work_order_id='F1-WO-DR002-2B5-001'):
    """Pure deterministic API, explicit bytes/metadata only. No caller trust flags.

    Artifact metadata pins and accepted checkpoint reuse prior independent review.
    ZIP bytes are not inspected by this API; missing proofs remain NOT_PROVEN.
    No receipt or verified_receipt_binding is constructed.
    """
    rows=[];errors=[]
    def row(layer,status,claim,blocker):
        require(status in STATUSES,'invalid_status');rows.append(dict(layer=layer,status=status,strongest_defensible_claim=claim,blocker_or_limitation=blocker))
    try:
        require(isinstance(checkpoint_bytes,bytes) and sha256(checkpoint_bytes)==CHECKPOINT_SHA256,'accepted_checkpoint_changed')
        require(set(artifacts)==set(ARTIFACTS) and set(runs)==set(HEADS),'missing_or_extra_live_evidence')
        for rid,expected in ARTIFACTS.items():
            require(all(artifacts[rid].get(k)==v for k,v in expected.items()),'artifact_identity_or_digest_mismatch')
            require(artifacts[rid].get('expired') is False,'artifact_expired_or_unknown')
            require(runs[rid].get('id')==rid and runs[rid].get('head_sha')==HEADS[rid] and runs[rid].get('run_attempt')==1
                and runs[rid].get('event')=='workflow_dispatch' and runs[rid].get('conclusion')=='success','live_run_mismatch')
        require(bool(dependency_fingerprints) and len({d['path'] for d in dependency_fingerprints})==len(dependency_fingerprints),'ambiguous_fingerprints')
        for dep in dependency_fingerprints:
            require(blob_sha(dependency_bytes[dep['path']])==dep['blob_sha'],'dependency_changed:'+dep['path'])
        findings=inspect_production(dependency_bytes[PRODUCER_PATH],dependency_bytes[LOCKER_PATH])
        require(bool(findings['broad_discovery']) and bool(findings['lane_labels']) and bool(findings['source_found_blind']), 'production_inspection_changed_requires_review')
    except (ValueError,KeyError,TypeError,SyntaxError) as exc:
        errors.append(str(exc));findings={}
    live='HOLD' if errors else 'PROVEN_LIVE'
    basis='Accepted adviser-inspected Gate 2B-2B/3B2 evidence; current artifact metadata matches. No ZIP re-download.'
    for layer,claim in [('source capture','Exact source response captured/persisted/read back; 85 weather rows.'),
                        ('temporal observation','Observer first possession established only on 2026-10-03.'),
                        ('event/session containment','Single shadow source matched Baku meeting 1295 / session 11371.'),
                        ('frozen evidence','Explicit single receipt/content set hashed and contained.'),
                        ('producer execution','Weather execution-shadow output/code/input/receipt relationships independently reviewed.')]:
        row(layer,live,claim if not errors else 'Accepted live evidence invalidated or unavailable.',basis if not errors else '; '.join(errors))
    row('engine execution','NOT_PROVEN','No separate engine executed in accepted shadow.','All engine fields null; lane names are not execution proof.')
    for layer in ('forecast lock','outcome boundary','revision handling'):
        row(layer,'NOT_PROVEN','Gate 2B-4 contract proven offline; no live proof supplied.',
            'Live lock bytes/time/storage proof missing.' if layer=='forecast lock' else
            'Separate live outcome capture/boundary missing.' if layer=='outcome boundary' else
            'No live revision capture; completeness unproven.')
    classification=classify_forecast(dict(gate='post_event'))
    row('blind eligibility','NOT_APPLICABLE',classification['state'],'Historical post_event shadow is NOT A PREDICTION; cannot be blind.')
    row('external binding/authentication','NOT_PROVEN','UNBOUND; no production issuer/clock/storage authentication.','External binding interface is not authentication; no bindings fabricated.')
    row('historical availability','NOT_PROVEN','October observation does not prove earlier Baku availability.','Later API/artifact retrieval cannot backdate possession.')
    row('stable-engine provenance','NOT_PROVEN','No Engine_2026-06-07_STABLE execution proof.','Generic producer/lane configuration does not prove protected engine execution.')
    row('current production-producer containment','HOLD','Broad discovery risk found by source-code AST inspection.' if findings else 'Production inspection not established.',
        'find_sources recursive candidate lookup; existing bundle source_found blind assignment and stable lane label remain open.')
    row('readiness for production enforcement','HOLD','Assessment complete without production enforcement readiness.','Require replay/leakage evidence and separately approved authenticated full-chain enforcement proposal.')
    require(tuple(r['layer'] for r in rows)==LAYERS,'incomplete_matrix')
    return dict(schema_version='dr002-full-shadow-assessment-v1',work_order_id=work_order_id,observed_main_sha=observed_main_sha,
        assessment_result='HOLD' if errors else 'COMPLETED',invalidation_reasons=errors,matrix=rows,
        contract_capabilities=[dict(layer=x,status='CONTRACT_PROVEN_OFFLINE',basis='Accepted Gate 2B-4 / PR #129; 47 reviewed tests, not rerun here.') for x in ('forecast lock','outcome boundary','revision handling')],
        evidence_basis=basis,checkpoint_sha256=sha256(checkpoint_bytes),production_inspection=findings,
        integrity_classification=classification,trust=dict(TRUST),production_forecast_generated=False,
        gate2b6_started=False,gate2b7_started=False,
        next_decision='Review bounded Gate 2B-6 replay/leakage design; resolve authenticated capture/execution/lock/outcome/revision proof gaps before any separately approved Gate 2B-7 enforcement.')
