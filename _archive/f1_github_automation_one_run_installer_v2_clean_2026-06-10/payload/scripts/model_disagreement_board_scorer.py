#!/usr/bin/env python3
"""
Model Disagreement Board scorer.

Computes a simple disagreement score from ranks and risk/action divergence.
"""

import argparse
import pandas as pd
import numpy as np

RISK_SCORE = {"none":0, "watch":0.25, "warning":0.5, "action":0.75, "promotion_review_candidate":1.0}
FANTASY_RISK = {"optimal":0, "safe":0.1, "upside":0.25, "caution":0.6, "avoid":1.0}

def row_score(r):
    ranks = []
    for c in ["stable_rank","qualifying_specialist_rank","race_specialist_rank","external_benchmark_rank"]:
        try:
            v = float(r.get(c))
            if not np.isnan(v):
                ranks.append(v)
        except Exception:
            pass
    rank_disp = (max(ranks) - min(ranks)) / 20 if len(ranks) >= 2 else 0
    risk = RISK_SCORE.get(str(r.get("reliability_risk_band","none")).lower(), 0)
    fan = FANTASY_RISK.get(str(r.get("fantasy_action","")).lower(), 0)
    return max(0, min(1, 0.5*rank_disp + 0.3*risk + 0.2*fan))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-csv", required=True)
    p.add_argument("--output-csv", required=True)
    args = p.parse_args()
    df = pd.read_csv(args.input_csv)
    df["disagreement_score"] = df.apply(row_score, axis=1)
    df.to_csv(args.output_csv, index=False)

if __name__ == "__main__":
    main()
