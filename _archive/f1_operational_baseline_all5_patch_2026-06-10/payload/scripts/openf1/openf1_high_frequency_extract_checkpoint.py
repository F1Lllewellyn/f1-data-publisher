#!/usr/bin/env python3
"""
OpenF1 high-frequency extraction checkpoint runner.

Runs the expensive OpenF1 extraction/build stage and uploads a checkpoint before
reporting. In race/post-race mode, if the normal feature mart is empty despite
successful extraction, it invokes a robust public-data fallback feature builder.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from openf1_high_frequency_auto_ingest import (  # noqa: E402
    OpenF1Client,
    discover_sessions,
    extract_raw,
    build_feature_mart,
    build_metrics,
)

from openf1_feature_fallback import build_feature_mart_fallback  # noqa: E402


def filter_recent_sessions(sessions: pd.DataFrame, recent_days: int) -> pd.DataFrame:
    if not recent_days or recent_days <= 0 or sessions.empty:
        return sessions
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=recent_days)
    dt_col = None
    for candidate in ["date_end_dt", "date_start_dt"]:
        if candidate in sessions.columns:
            dt_col = candidate
            break
    if dt_col is None:
        return sessions

    def keep_dt(x):
        if x is None or pd.isna(x):
            return False
        if getattr(x, "tzinfo", None) is None:
            x = x.replace(tzinfo=timezone.utc)
        return x >= cutoff

    return sessions[sessions[dt_col].apply(keep_dt)].copy().reset_index(drop=True)


def filter_latest_meeting(sessions: pd.DataFrame) -> pd.DataFrame:
    if sessions.empty or "meeting_key" not in sessions.columns:
        return sessions
    sort_cols = [c for c in ["date_end_dt", "date_start_dt", "meeting_key", "session_key"] if c in sessions.columns]
    ordered = sessions.sort_values(sort_cols).reset_index(drop=True)
    latest_meeting = ordered.iloc[-1]["meeting_key"]
    return ordered[ordered["meeting_key"] == latest_meeting].copy().reset_index(drop=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--mode", choices=["race", "prerace", "all"], required=True)
    p.add_argument("--event-filter", default="")
    p.add_argument("--fetch-mode", choices=["driver_full_session", "chunked_then_fallback"], default="driver_full_session")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--request-sleep", type=float, default=0.35)
    p.add_argument("--warning-threshold", type=float, default=0.80)
    p.add_argument("--strict-threshold", type=float, default=0.90)
    p.add_argument("--recent-days", type=int, default=0)
    p.add_argument("--latest-meeting-only", action="store_true")
    args = p.parse_args()

    output_dir = Path(args.output_dir)
    for sub in ["raw", "features", "metrics", "manifests", "reports"]:
        (output_dir / sub).mkdir(parents=True, exist_ok=True)

    token = os.environ.get("OPENF1_TOKEN", "").strip()
    client = OpenF1Client(token=token, sleep_seconds=args.request_sleep)

    sessions = discover_sessions(client, args.year, args.mode, event_filter=args.event_filter)
    original_session_count = len(sessions)
    sessions = filter_recent_sessions(sessions, args.recent_days)
    after_recent_count = len(sessions)

    if args.latest_meeting_only:
        sessions = filter_latest_meeting(sessions)

    sessions = sessions.reset_index(drop=True)
    sessions.to_csv(output_dir / "manifests" / "completed_sessions_selected.csv", index=False)

    if sessions.empty:
        summary = {
            "status": "NO_COMPLETED_SESSIONS_SELECTED",
            "year": args.year,
            "mode": args.mode,
            "event_filter": args.event_filter,
            "recent_days": args.recent_days,
            "latest_meeting_only": args.latest_meeting_only,
            "original_session_count": original_session_count,
            "after_recent_filter_session_count": after_recent_count,
            "selected_session_count": 0,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "manifests" / "extraction_checkpoint_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return

    session_drivers, manifest = extract_raw(client, sessions, output_dir, args.fetch_mode)

    fallback_feature_builder_used = False
    normal_feature_rows = 0
    fm = build_feature_mart(output_dir, sessions, session_drivers)
    normal_feature_rows = 0 if fm is None or fm.empty else len(fm)

    if args.mode == "race" and normal_feature_rows == 0:
        print("Normal race-mode feature mart is empty; invoking robust post-race fallback feature builder.")
        fm_fallback = build_feature_mart_fallback(output_dir, sessions, session_drivers)
        if fm_fallback is not None and not fm_fallback.empty:
            fm = fm_fallback
            fallback_feature_builder_used = True

    build_metrics(output_dir, args.mode, fm, client, args.year)

    policy = {
        "year": args.year,
        "mode": args.mode,
        "event_filter": args.event_filter,
        "fetch_mode": args.fetch_mode,
        "request_sleep": args.request_sleep,
        "warning_threshold": args.warning_threshold,
        "strict_threshold": args.strict_threshold,
        "recent_days": args.recent_days,
        "latest_meeting_only": args.latest_meeting_only,
        "stable_rank_change_allowed": False,
        "fantasy_and_reporting_use": True,
        "checkpoint_before_report": True,
        "postrace_feature_fallback_enabled": True,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "openf1_auto_ingest_run_policy.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")

    total_rows = 0
    if manifest is not None and not manifest.empty and "rows" in manifest.columns:
        total_rows = int(pd.to_numeric(manifest["rows"], errors="coerce").fillna(0).sum())

    feature_rows = 0 if fm is None or fm.empty else len(fm)

    summary = {
        "status": "EXTRACTION_CHECKPOINT_COMPLETE",
        "year": args.year,
        "mode": args.mode,
        "event_filter": args.event_filter,
        "recent_days": args.recent_days,
        "latest_meeting_only": args.latest_meeting_only,
        "original_session_count": original_session_count,
        "after_recent_filter_session_count": after_recent_count,
        "selected_session_count": len(sessions),
        "total_high_frequency_rows": total_rows,
        "normal_feature_rows": int(normal_feature_rows),
        "fallback_feature_builder_used": bool(fallback_feature_builder_used),
        "feature_rows": int(feature_rows),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "manifests" / "extraction_checkpoint_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Checkpoint complete. Output: {output_dir}")


if __name__ == "__main__":
    main()
