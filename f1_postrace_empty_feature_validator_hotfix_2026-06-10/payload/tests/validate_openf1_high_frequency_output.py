#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd
import sys
import json

def read_checkpoint_summary(root: Path) -> dict:
    path = root / "manifests" / "extraction_checkpoint_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--mode", choices=["race","prerace","all"], required=True)
    p.add_argument(
        "--allow-empty-features",
        action="store_true",
        help="Allow race/post-race jobs to pass with warnings when extraction succeeds but no feature rows are produced."
    )
    args = p.parse_args()

    root = Path(args.output_dir)

    base_required = [
        root / "manifests" / "completed_sessions_selected.csv",
        root / "manifests" / "high_frequency_extraction_manifest.csv",
        root / "manifests" / "feature_manifest.csv",
        root / "reports" / "openf1_high_frequency_auto_ingest_report.md",
    ]

    missing = [str(p) for p in base_required if not p.exists()]
    if missing:
        print("Missing required files:")
        print("\n".join(missing))
        sys.exit(1)

    manifest = pd.read_csv(root / "manifests" / "high_frequency_extraction_manifest.csv")
    if manifest.empty:
        print("Extraction manifest is empty.")
        sys.exit(1)

    rows = pd.to_numeric(manifest.get("rows", 0), errors="coerce").fillna(0).sum()
    if rows <= 0:
        print("No OpenF1 high-frequency rows were extracted.")
        sys.exit(1)

    feature_manifest = pd.read_csv(root / "manifests" / "feature_manifest.csv")
    feature_file = root / "features" / "openf1_high_frequency_reliability_features_30s.parquet"

    feature_rows_from_manifest = 0
    if not feature_manifest.empty and "rows_30s" in feature_manifest.columns:
        feature_rows_from_manifest = int(pd.to_numeric(feature_manifest["rows_30s"], errors="coerce").fillna(0).sum())

    if feature_file.exists():
        features = pd.read_parquet(feature_file)
        feature_rows = len(features)
    else:
        features = pd.DataFrame()
        feature_rows = feature_rows_from_manifest

    if feature_rows <= 0:
        if args.allow_empty_features and args.mode == "race":
            summary = read_checkpoint_summary(root)
            print("Validation PASS_WITH_WARNINGS")
            print("Reason: post-race extraction succeeded, report exists, and artifacts are available, but no 30-second feature rows were produced.")
            print(f"High-frequency rows extracted: {int(rows)}")
            print(f"Selected sessions: {summary.get('selected_session_count', 'unknown')}")
            print("No stable/fantasy/race-order signal should be consumed from this post-race run until feature rows are available.")
            sys.exit(0)

        if not feature_file.exists():
            print("Missing required files:")
            print(str(feature_file))
            sys.exit(1)

        print("Feature mart is empty.")
        sys.exit(1)

    if args.mode in ["prerace", "all"]:
        metric = root / "metrics" / "pre_race_first_warning_to_dnf_aggregate.csv"
        if not metric.exists():
            print("Pre-race metric file is missing for prerace/all mode.")
            sys.exit(1)

    print("Validation PASS")
    print(f"High-frequency rows extracted: {int(rows)}")
    print(f"Feature rows: {feature_rows}")

if __name__ == "__main__":
    main()
