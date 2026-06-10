#!/usr/bin/env python3
"""
Append to Locked Forecast Ledger v2.

Usage:
python append_locked_forecast_ledger_v2.py --ledger ledgers/locked_forecast_ledger_v2.jsonl --payload payload.json
"""

import argparse, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

REQUIRED = [
    "event","session","forecast_stage","model_version","forecast_type",
    "prediction_payload","authority_status"
]

def stable_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", required=True)
    p.add_argument("--payload", required=True)
    args = p.parse_args()

    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in payload]
    if missing:
        raise SystemExit(f"Missing required fields: {missing}")

    payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
    payload.setdefault("data_available_at_lock", payload["timestamp_utc"])
    payload.setdefault("source_readiness", "unknown")
    payload.setdefault("risk_flags", [])
    payload.setdefault("pattern_warnings", [])
    payload.setdefault("fantasy_recommendations", [])
    payload.setdefault("post_event_score", "pending")
    payload["stable_race_p1_p20_rank_change_allowed_from_risk_layers"] = False
    payload["private_internal_sensor_inference_allowed"] = False
    payload["ledger_id"] = stable_hash(payload)[:16]
    payload["lineage_hash"] = stable_hash(payload)

    ledger = Path(args.ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")
    print(payload["ledger_id"])

if __name__ == "__main__":
    main()
