#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

POLICY = {
  "model_id": "experimental_challenger_v2_1_calibrated_gate_aware_stack",
  "stable_exact_output_overwrite_allowed": False,
  "promotion_allowed": False,
  "purpose": "Publish v2.1 policy/control artifacts and validate source readiness without changing stable forecasts."
}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--event-id', default='manual_v2_1_policy_validation')
    parser.add_argument('--commit-outputs', default='true')
    args=parser.parse_args()
    ts=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    root=Path.cwd()
    out=root/'latest'/'experimental_challenger_v2_1'
    hist=root/'history'/'experimental_challenger_v2_1'/f'{ts}_{args.event_id}'
    for p in [out,hist]:
        p.mkdir(parents=True, exist_ok=True)
    readiness={
        'event_id':args.event_id,
        'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'status':'pass_with_warnings',
        'stable_engine_changed':False,
        'stable_exact_output_overwrite_allowed':False,
        'promotion_allowed':False,
        'actual_saved_live_bundles_required_for_promotion':True,
        'notes':'v2.1 policy artifacts published; forecast generation/locking handled by source writer and bundle locker.'
    }
    for p in [out,hist]:
        (p/'experimental_challenger_v2_1_policy.json').write_text(json.dumps(POLICY,indent=2),encoding='utf-8')
        (p/'experimental_challenger_v2_1_readiness.json').write_text(json.dumps(readiness,indent=2),encoding='utf-8')
        pd.DataFrame([readiness]).to_csv(p/'experimental_challenger_v2_1_health_check.csv', index=False)
    print(json.dumps(readiness,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
