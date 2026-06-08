#!/usr/bin/env python3
"""
Hands-free OpenF1 + FastF1 public data publisher.

Goal:
- Run in GitHub Actions on a schedule.
- Pull OpenF1 and FastF1 data.
- Write validated CSVs/manifests/readiness files.
- Publish a static public folder suitable for GitHub Pages.
- Expose stable URLs:
    /latest/latest_manifest.json
    /latest/data_readiness.json
    /latest/latest.zip
    /history/<year>/<event_slug>/<run_tag>/...

Once GitHub Pages is enabled, ChatGPT can fetch these public URLs directly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

try:
    import fastf1
except Exception:
    fastf1 = None


OPENF1_BASE = "https://api.openf1.org/v1"

SESSION_ALIASES = {
    "FP1": ["Practice 1", "Free Practice 1", "FP1"],
    "FP2": ["Practice 2", "Free Practice 2", "FP2"],
    "FP3": ["Practice 3", "Free Practice 3", "FP3"],
    "Q": ["Qualifying", "Q"],
    "SQ": ["Sprint Qualifying", "Sprint Shootout", "SQ"],
    "S": ["Sprint", "Sprint Race", "S"],
    "R": ["Race", "Grand Prix", "R"],
}

CORE_OPENF1_ENDPOINTS = [
    "drivers", "session_result", "starting_grid", "laps", "position",
    "intervals", "pit", "stints", "race_control", "weather",
]


def utc_now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def safe_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def df_from_json(data: Any) -> pd.DataFrame:
    if isinstance(data, dict):
        data = [data]
    return pd.DataFrame(data or [])


def get_json(url: str, params: Optional[Dict[str, Any]] = None, retries: int = 3, sleep_s: float = 1.0) -> Any:
    params = {k: v for k, v in (params or {}).items() if v not in [None, ""]}
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=90)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last_error = exc
            print(f"[WARN] GET {url} attempt {attempt}/{retries} failed: {exc}")
            time.sleep(sleep_s * attempt)
    raise RuntimeError(f"GET failed: {url} params={params} error={last_error}")


def openf1(endpoint: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    return df_from_json(get_json(f"{OPENF1_BASE}/{endpoint}", params=params))


def normalize_sessions(sessions: str | List[str]) -> List[str]:
    if isinstance(sessions, str):
        parts = [p.strip() for p in sessions.split(",") if p.strip()]
    else:
        parts = [str(p).strip() for p in sessions if str(p).strip()]
    return parts or ["Q", "R"]


def session_matches(session_name: str, requested_code: str) -> bool:
    session_name_norm = slug(session_name)
    aliases = SESSION_ALIASES.get(requested_code.upper(), [requested_code])
    return any(slug(a) == session_name_norm or slug(a) in session_name_norm for a in aliases)


def select_openf1_sessions(sessions_df: pd.DataFrame, requested: List[str]) -> pd.DataFrame:
    if sessions_df.empty or "session_name" not in sessions_df.columns:
        return sessions_df
    mask = pd.Series([False] * len(sessions_df))
    for code in requested:
        mask = mask | sessions_df["session_name"].astype(str).apply(lambda x: session_matches(x, code))
    selected = sessions_df[mask.values].copy()
    return selected if not selected.empty else sessions_df.copy()


def openf1_find_meeting(year: int, country_name: Optional[str], event_name: Optional[str], meeting_key: Optional[int]) -> pd.DataFrame:
    if meeting_key:
        return openf1("meetings", {"meeting_key": meeting_key})
    if country_name:
        meetings = openf1("meetings", {"year": year, "country_name": country_name})
        if not meetings.empty:
            return meetings

    meetings = openf1("meetings", {"year": year})
    if event_name and not meetings.empty:
        event_slug = slug(event_name)
        matches = []
        for _, row in meetings.iterrows():
            text = " ".join(str(row.get(c, "")) for c in meetings.columns)
            matches.append(event_slug in slug(text))
        filtered = meetings[pd.Series(matches).values]
        if not filtered.empty:
            return filtered
    return meetings


def run_openf1_pull(outdir: Path, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    manifest = []
    out = outdir / "openf1"
    out.mkdir(parents=True, exist_ok=True)

    year = int(cfg["year"])
    event_name = cfg["event_name"]
    country_name = cfg.get("country_name")
    requested_sessions = normalize_sessions(cfg.get("sessions", ["Q", "R"]))
    meeting_key = cfg.get("meeting_key")
    endpoints = list(CORE_OPENF1_ENDPOINTS)
    if cfg.get("include_team_radio", True):
        endpoints.append("team_radio")
    if cfg.get("include_car_data", False):
        endpoints.append("car_data")

    try:
        meetings = openf1_find_meeting(year, country_name, event_name, meeting_key)
        safe_write_csv(meetings, out / "openf1_meetings.csv")
        if meetings.empty:
            manifest.append({"source": "openf1", "table": "meetings", "rows": 0, "status": "empty", "message": "No meeting found"})
            return manifest

        chosen_meeting_key = int(meetings.iloc[0]["meeting_key"])
        sessions = openf1("sessions", {"meeting_key": chosen_meeting_key})
        safe_write_csv(sessions, out / "openf1_sessions.csv")
        selected_sessions = select_openf1_sessions(sessions, requested_sessions)
        safe_write_csv(selected_sessions, out / "openf1_selected_sessions.csv")
        manifest.append({"source": "openf1", "table": "meetings", "rows": len(meetings), "status": "ok", "message": ""})
        manifest.append({"source": "openf1", "table": "sessions", "rows": len(sessions), "status": "ok", "message": ""})

        for _, session in selected_sessions.iterrows():
            session_key = int(session["session_key"])
            sname = str(session.get("session_name", f"session_{session_key}"))
            sslug = slug(sname)
            for endpoint in endpoints:
                try:
                    df = openf1(endpoint, {"session_key": session_key})
                    filename = f"openf1_{year}_{slug(event_name)}_{sslug}_{endpoint}.csv"
                    safe_write_csv(df, out / filename)
                    manifest.append({
                        "source": "openf1", "session_name": sname, "session_key": session_key,
                        "table": endpoint, "rows": len(df), "columns": len(df.columns),
                        "status": "ok" if len(df) else "empty_or_unavailable",
                        "filename": f"openf1/{filename}", "message": ""
                    })
                    print(f"[OpenF1] {sname} {endpoint}: {len(df):,}")
                    time.sleep(0.2)
                except Exception as exc:
                    manifest.append({
                        "source": "openf1", "session_name": sname, "session_key": session_key,
                        "table": endpoint, "rows": 0, "columns": 0,
                        "status": "error", "filename": "", "message": str(exc)
                    })
    except Exception as exc:
        manifest.append({"source": "openf1", "table": "openf1_run", "rows": 0, "status": "error", "message": str(exc)})
    return manifest


def timedeltas_to_seconds(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in list(out.columns):
        if pd.api.types.is_timedelta64_dtype(out[col]):
            out[f"{col}_seconds"] = out[col].dt.total_seconds()
    return out


def fastf1_load_with_diagnostics(session) -> List[Dict[str, Any]]:
    diagnostics = []
    modes = [
        {"laps": True, "telemetry": False, "weather": True, "messages": True},
        {"laps": True, "telemetry": True, "weather": True, "messages": True},
        {},
    ]
    for i, kwargs in enumerate(modes, start=1):
        try:
            if kwargs:
                session.load(**kwargs)
            else:
                session.load()
            checks = {}
            for attr in ["results", "laps", "weather_data", "race_control_messages"]:
                try:
                    obj = getattr(session, attr)
                    checks[attr] = len(obj) if hasattr(obj, "__len__") else "available"
                except Exception as exc:
                    checks[attr] = f"error: {exc}"
            diagnostics.append({"mode": i, "status": "ok", "checks": checks})
            if isinstance(checks.get("laps"), int) and checks["laps"] > 0:
                break
        except Exception as exc:
            diagnostics.append({"mode": i, "status": "error", "error": str(exc)})
    return diagnostics


def get_attr_df(session, attr: str) -> pd.DataFrame:
    try:
        obj = getattr(session, attr)
        if obj is None:
            return pd.DataFrame()
        if hasattr(obj, "copy"):
            return timedeltas_to_seconds(obj.copy())
        return pd.DataFrame(obj)
    except Exception as exc:
        print(f"[FastF1 WARN] could not access {attr}: {exc}")
        return pd.DataFrame()


def run_fastf1_pull(outdir: Path, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    manifest = []
    out = outdir / "fastf1"
    out.mkdir(parents=True, exist_ok=True)

    if fastf1 is None:
        manifest.append({"source": "fastf1", "table": "import", "rows": 0, "status": "error", "message": "fastf1 not installed"})
        return manifest

    year = int(cfg["year"])
    event_name = cfg["event_name"]
    requested_sessions = normalize_sessions(cfg.get("sessions", ["Q", "R"]))

    cache_dir = outdir / "fastf1_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        fastf1.Cache.enable_cache(str(cache_dir))
    except Exception as exc:
        print(f"[FastF1 WARN] cache failed: {exc}")

    diagnostics = []
    try:
        schedule = fastf1.get_event_schedule(year)
        safe_write_csv(schedule, out / f"fastf1_{year}_event_schedule.csv")
        manifest.append({"source": "fastf1", "table": "event_schedule", "rows": len(schedule), "status": "ok", "message": ""})
    except Exception as exc:
        manifest.append({"source": "fastf1", "table": "event_schedule", "rows": 0, "status": "error", "message": str(exc)})

    for code in requested_sessions:
        try:
            session = fastf1.get_session(year, event_name, code)
            d = fastf1_load_with_diagnostics(session)
            for row in d:
                row["session_code"] = code
            diagnostics.extend(d)

            prefix = f"fastf1_{year}_{slug(event_name)}_{slug(code)}"
            tables = {
                "results": get_attr_df(session, "results"),
                "laps": get_attr_df(session, "laps"),
                "weather": get_attr_df(session, "weather_data"),
                "race_control": get_attr_df(session, "race_control_messages"),
            }
            try:
                safe_write_csv(pd.DataFrame([dict(session.event)]), out / f"{prefix}_event_metadata.csv")
            except Exception:
                pass

            for name, df in tables.items():
                filename = f"{prefix}_{name}.csv"
                safe_write_csv(df, out / filename)
                manifest.append({
                    "source": "fastf1", "session_code": code, "table": name,
                    "rows": len(df), "columns": len(df.columns),
                    "status": "ok" if len(df) else "empty_or_unavailable",
                    "filename": f"fastf1/{filename}", "message": ""
                })
                print(f"[FastF1] {code} {name}: {len(df):,}")

            laps = tables["laps"]
            if not laps.empty and "Driver" in laps.columns:
                temp = laps.copy()
                if "LapTime" in temp.columns:
                    temp["LapTime_seconds_calc"] = pd.to_timedelta(temp["LapTime"], errors="coerce").dt.total_seconds()
                elif "LapTime_seconds" in temp.columns:
                    temp["LapTime_seconds_calc"] = temp["LapTime_seconds"]
                else:
                    temp["LapTime_seconds_calc"] = pd.NA
                summary = temp.groupby("Driver", dropna=False).agg(
                    laps=("Driver", "size"),
                    fastest_lap_seconds=("LapTime_seconds_calc", "min"),
                    median_lap_seconds=("LapTime_seconds_calc", "median"),
                    mean_lap_seconds=("LapTime_seconds_calc", "mean"),
                ).reset_index()
            else:
                summary = pd.DataFrame()

            filename = f"{prefix}_driver_lap_summary.csv"
            safe_write_csv(summary, out / filename)
            manifest.append({
                "source": "fastf1", "session_code": code, "table": "driver_lap_summary",
                "rows": len(summary), "columns": len(summary.columns),
                "status": "ok" if len(summary) else "empty_or_unavailable",
                "filename": f"fastf1/{filename}", "message": ""
            })

        except Exception as exc:
            manifest.append({"source": "fastf1", "session_code": code, "table": "session_load", "rows": 0, "status": "error", "message": str(exc)})

    safe_write_json(diagnostics, out / "fastf1_load_diagnostics.json")
    return manifest


def create_readiness(manifest_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    df = pd.DataFrame(manifest_rows)
    if df.empty:
        return {"overall": "not_ready", "reason": "No manifest rows"}

    def row_sum(source: str, table: str) -> int:
        if "source" not in df.columns or "table" not in df.columns:
            return 0
        sub = df[(df["source"].eq(source)) & (df["table"].eq(table))]
        return int(sub["rows"].fillna(0).sum()) if not sub.empty and "rows" in sub.columns else 0

    openf1_laps = row_sum("openf1", "laps")
    openf1_weather = row_sum("openf1", "weather")
    openf1_race_control = row_sum("openf1", "race_control")
    fastf1_laps = row_sum("fastf1", "laps")
    fastf1_results = row_sum("fastf1", "results")

    if openf1_laps > 0 and openf1_weather > 0:
        overall = "model_ready_primary_openf1"
    elif fastf1_laps > 0:
        overall = "model_ready_primary_fastf1"
    elif fastf1_results > 0:
        overall = "result_only_crosscheck"
    else:
        overall = "not_ready"

    return {
        "overall": overall,
        "openf1_laps": openf1_laps,
        "openf1_weather": openf1_weather,
        "openf1_race_control": openf1_race_control,
        "fastf1_laps": fastf1_laps,
        "fastf1_results": fastf1_results,
        "recommendation": (
            "Use OpenF1 as primary timing/weather/race-control source; FastF1 as cross-check."
            if overall == "model_ready_primary_openf1"
            else "Use FastF1 as timing source."
            if overall == "model_ready_primary_fastf1"
            else "Use as result cross-check only; rerun later for timing."
            if overall == "result_only_crosscheck"
            else "Rerun later; insufficient source readiness."
        )
    }


def build_zip(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in source_dir.rglob("*"):
            if p.is_file() and p != zip_path:
                zf.write(p, p.relative_to(source_dir))


def load_config(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def copytree_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.rglob("*"):
        if p.is_file():
            target = dst / p.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/race_config.json")
    parser.add_argument("--year", type=int)
    parser.add_argument("--event-name")
    parser.add_argument("--country-name")
    parser.add_argument("--sessions")
    parser.add_argument("--meeting-key", type=int)
    parser.add_argument("--out-public", default="public")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.year:
        cfg["year"] = args.year
    if args.event_name:
        cfg["event_name"] = args.event_name
    if args.country_name:
        cfg["country_name"] = args.country_name
    if args.sessions:
        cfg["sessions"] = normalize_sessions(args.sessions)
    if args.meeting_key:
        cfg["meeting_key"] = args.meeting_key

    cfg["sessions"] = normalize_sessions(cfg.get("sessions", ["Q", "R"]))

    run_tag = utc_now_tag()
    event_slug = slug(cfg["event_name"])
    year = int(cfg["year"])

    work = Path("_work") / f"{year}_{event_slug}_{run_tag}"
    work.mkdir(parents=True, exist_ok=True)

    safe_write_json({**cfg, "run_tag": run_tag, "run_started_utc": utc_now_iso()}, work / "run_config.json")

    manifest_rows = []
    if cfg.get("include_openf1", True):
        manifest_rows.extend(run_openf1_pull(work, cfg))
    if cfg.get("include_fastf1", True):
        manifest_rows.extend(run_fastf1_pull(work, cfg))

    manifest = pd.DataFrame(manifest_rows)
    safe_write_csv(manifest, work / "combined_source_manifest.csv")
    readiness = create_readiness(manifest_rows)
    safe_write_json(readiness, work / "data_readiness.json")
    safe_write_csv(pd.DataFrame([readiness]), work / "data_readiness.csv")

    # Output README
    readme = f"""# F1 data ingest output

Year: {year}
Event: {cfg["event_name"]}
Run: {run_tag}

Readiness: {readiness.get("overall")}

Recommendation: {readiness.get("recommendation")}

Stable URLs after GitHub Pages deploy:
- /latest/latest_manifest.json
- /latest/data_readiness.json
- /latest/latest.zip
"""
    (work / "README_OUTPUT.md").write_text(readme, encoding="utf-8")

    # Package this run.
    build_zip(work, work / "latest.zip")

    public = Path(args.out_public)
    latest = public / "latest"
    history = public / "history" / str(year) / event_slug / run_tag

    # Recreate latest only.
    if latest.exists():
        import shutil
        shutil.rmtree(latest)
    latest.mkdir(parents=True, exist_ok=True)

    copytree_contents(work, latest)
    copytree_contents(work, history)

    # Write easy-to-fetch manifest pointers.
    latest_manifest = {
        "year": year,
        "event_name": cfg["event_name"],
        "event_slug": event_slug,
        "run_tag": run_tag,
        "generated_utc": utc_now_iso(),
        "readiness": readiness,
        "stable_files": {
            "latest_manifest": "latest/latest_manifest.json",
            "data_readiness": "latest/data_readiness.json",
            "combined_source_manifest": "latest/combined_source_manifest.csv",
            "latest_zip": "latest/latest.zip"
        },
        "history_path": f"history/{year}/{event_slug}/{run_tag}/"
    }
    safe_write_json(latest_manifest, latest / "latest_manifest.json")
    safe_write_json(latest_manifest, history / "latest_manifest.json")

    index = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>F1 Data Publisher</title></head>
<body>
<h1>F1 Data Publisher</h1>
<p>Latest event: {cfg["event_name"]} {year}</p>
<p>Run: {run_tag}</p>
<p>Readiness: {readiness.get("overall")}</p>
<ul>
<li><a href="latest/latest_manifest.json">latest_manifest.json</a></li>
<li><a href="latest/data_readiness.json">data_readiness.json</a></li>
<li><a href="latest/combined_source_manifest.csv">combined_source_manifest.csv</a></li>
<li><a href="latest/latest.zip">latest.zip</a></li>
</ul>
</body></html>
"""
    (public / "index.html").write_text(index, encoding="utf-8")

    print("Published public folder:")
    print(json.dumps(latest_manifest, indent=2))


if __name__ == "__main__":
    main()
