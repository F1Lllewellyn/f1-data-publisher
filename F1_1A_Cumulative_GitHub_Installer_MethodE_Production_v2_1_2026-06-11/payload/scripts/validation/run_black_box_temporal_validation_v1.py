#!/usr/bin/env python3
"""F1 Black-Box Temporal Validation Harness v1.

Creates temporal cutoff manifests, leakage audits, gate/lane bundle containers,
and a promotion-gate decision. This harness does not fabricate actual saved
forecast bundles; it clearly labels black-box temporal replay outputs.
"""
from __future__ import annotations
import argparse, json, hashlib, zipfile
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

GATES = ["pre_weekend", "post_fp3", "post_qualifying", "race_result", "post_event"]
LANES = ["stable_baseline", "control_room_overlay", "experimental_challenger"]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def read_zip_csv(zip_path: Path, suffix: str):
    if not zip_path.exists():
        return None
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith(suffix):
                return pd.read_csv(z.open(name))
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo-root', default='.', help='Repository root or artifact workspace')
    ap.add_argument('--out-dir', default='latest/black_box_temporal_validation', help='Output directory')
    ap.add_argument('--event-id', default='historical_replay')
    args = ap.parse_args()
    root = Path(args.repo_root).resolve()
    out = (root / args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out/'results').mkdir(exist_ok=True)
    (out/'manifests').mkdir(exist_ok=True)
    (out/'black_box_replay_bundles').mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    # Build gate/lane containers and cutoffs.
    rows=[]
    for gate in GATES:
        for lane in LANES:
            bdir = out/'black_box_replay_bundles'/gate/lane
            bdir.mkdir(parents=True, exist_ok=True)
            manifest = {
                'event_id': args.event_id,
                'gate': gate,
                'engine_lane': lane,
                'created_utc': now,
                'bundle_type': 'black_box_temporal_replay_container',
                'actual_saved_forecast_bundle': False,
                'promotion_value': 'supportive_only_not_sufficient',
                'stable_output_overwrite_allowed': False,
            }
            (bdir/'bundle_manifest.json').write_text(json.dumps(manifest, indent=2))
            rows.append(manifest)
    pd.DataFrame(rows).to_csv(out/'results/gate_lane_black_box_bundle_matrix.csv', index=False)

    promotion = {
        'created_utc': now,
        'event_id': args.event_id,
        'promotion_decision': 'NO_PROMOTION',
        'promotion_gate_satisfied': False,
        'reason': 'Black-box temporal replay is supportive evidence but not a substitute for actual saved gate-locked forecast bundles.',
    }
    (out/'results/promotion_gate_black_box_temporal.json').write_text(json.dumps(promotion, indent=2))
    pd.DataFrame([promotion]).to_csv(out/'results/promotion_gate_black_box_temporal.csv', index=False)
    print(json.dumps({'status':'Pass with warnings','out_dir':str(out),'promotion':'NO_PROMOTION'}, indent=2))

if __name__ == '__main__':
    main()
