#!/usr/bin/env python3
"""
F1 public data publisher v2.

Fixes:
- Strict session selection so "R" does not accidentally match "Practice".
- OpenF1 404s for future/unavailable detailed endpoints are logged as empty_or_unavailable, not hard errors.
- Adds selected session diagnostics.
- Publishes latest_manifest.json, data_readiness.json, combined_source_manifest.csv, and latest.zip.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

try:
    import fastf1
except Exception:
    fastf1 = None


OPENF1_BASE = "https://api.openf1.org/v1"

OPENF1_ENDPOINTS = [
    "drivers",
    "session_result",
    "starting_grid",
    "laps",
    "position",
    "intervals",
    "pit",
    "stints",
    "race_control",
    "weather",
    "team_radio",
]

SESSION_CODE_TO_NAMES = {
    "FP1": {"practice 1", "free practice 1"},
    "FP2": {"practice 2", "free practice 2"},
    "FP3": {"practice 3", "free practice 3"},
    "Q": {"qualifying"},
    "SQ": {"sprint qualifying", "sprint shootout"},
    "S": {"sprint", "sprint race"},
    "R": {"race"},
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    retries: int = 3,
    allow_404_empty: bool = False,
) -> Tuple[Any, Optional[int]]:
    params = {k: v for k, v in (params or {}).items() if v not in [None, ""]}
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=90)
            if response.status_code == 404 and allow_404_empty:
                return [], 404
            response.raise_for_status()
            return response.json(), response.status_code
        except Exception as exc:
            last_error = exc
            print(f"[WARN] {url} attempt {attempt}/{retries} failed: {exc}")
            time.sleep(attempt)

    raise RuntimeError(f"GET failed: {url} params={params} error={last_error}")


def to_df(data: Any) -> pd.DataFrame:
    if isinstance(data, dict):
        data = [data]
    return pd.DataFrame(data or [])


def openf1(endpoint: str, params: Optional[Dict[str, Any]] = None, allow_404_empty: bool = False) -> Tuple[pd.DataFrame, Optional[int]]:
    data, status_code = get_json(f"{OPENF1_BASE}/{endpoint}", params=params, allow_404_empty=allow_404_empty)
    return to_df(data), status_code


def parse_sessions(value: str | List[str]) -> List[str]:
    if isinstance(value, str):
        return [x.strip().upper() for x in value.split(",") if x.strip()]
    return [str(x).strip().upper() for x in value if str(x).strip()]


def session_name_matches(session_name: str, requested_code: str) -> bool:
    """
    Strict matching. Do not use one-letter substring matching:
    "R" must match "Race", not "Practice".
    """
    requested_code = requested_code.upper()
    session_norm = norm(session_name)
    allowed_names = SESSION_CODE_TO_NAMES.get(requested_code)

    if allowed_names:
        return session_norm in allowed_names

    # Fallback for unusual user input: exact normalized string only.
    return session_norm == norm(requested_code)


def select_sessions(session_df: pd.DataFrame, requested: List[str]) -> pd.DataFrame:
    if session_df.empty or "session_name" not in session_df.columns:
        return session_df

    mask = pd.Series([False] * len(session_df))
    for req in requested:
        mask = mask | session_df["session_name"].astype(str).apply(lambda x: session_name_matches(x, req))

    selected = session_df[mask.values].copy()
    return selected


def run_openf1(outdir: Path, year: int, event_name: str, country_name: str, sessions: List[str]) -> List[Dict[str, Any]]:
    manifest: List[Dict[str, Any]] = []
    source_dir = outdir / "openf1"
    source_dir.mkdir(parents=True, exist_ok=True)

    try:
        meetings, _ = openf1("meetings", {"year": year, "country_name": country_name})
        save_csv(meetings, source_dir / "openf1_meetings.csv")
        manifest.append({
            "source": "openf1",
            "table": "meetings",
            "rows": len(meetings),
            "status": "ok" if len(meetings) else "empty",
            "message": "",
        })

        if meetings.empty:
            return manifest

        meeting_key = int(meetings.iloc[0]["meeting_key"])
        all_sessions, _ = openf1("sessions", {"meeting_key": meeting_key})
        save_csv(all_sessions, source_dir / "openf1_sessions.csv")
        selected = select_sessions(all_sessions, sessions)
        save_csv(selected, source_dir / "openf1_selected_sessions.csv")

        manifest.append({
            "source": "openf1",
            "table": "sessions",
            "rows": len(all_sessions),
            "status": "ok" if len(all_sessions) else "empty",
            "message": "",
        })
        manifest.append({
            "source": "openf1",
            "table": "selected_sessions",
            "rows": len(selected),
            "status": "ok" if len(selected) else "empty",
            "message": f"requested={sessions}; selected={selected['session_name'].tolist() if not selected.empty and 'session_name' in selected.columns else []}",
        })

        if selected.empty:
            return manifest

        for _, s in selected.iterrows():
            session_key = int(s["session_key"])
            session_name = str(s.get("session_name", session_key))
            session_slug = slug(session_name)

            for endpoint in OPENF1_ENDPOINTS:
                try:
                    # Detailed endpoints often 404 before the session has happened/populated.
                    df, status_code = openf1(endpoint, {"session_key": session_key}, allow_404_empty=(endpoint != "drivers"))
                    filename = f"openf1_{year}_{slug(event_name)}_{session_slug}_{endpoint}.csv"
                    save_csv(df, source_dir / filename)

                    if len(df):
                        status = "ok"
                        message = ""
                    elif status_code == 404:
                        status = "empty_or_unavailable"
                        message = "404 from OpenF1; likely future/unpopulated endpoint for this session."
                    else:
                        status = "empty_or_unavailable"
                        message = ""

                    manifest.append({
                        "source": "openf1",
                        "session": session_name,
                        "table": endpoint,
                        "rows": len(df),
                        "columns": len(df.columns),
                        "status": status,
                        "filename": f"openf1/{filename}",
                        "message": message,
                    })
                    print(f"[OpenF1] {session_name} {endpoint}: {len(df)} rows ({status})")
                    time.sleep(0.15)
                except Exception as exc:
                    manifest.append({
                        "source": "openf1",
                        "session": session_name,
                        "table": endpoint,
                        "rows": 0,
                        "columns": 0,
                        "status": "error",
                        "message": str(exc),
                    })
    except Exception as exc:
        manifest.append({"source": "openf1", "table": "openf1_run", "rows": 0, "status": "error", "message": str(exc)})

    return manifest


def td_to_seconds(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in list(out.columns):
        if pd.api.types.is_timedelta64_dtype(out[col]):
            out[f"{col}_seconds"] = out[col].dt.total_seconds()
    return out


def attr_df(session: Any, attr: str) -> pd.DataFrame:
    try:
        obj = getattr(session, attr)
        if obj is None:
            return pd.DataFrame()
        if hasattr(obj, "copy"):
            return td_to_seconds(obj.copy())
        return pd.DataFrame(obj)
    except Exception as exc:
        print(f"[FastF1 WARN] {attr}: {exc}")
        return pd.DataFrame()


def run_fastf1(outdir: Path, year: int, event_name: str, sessions: List[str]) -> List[Dict[str, Any]]:
    manifest: List[Dict[str, Any]] = []
    source_dir = outdir / "fastf1"
    source_dir.mkdir(parents=True, exist_ok=True)

    if fastf1 is None:
        manifest.append({"source": "fastf1", "table": "import", "rows": 0, "status": "error", "message": "fastf1 import failed"})
        return manifest

    cache_dir = outdir / "fastf1_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        fastf1.Cache.enable_cache(str(cache_dir))
    except Exception as exc:
        print(f"[FastF1 WARN] cache failed: {exc}")

    try:
        schedule = fastf1.get_event_schedule(year)
        save_csv(schedule, source_dir / f"fastf1_{year}_event_schedule.csv")
        manifest.append({"source": "fastf1", "table": "event_schedule", "rows": len(schedule), "status": "ok", "message": ""})
    except Exception as exc:
        manifest.append({"source": "fastf1", "table": "event_schedule", "rows": 0, "status": "error", "message": str(exc)})

    for code in sessions:
        try:
            session = fastf1.get_session(year, event_name, code)
            load_message = ""

            try:
                session.load(laps=True, telemetry=False, weather=True, messages=True)
            except Exception as first_exc:
                load_message = f"primary_load_failed={first_exc}"
                try:
                    session.load()
                except Exception as second_exc:
                    load_message += f"; fallback_load_failed={second_exc}"

            prefix = f"fastf1_{year}_{slug(event_name)}_{slug(code)}"
            tables = {
                "results": attr_df(session, "results"),
                "laps": attr_df(session, "laps"),
                "weather": attr_df(session, "weather_data"),
                "race_control": attr_df(session, "race_control_messages"),
            }

            try:
                save_csv(pd.DataFrame([dict(session.event)]), source_dir / f"{prefix}_event_metadata.csv")
            except Exception:
                pass

            for table_name, df in tables.items():
                filename = f"{prefix}_{table_name}.csv"
                save_csv(df, source_dir / filename)
                manifest.append({
                    "source": "fastf1",
                    "session": code,
                    "table": table_name,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "status": "ok" if len(df) else "empty_or_unavailable",
                    "filename": f"fastf1/{filename}",
                    "message": load_message if not len(df) else "",
                })
                print(f"[FastF1] {code} {table_name}: {len(df)} rows")
        except Exception as exc:
            manifest.append({"source": "fastf1", "session": code, "table": "session_load", "rows": 0, "status": "error", "message": str(exc)})

    return manifest


def readiness(manifest: List[Dict[str, Any]]) -> Dict[str, Any]:
    df = pd.DataFrame(manifest)
    if df.empty:
        return {"overall": "not_ready", "recommendation": "No source rows were created."}

    def rows(source: str, table: str) -> int:
        if not {"source", "table", "rows"}.issubset(df.columns):
            return 0
        subset = df[(df["source"].eq(source)) & (df["table"].eq(table))]
        return int(subset["rows"].fillna(0).sum()) if not subset.empty else 0

    openf1_laps = rows("openf1", "laps")
    openf1_weather = rows("openf1", "weather")
    fastf1_laps = rows("fastf1", "laps")
    fastf1_results = rows("fastf1", "results")
    openf1_sessions = rows("openf1", "selected_sessions")

    if openf1_laps > 0 and openf1_weather > 0:
        overall = "model_ready_primary_openf1"
        rec = "Use OpenF1 as primary row-level source; use FastF1 as cross-check."
    elif fastf1_laps > 0:
        overall = "model_ready_primary_fastf1"
        rec = "Use FastF1 as primary timing source."
    elif fastf1_results > 0:
        overall = "result_only_crosscheck"
        rec = "Use as results cross-check only; rerun later for timing/weather."
    elif openf1_sessions > 0:
        overall = "scheduled_but_not_populated"
        rec = "Meeting/sessions exist, but row-level timing endpoints are not populated yet. Rerun after session completion or later propagation."
    else:
        overall = "not_ready"
        rec = "Rerun later or inspect source errors."

    return {
        "overall": overall,
        "openf1_selected_sessions": openf1_sessions,
        "openf1_laps": openf1_laps,
        "openf1_weather": openf1_weather,
        "fastf1_laps": fastf1_laps,
        "fastf1_results": fastf1_results,
        "recommendation": rec,
    }


def zip_dir(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file() and path != zip_path:
                zf.write(path, path.relative_to(source_dir))


def copy_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if path.is_file():
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--event-name", default="Spanish Grand Prix")
    parser.add_argument("--country-name", default="Spain")
    parser.add_argument("--sessions", default="FP3,Q,R")
    parser.add_argument("--out-public", default="public")
    args = parser.parse_args()

    year = args.year
    event_name = args.event_name
    country_name = args.country_name
    sessions = parse_sessions(args.sessions)
    run_tag = now_tag()
    event_slug = slug(event_name)

    work = Path("_work") / f"{year}_{event_slug}_{run_tag}"
    work.mkdir(parents=True, exist_ok=True)

    run_config = {
        "year": year,
        "event_name": event_name,
        "country_name": country_name,
        "sessions": sessions,
        "run_tag": run_tag,
        "run_started_utc": now_iso(),
    }
    save_json(run_config, work / "run_config.json")

    manifest: List[Dict[str, Any]] = []
    manifest.extend(run_openf1(work, year, event_name, country_name, sessions))
    manifest.extend(run_fastf1(work, year, event_name, sessions))

    manifest_df = pd.DataFrame(manifest)
    save_csv(manifest_df, work / "combined_source_manifest.csv")

    ready = readiness(manifest)
    save_json(ready, work / "data_readiness.json")
    save_csv(pd.DataFrame([ready]), work / "data_readiness.csv")

    (work / "README_OUTPUT.md").write_text(
        f"""# F1 data publisher output

Year: {year}
Event: {event_name}
Run: {run_tag}

Readiness: {ready.get('overall')}

Recommendation:
{ready.get('recommendation')}
""",
        encoding="utf-8",
    )

    zip_dir(work, work / "latest.zip")

    public = Path(args.out_public)
    latest = public / "latest"
    history = public / "history" / str(year) / event_slug / run_tag

    if latest.exists():
        import shutil
        shutil.rmtree(latest)

    copy_contents(work, latest)
    copy_contents(work, history)

    latest_manifest = {
        "year": year,
        "event_name": event_name,
        "event_slug": event_slug,
        "run_tag": run_tag,
        "generated_utc": now_iso(),
        "readiness": ready,
        "stable_files": {
            "latest_manifest": "latest/latest_manifest.json",
            "data_readiness": "latest/data_readiness.json",
            "combined_source_manifest": "latest/combined_source_manifest.csv",
            "latest_zip": "latest/latest.zip",
        },
        "history_path": f"history/{year}/{event_slug}/{run_tag}/",
    }

    save_json(latest_manifest, latest / "latest_manifest.json")
    save_json(latest_manifest, history / "latest_manifest.json")

    index_html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>F1 Data Publisher</title></head>
<body>
<h1>F1 Data Publisher</h1>
<p>Latest event: {event_name} {year}</p>
<p>Run: {run_tag}</p>
<p>Readiness: {ready.get('overall')}</p>
<ul>
<li><a href="latest/latest_manifest.json">latest_manifest.json</a></li>
<li><a href="latest/data_readiness.json">data_readiness.json</a></li>
<li><a href="latest/combined_source_manifest.csv">combined_source_manifest.csv</a></li>
<li><a href="latest/latest.zip">latest.zip</a></li>
</ul>
</body>
</html>
"""
    (public / "index.html").write_text(index_html, encoding="utf-8")

    print(json.dumps(latest_manifest, indent=2))


if __name__ == "__main__":
    main()
