#!/usr/bin/env python3
"""Direct forecast custody boundary and exclusive candidate storage.

An original authenticated execution and separate prospective lock authorization
are required before any write. Neither currently exists for the protected model.
Self-supplied receipts, lane labels, row presence and placeholder flags do not
satisfy that boundary. Historical predictions are never re-locked or overwritten.
Candidate storage helpers do not grant scientific lock or blind eligibility.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, os, shutil
from pathlib import Path

def load_custody_guard():
    import importlib.util
    path=Path(__file__).resolve().with_name('validate_forecast_chain_readiness_v1.py')
    spec=importlib.util.spec_from_file_location('direct_forecast_custody',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

custody_guard=load_custody_guard()


GATES = ["pre_weekend", "post_fp3", "post_qualifying", "race_result", "post_event"]
LANES = {
    "stable_baseline": "StableBaseline_LanePolicy_v1",
    "control_room_overlay": "MethodE_ControlRoom_Overlay",
    "experimental_challenger": "Integrated_Recalibrated_Specialist_Challenger",
}
REQUIRED = [
    "bundle_lock_manifest.json","forecast_rows.csv","source_snapshot_manifest.csv","engine_lane_config.json",
    "forecast_attribution.csv","stable_vs_challenger_delta.csv","method_e_proof_loop_gate_record.json",
    "promotion_gate_metadata.json","scoring_placeholder.csv","bundle_completeness_check.csv","README.md"
]
FORECAST_COLS = ['bundle_id','bundle_status','event_id','season','round','race_name','gate','engine_lane','engine_lane_config','forecast_timestamp_utc','forecast_lock_utc','session_scope','driver_number','driver_name','team_name','predicted_qualifying_position','predicted_race_finish_position','predicted_points_band','predicted_dnf_probability','predicted_top1_probability','predicted_top3_probability','predicted_top5_probability','predicted_top10_probability','predicted_mean_finish_position','confidence_score','risk_flags','source_snapshot_id','forecast_artifact_id','stable_vs_challenger_delta_note','method_e_attribution_note','promotion_gate_eligible','notes']


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c:r.get(c,'') for c in cols})


def count_csv_rows(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    try:
        with path.open('r', newline='', encoding='utf-8') as f:
            reader=csv.DictReader(f)
            return sum(1 for _ in reader)
    except Exception:
        return 0


def candidate_sources(root: Path, event_id: str, gate: str, lane: str, include_existing_bundles: bool=True):
    sources = [
        root / 'latest' / 'forecasts' / event_id / gate / lane / 'forecast_rows.csv',
        root / 'latest' / 'method_e_control_room' / 'forecasts' / event_id / gate / f'{lane}.csv',
        root / 'latest' / 'forecast_outputs' / event_id / gate / lane / 'forecast_rows.csv',
    ]
    # Manual runs may intentionally re-lock a known latest bundle as lineage. Scheduled runs should not,
    # because that creates self-referential placeholder churn.
    if include_existing_bundles:
        sources.append(root / 'latest' / 'forecast_bundles' / event_id / gate / lane / 'forecast_rows.csv')
    return sources


def source_has_rows(root: Path, event_id: str, gate: str, lane: str) -> bool:
    for cand in candidate_sources(root, event_id, gate, lane, include_existing_bundles=False):
        if count_csv_rows(cand) > 0:
            return True
    return False


def discover_scheduled_targets(source_root: Path, gates: list[str]):
    """Find real forecast sources for scheduled gate locking.

    Returns a sorted list of (event_id, gate) pairs for which at least one lane has
    actual forecast rows. Existing forecast_bundles are deliberately excluded to avoid
    repeated scheduled re-locking of old/placeholder bundles.
    """
    targets=set()
    details=[]
    # latest/forecasts/<event_id>/<gate>/<lane>/forecast_rows.csv
    base = source_root / 'latest' / 'forecasts'
    if base.exists():
        for event_dir in base.iterdir():
            if not event_dir.is_dir():
                continue
            for gate in gates:
                for lane in LANES:
                    p = event_dir / gate / lane / 'forecast_rows.csv'
                    rows = count_csv_rows(p)
                    if rows > 0:
                        targets.add((event_dir.name, gate))
                        details.append({'event_id':event_dir.name,'gate':gate,'lane':lane,'source':str(p),'rows':rows})
    # latest/forecast_outputs/<event_id>/<gate>/<lane>/forecast_rows.csv
    base = source_root / 'latest' / 'forecast_outputs'
    if base.exists():
        for event_dir in base.iterdir():
            if not event_dir.is_dir():
                continue
            for gate in gates:
                for lane in LANES:
                    p = event_dir / gate / lane / 'forecast_rows.csv'
                    rows = count_csv_rows(p)
                    if rows > 0:
                        targets.add((event_dir.name, gate))
                        details.append({'event_id':event_dir.name,'gate':gate,'lane':lane,'source':str(p),'rows':rows})
    # latest/method_e_control_room/forecasts/<event_id>/<gate>/<lane>.csv
    base = source_root / 'latest' / 'method_e_control_room' / 'forecasts'
    if base.exists():
        for event_dir in base.iterdir():
            if not event_dir.is_dir():
                continue
            for gate in gates:
                for lane in LANES:
                    p = event_dir / gate / f'{lane}.csv'
                    rows = count_csv_rows(p)
                    if rows > 0:
                        targets.add((event_dir.name, gate))
                        details.append({'event_id':event_dir.name,'gate':gate,'lane':lane,'source':str(p),'rows':rows})
    return sorted(targets), details


def write_scheduler_guard_report(repo: Path, reason: str, gates: list[str], detected_details: list[dict]):
    outdir = repo / '_runtime' / 'forecast_bundle_locker_guard'
    outdir.mkdir(parents=True, exist_ok=True)
    now=utcnow()
    report={
        'created_utc': now,
        'guard_status': 'no_commit',
        'reason': reason,
        'gates_checked': gates,
        'detected_source_details': detected_details,
        'stable_engine_touched': False,
        'canonical_workbook_touched': False,
        'promotion_attempted': False,
    }
    (outdir/'scheduler_guard_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (outdir/'scheduler_guard_report.md').write_text(
        '# Forecast Bundle Locker Scheduler Guard\n\n'
        f'Created UTC: {now}\n\n'
        f'Status: no_commit\n\nReason: {reason}\n\n'
        'Scheduled runs only create/commit bundles when real forecast source rows are detected.\n',
        encoding='utf-8'
    )
    print(json.dumps(report, indent=2))


def load_forecast_rows(path: Path|None, bundle_id: str, event_id: str, season: str, round_no: str, race_name: str, gate: str, lane: str, config: str, lock_time: str):
    if not path or not path.exists():
        return [], False
    rows=[]
    with path.open('r', newline='', encoding='utf-8') as f:
        reader=csv.DictReader(f)
        for raw in reader:
            r={c: raw.get(c,'') for c in FORECAST_COLS}
            r.update({'bundle_id':bundle_id,'bundle_status':'locked','event_id':event_id,'season':season,'round':round_no,'race_name':race_name,'gate':gate,'engine_lane':lane,'engine_lane_config':config,'forecast_lock_utc':lock_time,'promotion_gate_eligible':'False'})
            rows.append(r)
    return rows, bool(rows)


def create_bundle(repo: Path, event_id: str, season: str, round_no: str, race_name: str, gate: str, lane: str, source_root: Path, commit_latest: bool, include_existing_bundles: bool=True):
    # Every direct caller crosses the same boundary before any mkdir/write.
    custody_guard.require_forecast_authority(event_id,gate,lane)
    found_path=next((p for p in candidate_sources(source_root,event_id,gate,lane,False) if count_csv_rows(p)>0),None)
    if found_path is None:raise custody_guard.ScientificHold('HOLD_FORECAST_SOURCE_MISSING')
    custody=custody_guard.verify_candidate(source_root,found_path,event_id,gate,lane,utcnow())
    doc=custody['manifest']; original=found_path.read_bytes()
    if sha(found_path)!=custody['source_sha256']:raise custody_guard.ScientificHold('HOLD_FORECAST_CHANGED_BEFORE_LOCK')
    key=custody_guard.digest(json.dumps(custody,sort_keys=True,separators=(',',':')).encode())
    bundle_id=f'{event_id}__{gate}__{lane}__{key}'
    history_dir=repo/'history/forecast_bundles'/event_id/key/gate/lane
    latest_dir=repo/'latest/forecast_bundles'/event_id/gate/lane
    # A retry retains the first actual storage time. It never changes generation
    # or source-observation times and cannot acquire scientific lock authority.
    old=history_dir/'bundle_lock_manifest.json'
    lock_time=json.loads(old.read_text())['preserved_at_utc'] if old.is_file() else utcnow()
    def raw(value):return (json.dumps(value,indent=2,sort_keys=True)+'\n').encode()
    manifest=dict(bundle_id=bundle_id,bundle_status='CANDIDATE_PRESERVED_NOT_SCIENTIFIC_LOCK',
        event_id=event_id,gate=gate,engine_lane=lane,engine_lane_config=LANES[lane],
        preserved_at_utc=lock_time,forecast_generation_utc=doc['forecast_generation_utc'],
        forecast_lock_utc=None,source_forecast_found=True,blind_validation_eligible=False,
        prediction_locked=False,promotion_gate_status='blocked',custody=custody)
    files={
        'forecast_rows.csv':original,
        'forecast_execution_manifest.json':found_path.with_name('forecast_execution_manifest.json').read_bytes(),
        'bundle_lock_manifest.json':raw(manifest),
        'source_snapshot_manifest.json':raw(doc['inputs']),
        'engine_lane_config.json':raw(dict(engine_lane=lane,engine_lane_config=LANES[lane],
            stable_engine_touched=False,canonical_workbook_touched=False,
            stable_engine_execution_proven=False,historical_stable_engine_execution_claimed=False)),
        'promotion_gate_metadata.json':raw(dict(promotion_gate_status='blocked',reason='Separate execution and lock authority required.')),
        'README.md':b'Preserved candidate bytes only. No scientific forecast lock or blind eligibility.\n',
    }
    # Check latest conflicts before creating any history; neither path may erase
    # an existing forecast or restore old evidence under a new observation time.
    if commit_latest and latest_dir.exists():
        actual={p.relative_to(latest_dir).as_posix():p.read_bytes() for p in latest_dir.rglob('*') if p.is_file()}
        if actual!=files:raise custody_guard.ScientificHold('HOLD_IMMUTABLE_FORECAST_COLLISION')
    if custody_guard.verify_candidate(source_root,found_path,event_id,gate,lane,utcnow()) != custody:
        raise custody_guard.ScientificHold('HOLD_FORECAST_CHANGED_BEFORE_LOCK')
    custody_guard.immutable_directory(history_dir,files)
    if commit_latest:custody_guard.immutable_directory(latest_dir,files)
    return dict(bundle_id=bundle_id,gate=gate,engine_lane=lane,source_found=True,
        history_dir=str(history_dir),latest_dir=str(latest_dir) if commit_latest else '',prediction_locked=False)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo-root', default='.')
    ap.add_argument('--event-id', required=True)
    ap.add_argument('--race-name', required=True)
    ap.add_argument('--season', default='2026')
    ap.add_argument('--round', default='')
    ap.add_argument('--gate', choices=GATES+['all'], default='all')
    ap.add_argument('--source-root', default='.')
    ap.add_argument('--commit-latest', action='store_true')
    ap.add_argument('--scheduled-run', action='store_true')
    ap.add_argument('--require-scheduled-source', action='store_true')
    ap.add_argument('--allow-structural-placeholders', action='store_true', help='Allow creation of missing_forecast_source structural bundles when actual forecast rows are absent. Default is false to avoid placeholder commits.')
    args=ap.parse_args()
    repo=Path(args.repo_root).resolve()
    source_root=Path(args.source_root).resolve()
    gates=GATES if args.gate=='all' else [args.gate]

    try:
        custody_guard.require_forecast_authority(args.event_id,gates[0],'stable_baseline')
    except custody_guard.ScientificHold as exc:
        return custody_guard.hold_report(repo,args.event_id,args.gate,'all',str(exc))

    # Scheduled guard: never create placeholder bundles on a timer unless actual forecast rows exist.
    if args.scheduled_run and args.require_scheduled_source:
        targets, details = discover_scheduled_targets(source_root, gates)
        if not targets:
            write_scheduler_guard_report(repo, 'No actual forecast source rows detected for scheduled run. No latest/history bundles created or committed.', gates, details)
            return
        print(json.dumps({'scheduled_guard_status':'source_detected','targets':targets,'detected_source_count':len(details)}, indent=2))
    else:
        targets=[(args.event_id, gate) for gate in gates]
        details=[]

    rows=[]
    skipped=[]
    for event_id, gate in targets:
        race_name = args.race_name if not args.scheduled_run else event_id.replace('_',' ').title()
        for lane in LANES:
            has_source = source_has_rows(source_root, event_id, gate, lane)
            if (not has_source) and (not args.allow_structural_placeholders):
                skipped.append({'event_id': event_id, 'gate': gate, 'engine_lane': lane, 'reason': 'missing_actual_forecast_rows'})
                continue
            rows.append(create_bundle(repo, event_id, args.season, args.round, race_name, gate, lane, source_root, args.commit_latest, include_existing_bundles=not args.scheduled_run))

    if not rows:
        write_scheduler_guard_report(
            repo,
            'No actual forecast source rows detected. No latest/history forecast bundles created. Re-run with --allow-structural-placeholders only if you intentionally want structural placeholders.',
            gates,
            skipped
        )
        return

    # Write summary only when bundles are actually created. This avoids latest churn on guarded no-source runs.
    summary_event = args.event_id if not args.scheduled_run else 'scheduled_detected_sources'
    out=repo/'latest'/'forecast_bundles'/summary_event/'bundle_creation_summary.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'created_utc':utcnow(),'event_id':args.event_id,'race_name':args.race_name,'gate':args.gate,'scheduled_run':args.scheduled_run,'detected_sources':details,'skipped_missing_sources':skipped,'bundles':rows}, indent=2), encoding='utf-8')
    print(json.dumps({'created':len(rows),'source_found':sum(1 for r in rows if r['source_found']),'summary':str(out)}, indent=2))

if __name__=='__main__':
    raise SystemExit(main())
