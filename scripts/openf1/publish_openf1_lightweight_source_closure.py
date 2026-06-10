#!/usr/bin/env python3
"""Publish lightweight OpenF1 source-closure artifacts.

This script is deliberately lightweight. It does not pull high-frequency
car_data or location by default. It captures source lanes that support
pattern identification, forecast attribution, reliability/EOL context,
clean-air/traffic-energy modelling, and post-event audit.

Timestamp policy: use timezone-aware dt.datetime.now(dt.UTC).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

API_BASE = "https://api.openf1.org/v1"
ROOT = Path.cwd()
POLICY_PATH = ROOT / "configs" / "openf1" / "openf1_lightweight_source_closure_policy.json"

# Lightweight endpoints only. Do not add car_data/location here by default.
LANES = [
    "weather",
    "race_control",
    "intervals",
    "position",
    "stints",
    "pit",
    "starting_grid",
    "drivers",
    "team_radio",
]

RACE_LIKE_HINTS = ("race", "sprint")
TEAM_RADIO_IS_OPPORTUNISTIC = True
REQUEST_TIMEOUT = 30
SLEEP_SECONDS = 0.10


def utc_now() -> dt.datetime:
    """Timezone-aware UTC timestamp, compatible with modern Python."""
    return dt.datetime.now(dt.UTC)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def slugify(value: Any) -> str:
    s = str(value or "unknown")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s or "unknown"


def openf1_get(endpoint: str, params: Dict[str, Any], request_log: List[Dict[str, Any]], strategy: str) -> pd.DataFrame:
    url = f"{API_BASE}/{endpoint}"
    clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
    start = time.time()
    status = "unknown"
    error = ""
    rows = 0
    try:
        r = requests.get(url, params=clean_params, timeout=REQUEST_TIMEOUT)
        status_code = r.status_code
        if status_code == 200:
            data = r.json()
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame([data]) if data else pd.DataFrame()
            rows = len(df)
            status = "pass" if rows > 0 else "zero_rows"
            return df
        else:
            status = f"http_{status_code}"
            error = r.text[:500]
            return pd.DataFrame()
    except Exception as exc:  # noqa: BLE001 - diagnostic script should never crash a full run for one lane
        status = "exception"
        error = repr(exc)
        return pd.DataFrame()
    finally:
        request_log.append({
            "timestamp_utc": iso_now(),
            "endpoint": endpoint,
            "strategy": strategy,
            "params_json": json.dumps(clean_params, sort_keys=True),
            "rows": rows,
            "status": status,
            "error": error,
            "elapsed_seconds": round(time.time() - start, 3),
        })
        time.sleep(SLEEP_SECONDS)


def load_policy() -> Dict[str, Any]:
    if POLICY_PATH.exists():
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return {}


def is_completed_session(row: pd.Series) -> bool:
    now = utc_now()
    for col in ("date_end", "session_end", "gmt_offset"):
        # gmt_offset is intentionally ignored; included only to document known OpenF1 columns.
        pass
    date_end = row.get("date_end")
    if not date_end or pd.isna(date_end):
        # If end is missing, use date_start as weak fallback; do not call future sessions completed.
        date_start = row.get("date_start")
        if not date_start or pd.isna(date_start):
            return False
        try:
            start_ts = pd.to_datetime(date_start, utc=True).to_pydatetime()
            return start_ts < now - dt.timedelta(hours=2)
        except Exception:
            return False
    try:
        end_ts = pd.to_datetime(date_end, utc=True).to_pydatetime()
        return end_ts < now
    except Exception:
        return False


def session_kind(row: pd.Series) -> str:
    text = " ".join(str(row.get(c, "")) for c in ["session_name", "session_type"])
    return text.lower()


def is_race_like_session(row: pd.Series) -> bool:
    kind = session_kind(row)
    return any(h in kind for h in RACE_LIKE_HINTS)


def read_existing_latest(latest_root: Path) -> Dict[str, Any]:
    manifest_path = latest_root / "latest_manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def write_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def get_sessions(season: int, completed_only: bool, request_log: List[Dict[str, Any]]) -> pd.DataFrame:
    sessions = openf1_get("sessions", {"year": season}, request_log, "sessions_by_year")
    if sessions.empty:
        return sessions
    sessions["_completed_session"] = sessions.apply(is_completed_session, axis=1)
    if completed_only:
        sessions = sessions[sessions["_completed_session"]].copy()
    return sessions.sort_values([c for c in ["date_start", "meeting_key", "session_key"] if c in sessions.columns])


def collect_observed_driver_numbers(outputs_by_lane: Dict[str, List[pd.DataFrame]]) -> List[int]:
    nums: set[int] = set()
    for lane, frames in outputs_by_lane.items():
        for df in frames:
            if df is None or df.empty:
                continue
            for col in ["driver_number", "driverNumber"]:
                if col in df.columns:
                    vals = pd.to_numeric(df[col], errors="coerce").dropna().astype(int).tolist()
                    nums.update(vals)
    return sorted(nums)


def retrieve_lane_for_session(lane: str, sess: pd.Series, request_log: List[Dict[str, Any]], outputs_by_lane: Dict[str, List[pd.DataFrame]]) -> pd.DataFrame:
    session_key = sess.get("session_key")
    meeting_key = sess.get("meeting_key")

    if lane == "pit" and not is_race_like_session(sess):
        request_log.append({
            "timestamp_utc": iso_now(),
            "endpoint": lane,
            "strategy": "skip_non_race_like_session",
            "params_json": json.dumps({"session_key": session_key}),
            "rows": 0,
            "status": "skipped_not_applicable",
            "error": "pit endpoint is only treated as required for race/sprint-like sessions",
            "elapsed_seconds": 0,
        })
        return pd.DataFrame()

    if lane == "position":
        # First try session_key. If zero, retry by meeting_key because OpenF1 position examples commonly use meeting_key.
        df = openf1_get("position", {"session_key": session_key}, request_log, "position_by_session_key")
        if df.empty and meeting_key is not None:
            df = openf1_get("position", {"meeting_key": meeting_key}, request_log, "position_by_meeting_key_fallback")
            if not df.empty and "session_key" in df.columns:
                df = df[df["session_key"].astype(str) == str(session_key)].copy()
        return df

    if lane == "drivers":
        df = openf1_get("drivers", {"session_key": session_key}, request_log, "drivers_by_session_key")
        if not df.empty:
            return df
        # Fallback: use already observed driver numbers from successful lanes.
        nums = collect_observed_driver_numbers(outputs_by_lane)
        frames = []
        for n in nums:
            part = openf1_get("drivers", {"session_key": session_key, "driver_number": n}, request_log, "drivers_by_observed_driver_number")
            if not part.empty:
                frames.append(part)
        return pd.concat(frames, ignore_index=True).drop_duplicates() if frames else pd.DataFrame()

    if lane == "team_radio":
        return openf1_get("team_radio", {"session_key": session_key}, request_log, "team_radio_by_session_key_opportunistic")

    return openf1_get(lane, {"session_key": session_key}, request_log, f"{lane}_by_session_key")


def classify_lane(lane: str, rows: int, attempted_sessions: int, applicable_sessions: int) -> Tuple[str, str]:
    if rows > 0:
        return "pass", "evidence_bearing"
    if lane == "team_radio":
        return "pass_with_warnings", "opportunistic_source_limited_zero_rows"
    if applicable_sessions == 0:
        return "pass_with_warnings", "not_applicable_for_current_completed_sessions"
    return "pass_with_warnings", "zero_rows_after_endpoint_specific_retry_needs_review"


def create_zip(folder: Path, zip_path: Path) -> str:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob("*"):
            if p.is_file() and p != zip_path:
                z.write(p, p.relative_to(folder))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (zip_path.with_suffix(zip_path.suffix + ".sha256.txt")).write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--completed-only", default="true")
    parser.add_argument("--output-root", default=".")
    args = parser.parse_args()

    season = int(args.season)
    completed_only = str(args.completed_only).lower() not in {"false", "0", "no"}
    policy = load_policy()

    output_root = Path(args.output_root).resolve()
    latest_root = output_root / "latest" / "openf1_lightweight_source_closure"
    history_root = output_root / "history" / "openf1_lightweight_source_closure" / utc_now().strftime("%Y%m%d_%H%M%S")
    data_latest = latest_root / "data"
    data_history = history_root / "data"
    latest_root.mkdir(parents=True, exist_ok=True)
    history_root.mkdir(parents=True, exist_ok=True)

    request_log: List[Dict[str, Any]] = []
    previous_manifest = read_existing_latest(latest_root)

    sessions = get_sessions(season, completed_only, request_log)
    write_df(sessions, data_latest / "target_sessions.csv")
    write_df(sessions, data_history / "target_sessions.csv")

    outputs_by_lane: Dict[str, List[pd.DataFrame]] = {lane: [] for lane in LANES}
    lane_session_rows: List[Dict[str, Any]] = []

    for _, sess in sessions.iterrows():
        for lane in LANES:
            applicable = not (lane == "pit" and not is_race_like_session(sess))
            df = retrieve_lane_for_session(lane, sess, request_log, outputs_by_lane)
            if not df.empty:
                df = df.copy()
                if "session_key" not in df.columns and sess.get("session_key") is not None:
                    df["session_key"] = sess.get("session_key")
                if "meeting_key" not in df.columns and sess.get("meeting_key") is not None:
                    df["meeting_key"] = sess.get("meeting_key")
                df["source_closure_retrieved_utc"] = iso_now()
                outputs_by_lane[lane].append(df)
            lane_session_rows.append({
                "lane": lane,
                "meeting_key": sess.get("meeting_key"),
                "session_key": sess.get("session_key"),
                "session_name": sess.get("session_name"),
                "session_type": sess.get("session_type"),
                "applicable": applicable,
                "rows": int(len(df)),
                "status": "pass" if len(df) > 0 else ("skipped_not_applicable" if not applicable else "zero_rows"),
            })

    source_manifest_rows = []
    readiness_rows = []
    for lane, frames in outputs_by_lane.items():
        if frames:
            combined = pd.concat(frames, ignore_index=True).drop_duplicates()
        else:
            combined = pd.DataFrame()
        # Write combined lane output.
        lane_file = f"openf1_{lane}.csv"
        write_df(combined, data_latest / lane_file)
        write_df(combined, data_history / lane_file)
        rows = int(len(combined))
        attempted_sessions = int((pd.DataFrame(lane_session_rows).query("lane == @lane").shape[0]) if lane_session_rows else 0)
        applicable_sessions = int(pd.DataFrame(lane_session_rows).query("lane == @lane and applicable == True").shape[0]) if lane_session_rows else 0
        result, reason = classify_lane(lane, rows, attempted_sessions, applicable_sessions)
        readiness_rows.append({
            "lane": lane,
            "rows": rows,
            "result": result,
            "reason": reason,
            "required_status": "opportunistic" if lane == "team_radio" else "required_lightweight",
            "heavy_endpoint": False,
        })
        source_manifest_rows.append({
            "path": f"data/{lane_file}",
            "lane": lane,
            "rows": rows,
            "sha256": hashlib.sha256((data_latest / lane_file).read_bytes()).hexdigest() if (data_latest / lane_file).exists() else "",
            "result": result,
            "reason": reason,
        })

    request_df = pd.DataFrame(request_log)
    lane_session_df = pd.DataFrame(lane_session_rows)
    readiness_df = pd.DataFrame(readiness_rows)
    source_manifest_df = pd.DataFrame(source_manifest_rows)

    write_df(request_df, latest_root / "request_log.csv")
    write_df(request_df, history_root / "request_log.csv")
    write_df(lane_session_df, latest_root / "zero_lane_diagnostics.csv")
    write_df(lane_session_df, history_root / "zero_lane_diagnostics.csv")
    write_df(readiness_df, latest_root / "source_readiness_summary.csv")
    write_df(readiness_df, history_root / "source_readiness_summary.csv")
    write_df(source_manifest_df, latest_root / "combined_source_manifest.csv")
    write_df(source_manifest_df, history_root / "combined_source_manifest.csv")

    # Optional workbook summary for non-coders.
    xlsx_path = latest_root / "F1_OpenF1_Lightweight_Source_Closure_Summary.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        readiness_df.to_excel(writer, sheet_name="Source Readiness", index=False)
        lane_session_df.to_excel(writer, sheet_name="Zero Lane Diagnostics", index=False)
        source_manifest_df.to_excel(writer, sheet_name="Manifest", index=False)
        sessions.to_excel(writer, sheet_name="Target Sessions", index=False)

    # Copy workbook to history too.
    history_xlsx = history_root / xlsx_path.name
    history_xlsx.write_bytes(xlsx_path.read_bytes())

    pass_count = int((readiness_df["result"] == "pass").sum()) if not readiness_df.empty else 0
    warning_count = int((readiness_df["result"] == "pass_with_warnings").sum()) if not readiness_df.empty else 0
    fail_count = int((readiness_df["result"] == "fail").sum()) if not readiness_df.empty else 0
    run_id = utc_now().strftime("%Y%m%d_%H%M%S")
    manifest = {
        "artifact_profile": "openf1-lightweight-source-closure",
        "generated_utc": iso_now(),
        "season": season,
        "completed_only": completed_only,
        "target_session_count": int(len(sessions)),
        "lanes": readiness_rows,
        "pass_count": pass_count,
        "pass_with_warnings_count": warning_count,
        "fail_count": fail_count,
        "heavy_endpoints_excluded_by_default": ["car_data", "location"],
        "timestamp_policy": "dt.datetime.now(dt.UTC)",
        "no_drs_2026_assumption": True,
        "previous_manifest_generated_utc": previous_manifest.get("generated_utc"),
        "latest_zip": "openf1_lightweight_source_closure.zip",
        "history_path": str(history_root.relative_to(output_root)),
    }
    (latest_root / "latest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (history_root / "latest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (latest_root / "data_readiness.json").write_text(json.dumps({"generated_utc": iso_now(), "lanes": readiness_rows}, indent=2), encoding="utf-8")
    (history_root / "data_readiness.json").write_text(json.dumps({"generated_utc": iso_now(), "lanes": readiness_rows}, indent=2), encoding="utf-8")

    report_lines = [
        "# F1 OpenF1 Lightweight Source Closure Report",
        "",
        f"Generated UTC: {iso_now()}",
        f"Season: {season}",
        f"Target sessions: {len(sessions)}",
        "",
        "## Result",
        "",
        f"Pass lanes: {pass_count}",
        f"Pass with warnings lanes: {warning_count}",
        f"Fail lanes: {fail_count}",
        "",
        "## Important",
        "",
        "Heavy OpenF1 car_data and location were not pulled by this workflow.",
        "Team radio is treated as opportunistic, not mandatory.",
        "2026 race assumptions do not use DRS logic.",
    ]
    (latest_root / "source_closure_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    (history_root / "source_closure_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    zip_digest = create_zip(latest_root, latest_root / "openf1_lightweight_source_closure.zip")
    create_zip(history_root, history_root / "openf1_lightweight_source_closure.zip")

    print("OpenF1 lightweight source closure complete.")
    print(f"Latest output: {latest_root}")
    print(f"History output: {history_root}")
    print(f"Latest ZIP SHA256: {zip_digest}")
    print(f"Pass lanes: {pass_count}; Pass with warnings lanes: {warning_count}; Fail lanes: {fail_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
