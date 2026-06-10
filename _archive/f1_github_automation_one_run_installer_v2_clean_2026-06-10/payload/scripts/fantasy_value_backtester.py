#!/usr/bin/env python3
"""
Fantasy Value Backtester v1.

Scores fantasy recommendations against actual points/price/DNF outcomes.
"""

import argparse
import pandas as pd
import numpy as np

def grade(row):
    rec = str(row.get("recommendation_type", "")).lower()
    actual = float(row.get("actual_points", 0) or 0)
    expected = float(row.get("expected_points", 0) or 0)
    dnf = bool(row.get("dnf_all", False))

    if rec in ["avoid", "caution"] and dnf:
        return "hit_avoided_dnf"
    if rec in ["avoid", "caution"] and actual > expected:
        return "false_positive_missed_upside"
    if rec in ["safe", "optimal"] and dnf:
        return "missed_dnf_risk"
    if rec in ["safe", "optimal"] and actual >= expected:
        return "hit_points"
    return "mixed"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-csv", required=True)
    p.add_argument("--output-csv", required=True)
    args = p.parse_args()

    df = pd.read_csv(args.input_csv)
    df["points_delta"] = pd.to_numeric(df.get("actual_points", 0), errors="coerce").fillna(0) - pd.to_numeric(df.get("expected_points", 0), errors="coerce").fillna(0)
    df["avoided_dnf_value"] = df.apply(lambda r: 1 if str(r.get("recommendation_type","")).lower() in ["avoid","caution"] and bool(r.get("dnf_all", False)) else 0, axis=1)
    df["decision_grade"] = df.apply(grade, axis=1)
    df.to_csv(args.output_csv, index=False)

if __name__ == "__main__":
    main()
