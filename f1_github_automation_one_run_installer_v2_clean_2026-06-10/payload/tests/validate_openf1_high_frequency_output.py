#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd
import sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--mode", choices=["race","prerace","all"], required=True)
    args = p.parse_args()

    root = Path(args.output_dir)
    required = [
        root / "manifests" / "completed_sessions_selected.csv",
        root / "manifests" / "high_frequency_extraction_manifest.csv",
        root / "manifests" / "feature_manifest.csv",
        root / "features" / "openf1_high_frequency_reliability_features_30s.parquet",
        root / "reports" / "openf1_high_frequency_auto_ingest_report.md",
    ]

    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("Missing required files:")
        print("\n".join(missing))
        sys.exit(1)

    manifest = pd.read_csv(root / "manifests" / "high_frequency_extraction_manifest.csv")
    if manifest.empty:
        print("Extraction manifest is empty.")
        sys.exit(1)

    rows = pd.to_numeric(manifest["rows"], errors="coerce").fillna(0).sum()
    if rows <= 0:
        print("No OpenF1 high-frequency rows were extracted.")
        sys.exit(1)

    features = pd.read_parquet(root / "features" / "openf1_high_frequency_reliability_features_30s.parquet")
    if features.empty:
        print("Feature mart is empty.")
        sys.exit(1)

    if args.mode in ["prerace", "all"]:
        metric = root / "metrics" / "pre_race_first_warning_to_dnf_aggregate.csv"
        if not metric.exists():
            print("Pre-race metric file is missing for prerace/all mode.")
            sys.exit(1)

    print("Validation PASS")

if __name__ == "__main__":
    main()
