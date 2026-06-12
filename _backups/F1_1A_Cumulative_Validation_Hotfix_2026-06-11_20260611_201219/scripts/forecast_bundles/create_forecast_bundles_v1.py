#!/usr/bin/env python3
"""F1 forecast bundle locker v1 with scheduler guard.

Creates immutable saved forecast bundles for all engine lanes at a requested gate.
It never fabricates forecasts: if a lane forecast source is missing during a manual
or detected-gate lock, the bundle is structurally complete but marked
missing_forecast_source. Scheduled runs are guarded: they do not create or commit
placeholder bundles unless actual forecast source rows are detected first.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, os, shutil
from pathlib import Path

GATES = ["pre_weekend", "post_fp3", "post_qualifying", "race_result"]
LANES = {
    "stable_baseline": "Engine_2026-06-07_STABLE",
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
    lock_time=utcnow()
    config=LANES[lane]
    bundle_id=f'{event_id}__{gate}__{lane}__{lock_time.replace(":","").replace("-","")}'
    history_dir=repo/'history'/'forecast_bundles'/event_id/lock_time.replace(':','').replace('-','')/gate/lane
    latest_dir=repo/'latest'/'forecast_bundles'/event_id/gate/lane
    bdir=history_dir
    bdir.mkdir(parents=True, exist_ok=True)
    found_path=None
    for cand in candidate_sources(source_root, event_id, gate, lane, include_existing_bundles=include_existing_bundles):
        if count_csv_rows(cand) > 0:
            found_path=cand
            break
    forecast_rows, source_found = load_forecast_rows(found_path, bundle_id, event_id, season, round_no, race_name, gate, lane, config, lock_time)
    if not source_found:
        forecast_rows=[{c:'' for c in FORECAST_COLS}]
        forecast_rows[0].update({'bundle_id':bundle_id,'bundle_status':'missing_forecast_source','event_id':event_id,'season':season,'round':round_no,'race_name':race_name,'gate':gate,'engine_lane':lane,'engine_lane_config':config,'forecast_lock_utc':lock_time,'promotion_gate_eligible':'False','notes':'No source forecast rows found. Bundle complete structurally but not valid for non-proxy validation.'})
    write_csv(bdir/'forecast_rows.csv', FORECAST_COLS, forecast_rows)
    src_rows=[{'source_id':'forecast_source','source_name':str(found_path) if found_path else 'missing','source_type':'csv' if found_path else 'missing','source_path_or_uri':str(found_path) if found_path else '', 'source_timestamp_utc':lock_time, 'source_sha256':sha(found_path) if found_path else '', 'source_role':'forecast_source','gate_allowed':str(source_found),'notes':'Actual forecast source copied into immutable bundle.' if source_found else 'Missing source blocks validation.'}]
    write_csv(bdir/'source_snapshot_manifest.csv', ['source_id','source_name','source_type','source_path_or_uri','source_timestamp_utc','source_sha256','source_role','gate_allowed','notes'], src_rows)
    (bdir/'engine_lane_config.json').write_text(json.dumps({'engine_lane':lane,'engine_lane_config':config,'stable_engine_touched':False,'canonical_workbook_touched':False}, indent=2), encoding='utf-8')
    write_csv(bdir/'forecast_attribution.csv', ['attribution_id','gate','engine_lane','feature_family','input_source','directional_effect','weight_class','confidence','proof_loop_status','notes'], [{'attribution_id':bundle_id+'__ATTR','gate':gate,'engine_lane':lane,'feature_family':'bundle_lock','input_source':str(found_path) if found_path else 'missing','directional_effect':'locked' if source_found else 'blocked','weight_class':'source','confidence':'high' if source_found else 'none','proof_loop_status':'ready_for_scoring' if source_found else 'blocked','notes':''}])
    write_csv(bdir/'stable_vs_challenger_delta.csv', ['event_id','gate','metric','stable_baseline_value','control_room_overlay_value','experimental_challenger_value','overlay_delta_vs_stable','challenger_delta_vs_stable','promotion_gate_relevance','notes'], [{'event_id':event_id,'gate':gate,'metric':'pending_cross_lane_delta','promotion_gate_relevance':'pending','notes':'Computed after all lane bundles are present.'}])
    (bdir/'method_e_proof_loop_gate_record.json').write_text(json.dumps({'bundle_id':bundle_id,'gate':gate,'engine_lane':lane,'source_found':source_found,'proof_loop_status':'ready_for_post_event_scoring' if source_found else 'blocked_missing_forecast_source'}, indent=2), encoding='utf-8')
    (bdir/'promotion_gate_metadata.json').write_text(json.dumps({'bundle_id':bundle_id,'promotion_gate_status':'blocked','reason':'Promotion requires scored blind/session-gated performance improvement. Bundle lock alone is not enough.'}, indent=2), encoding='utf-8')
    write_csv(bdir/'scoring_placeholder.csv', ['event_id','gate','engine_lane','score_timestamp_utc','actual_source','mae_position','winner_hit','podium_overlap','top10_overlap','dnf_auc','dnf_brier','actual_dnf_count','expected_dnf_count','scoring_status','notes'], [{'event_id':event_id,'gate':gate,'engine_lane':lane,'scoring_status':'pending_outcome'}])
    manifest={'bundle_id':bundle_id,'bundle_status':'locked' if source_found else 'missing_forecast_source','event_id':event_id,'season':season,'round':round_no,'race_name':race_name,'gate':gate,'engine_lane':lane,'engine_lane_config':config,'forecast_lock_utc':lock_time,'blind_validation_eligible':source_found,'source_forecast_found':source_found,'promotion_gate_status':'blocked'}
    (bdir/'bundle_lock_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (bdir/'README.md').write_text(f'# Forecast bundle {bundle_id}\n\nStatus: {manifest["bundle_status"]}\n', encoding='utf-8')
    completeness=[]
    for f in REQUIRED:
        p=bdir/f
        completeness.append({'bundle_id':bundle_id,'event_id':event_id,'gate':gate,'engine_lane':lane,'required_file':f,'present':p.exists(),'status':'Pass' if p.exists() else 'Fail','notes':''})
    write_csv(bdir/'bundle_completeness_check.csv', ['bundle_id','event_id','gate','engine_lane','required_file','present','status','notes'], completeness)
    if commit_latest:
        if latest_dir.exists():
            shutil.rmtree(latest_dir)
        latest_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bdir, latest_dir)
    return {'bundle_id':bundle_id,'gate':gate,'engine_lane':lane,'source_found':source_found,'history_dir':str(history_dir),'latest_dir':str(latest_dir) if commit_latest else ''}


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
    args=ap.parse_args()
    repo=Path(args.repo_root).resolve()
    source_root=Path(args.source_root).resolve()
    gates=GATES if args.gate=='all' else [args.gate]

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
    for event_id, gate in targets:
        race_name = args.race_name if not args.scheduled_run else event_id.replace('_',' ').title()
        for lane in LANES:
            rows.append(create_bundle(repo, event_id, args.season, args.round, race_name, gate, lane, source_root, args.commit_latest, include_existing_bundles=not args.scheduled_run))

    # Write summary only when bundles are actually created. This avoids latest churn on guarded scheduled no-op runs.
    summary_event = args.event_id if not args.scheduled_run else 'scheduled_detected_sources'
    out=repo/'latest'/'forecast_bundles'/summary_event/'bundle_creation_summary.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'created_utc':utcnow(),'event_id':args.event_id,'race_name':args.race_name,'gate':args.gate,'scheduled_run':args.scheduled_run,'detected_sources':details,'bundles':rows}, indent=2), encoding='utf-8')
    print(json.dumps({'created':len(rows),'source_found':sum(1 for r in rows if r['source_found']),'summary':str(out)}, indent=2))

if __name__=='__main__':
    main()
