#!/usr/bin/env python3
"""2026 Las Vegas post-session historical source custody: read-only and time bounded.

Runs only in the exact post-live source windows, never during a session,
never retimes inputs, never writes latest/history or invokes any forecast.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
import sys

from f1_live_session_source_custody_canary_v1 import capture_session

UTC=dt.timezone.utc
WINDOWS=(
    (dt.datetime(2026,11,21,2,0,tzinfo=UTC),dt.datetime(2026,11,21,4,0,tzinfo=UTC),11415,"FP3"),
    (dt.datetime(2026,11,21,6,0,tzinfo=UTC),dt.datetime(2026,11,21,8,0,tzinfo=UTC),11416,"QUALIFYING"),
    (dt.datetime(2026,11,22,7,0,tzinfo=UTC),dt.datetime(2026,11,22,9,0,tzinfo=UTC),11420,"RACE"),
)
MEETING=1300


def select_window(now):
    if now.tzinfo is None:raise ValueError("An offset-aware UTC observation clock is required")
    return next(((key,name) for start,end,key,name in WINDOWS if start<=now.astimezone(UTC)<end),None)


def main():
    now=dt.datetime.now(UTC)
    match=select_window(now)
    if match is None:
        print(json.dumps(dict(status="INACTIVE_EXACT_DATE_GUARD",observed_at_utc=now.isoformat(),provider_requests=0)))
        return 0
    session_key,session_name=match
    out=Path("_runtime/las_vegas_2026_post_session_custody")/f"{session_name.lower()}_{session_key}"
    result=capture_session(MEETING,session_key,out)
    diagnostic=dict(
        schema="f1-las-vegas-2026-historical-custody-v1",
        intent="post_session_historical_source_observation_only",
        attempted_at_utc=now.isoformat().replace("+00:00","Z"),
        session_name=session_name,meeting_key=MEETING,session_key=session_key,
        observation_result=result["result"],
        original_response_manifest="original_source_canary_manifest.json",
        verified_original_rows=result["verified_row_counts"],
        stable_engine_executed=False,forecast_eligible=False,
        historical_source_complete=False,prediction_locked=False,
        source_publication=False,
    )
    out.joinpath("post_session_custody_decision.json").write_text(json.dumps(diagnostic,indent=2)+"\n")
    print(json.dumps(diagnostic,indent=2))
    return 0 if result["result"].startswith("VERIFIED_") else 2


if __name__=="__main__":
    sys.exit(main())
