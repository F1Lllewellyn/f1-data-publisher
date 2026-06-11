#!/usr/bin/env python3
"""
F1 Forecast Gate Source Writer v1

This script does NOT fabricate historical blind forecasts. It normalizes actual forecast
source rows that already exist at a gate into the Forecast Bundle Locker's expected path.
It supports all five validation gates and all three engine lanes. If sources are missing,
it writes an audit record and exits cleanly without creating false actual bundles.
"""
import argparse, csv, json, hashlib, os, sys
from pathlib import Path
from datetime import datetime, timezone

GATES = ['pre_weekend','post_fp3','post_qualifying','race_result','post_event']
LANES = ['stable_baseline','control_room_overlay','experimental_challenger']
REQUIRED_COLUMNS = [
    'bundle_id','bundle_status','event_id','season','round','race_name','gate','engine_lane','engine_lane_config',
    'forecast_timestamp_utc','forecast_lock_utc','session_scope','driver_number','driver_name','team_name',
    'predicted_qualifying_position','predicted_race_finish_position','predicted_points_band','predicted_dnf_probability',
    'predicted_top1_probability','predicted_top3_probability','predicted_top5_probability','predicted_top10_probability',
    'predicted_mean_finish_position','confidence_score','risk_flags','source_snapshot_id','forecast_artifact_id',
    'stable_vs_challenger_delta_note','method_e_attribution_note','promotion_gate_eligible','notes'
]
LANE_CONFIG = {
    'stable_baseline':'Engine_2026-06-07_STABLE',
    'control_room_overlay':'MethodE_ControlRoom_Overlay',
    'experimental_challenger':'IntegratedSpecialist_RecalibratedReliability_EOL_EXPERIMENTAL'
}

def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

def normalize_rows(rows, event_id, gate, lane):
    out=[]
    ts=utcnow()
    for i,r in enumerate(rows, start=1):
        nr={c:'' for c in REQUIRED_COLUMNS}
        # pass through common fields if present
        for c in REQUIRED_COLUMNS:
            if c in r and r[c] not in (None,''):
                nr[c]=r[c]
        nr['bundle_id']=nr['bundle_id'] or f'{event_id}__{gate}__{lane}__LOCK_READY_{ts.replace(":","").replace("-","")}'
        nr['bundle_status']='forecast_source_rows_available_not_yet_locked'
        nr['event_id']=nr['event_id'] or event_id
        nr['gate']=gate
        nr['engine_lane']=lane
        nr['engine_lane_config']=nr['engine_lane_config'] or LANE_CONFIG[lane]
        nr['forecast_timestamp_utc']=nr['forecast_timestamp_utc'] or ts
        nr['forecast_lock_utc']=''  # Set by Forecast Bundle Locker, not source writer.
        nr['driver_number']=nr['driver_number'] or r.get('driver','') or r.get('driver_id','')
        nr['driver_name']=nr['driver_name'] or r.get('full_name','') or r.get('name','') or r.get('driver','')
        nr['team_name']=nr['team_name'] or r.get('team','') or r.get('team_name','')
        nr['predicted_race_finish_position']=nr['predicted_race_finish_position'] or r.get('predicted_position','') or r.get('predicted_finish','') or r.get('race_position','')
        nr['predicted_qualifying_position']=nr['predicted_qualifying_position'] or r.get('predicted_qualifying_position','') or r.get('qualifying_position','')
        nr['predicted_dnf_probability']=nr['predicted_dnf_probability'] or r.get('dnf_probability','') or r.get('predicted_dnf_probability','')
        nr['confidence_score']=nr['confidence_score'] or r.get('confidence','') or r.get('confidence_score','')
        nr['promotion_gate_eligible']='False'
        nr['notes']=(nr['notes'] + ' | ' if nr['notes'] else '') + 'Actual forecast source row normalized before bundle lock. Promotion eligibility remains false until scoring.'
        out.append(nr)
    return out

def candidate_paths(repo, event_id, gate, lane):
    templates=[
        'latest/forecasts/{event_id}/{gate}/{lane}/forecast_rows.csv',
        'latest/forecast_outputs/{event_id}/{gate}/{lane}/forecast_rows.csv',
        'latest/method_e_control_room/forecasts/{event_id}/{gate}/{lane}.csv',
        'history/forecast_outputs/{event_id}/{gate}/{lane}/forecast_rows.csv'
    ]
    return [repo / t.format(event_id=event_id, gate=gate, lane=lane) for t in templates]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo-root', default='.')
    ap.add_argument('--event-id', required=True)
    ap.add_argument('--gate', default='all', choices=['all']+GATES)
    ap.add_argument('--lane', default='all', choices=['all']+LANES)
    ap.add_argument('--allow-structural-empty', action='store_true', help='Do not use for blind validation; writes no forecast rows, only audit.')
    args=ap.parse_args()
    repo=Path(args.repo_root).resolve()
    gates=GATES if args.gate=='all' else [args.gate]
    lanes=LANES if args.lane=='all' else [args.lane]
    audit=[]; wrote=[]
    for gate in gates:
        for lane in lanes:
            cands=candidate_paths(repo,args.event_id,gate,lane)
            # Avoid treating the output path as source unless it already has rows and came from a previous forecast-producing run.
            source=None; source_rows=[]
            for c in cands[1:]:
                if c.exists():
                    rows=read_csv(c)
                    if rows:
                        source=c; source_rows=rows; break
            outpath=repo / f'latest/forecasts/{args.event_id}/{gate}/{lane}/forecast_rows.csv'
            if source is None:
                audit.append({'event_id':args.event_id,'gate':gate,'engine_lane':lane,'status':'missing_forecast_source_rows','source_path':'','output_path':str(outpath),'rows_written':0,'blind_validation_eligible':False,'note':'No actual forecast source rows found. No false bundle created.'})
                continue
            norm=normalize_rows(source_rows,args.event_id,gate,lane)
            write_csv(outpath,norm,REQUIRED_COLUMNS)
            wrote.append(outpath)
            audit.append({'event_id':args.event_id,'gate':gate,'engine_lane':lane,'status':'forecast_rows_normalized','source_path':str(source),'output_path':str(outpath),'rows_written':len(norm),'blind_validation_eligible':True,'note':'Rows are eligible only if this workflow ran before outcome and locker records gate lock time.'})
    audit_path=repo / f'latest/forecast_bundle_gap_closure/{args.event_id}/forecast_gate_source_writer_audit.csv'
    write_csv(audit_path,audit, list(audit[0].keys()) if audit else ['event_id','gate','engine_lane','status'])
    manifest={
        'event_id':args.event_id,'gate':args.gate,'lane':args.lane,'created_utc':utcnow(),
        'rows_files_written':[str(p) for p in wrote],
        'rows_files_written_count':len(wrote),
        'audit_path':str(audit_path),
        'promotion_gate_eligible':False,
        'stable_exact_output_overwrite_allowed':False,
        'next_step':'Run F1 Forecast Bundle Locker v1 after forecast rows exist.'
    }
    mpath=repo / f'latest/forecast_bundle_gap_closure/{args.event_id}/forecast_gate_source_writer_manifest.json'
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
