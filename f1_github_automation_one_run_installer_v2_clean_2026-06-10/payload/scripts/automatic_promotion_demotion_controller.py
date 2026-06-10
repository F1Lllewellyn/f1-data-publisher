#!/usr/bin/env python3
"""
Automatic Promotion/Demotion Controller v1.

Evaluates authority changes from evidence metrics.
"""

import argparse
import pandas as pd

def decide(r):
    current = str(r.get("current_authority","risk_only"))
    requested = str(r.get("requested_authority",current))
    try: locked = int(float(r.get("locked_events",0) or 0))
    except Exception: locked = 0
    try: blind = int(float(r.get("blind_replay_events",0) or 0))
    except Exception: blind = 0
    try: fp = float(r.get("false_positive_rate",1) or 1)
    except Exception: fp = 1
    try: dv = float(r.get("decision_value_delta",0) or 0)
    except Exception: dv = 0
    rank_degradation = str(r.get("rank_degradation","false")).lower() in ["true","1","yes"]

    if rank_degradation:
        return "demote_or_block", "Rank degradation detected"
    if locked < 4 and blind < 6:
        return "hold", "Insufficient locked/blind proof"
    if fp > 0.50 and requested not in ["note_only","watch","risk_only"]:
        return "hold", "False-positive rate too high for requested authority"
    if dv <= 0:
        return "hold", "No positive decision value"
    return "promotion_candidate", "Evidence threshold met for review, not automatic rank change"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-csv", required=True)
    p.add_argument("--output-csv", required=True)
    args = p.parse_args()
    df = pd.read_csv(args.input_csv)
    decisions = df.apply(lambda r: decide(r), axis=1)
    df["controller_decision"] = [d[0] for d in decisions]
    df["reason"] = [d[1] for d in decisions]
    df["automatic_stable_rank_change_allowed"] = False
    df.to_csv(args.output_csv, index=False)

if __name__ == "__main__":
    main()
