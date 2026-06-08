#!/usr/bin/env python3
"""
F1 universal auto data publisher v4.1.

Permanent/no-weekly-edit design:
- GitHub Actions runs on a broad race-weekend cadence.
- The script auto-detects the active/next race weekend using OpenF1 meetings.
- OpenF1 remains the live/session-data discovery layer.
- FastF1 now has a schedule resolver:
    OpenF1-selected event -> FastF1 schedule fuzzy/date/country match -> FastF1 sessions.
- Publishes stable latest_manifest.json/data_readiness/latest.zip.
- Manual override still works but is optional.

Car data remains off by default for stability.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import zipfile
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

try:
    import fastf1
except Exception:
    fastf1 = None


OPENF1_BASE = "https://api.openf1.org/v1"

CORE_OPENF1_ENDPOINTS = [
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

SESSION_NAME_TO_CODE = {
    "practice 1": "FP1",
    "free practice 1": "FP1",
    "practice 2": "FP2",
    "free practice 2": "FP2",
    "practice 3": "FP3",
    "free practice 3": "FP3",
    "qualifying": "Q",
    "sprint qualifying": "SQ",
    "sprint shootout": "SQ",
    "sprint": "S",
    "sprint race": "S",
    "race": "R",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def normalize_name(value: str) -> str:
    text = norm(value)
    text = text.replace("grand prix", "")
    text = text.replace("gp", "")
    text = text.replace("formula 1", "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    a_norm = normalize_name(a)
    b_norm = normalize_name(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.92
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_tag() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return now_utc().isoformat()


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        try:
            dt = pd.to_datetime(value, utc=True, errors="coerce")
            if pd.isna(dt):
                return None
            return dt.to_pydatetime().astimezone(timezone.utc)
        except Exception:
            return None


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
            response = requests.get(url, params=params, timeout=120)
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


def session_name_to_code(session_name: str) -> str:
    return SESSION_NAME_TO_CODE.get(norm(session_name), slug(session_name).upper())


def session_name_matches(session_name: str, requested_code: str) -> bool:
    requested_code = requested_code.upper()
    session_norm = norm(session_name)
    allowed_names = SESSION_CODE_TO_NAMES.get(requested_code)
    if allowed_names:
        return session_norm in allowed_names
    return session_norm == norm(requested_code)


def select_sessions(session_df: pd.DataFrame, requested: List[str]) -> pd.DataFrame:
    if session_df.empty or "session_name" not in session_df.columns:
        return session_df
    mask = pd.Series([False] * len(session_df))
    for req in requested:
        mask = mask | session_df["session_name"].astype(str).apply(lambda x: session_name_matches(x, req))
    return session_df[mask.values].copy()


def load_config(path: Optional[str]) -> Dict[str, Any]:
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {}


def meeting_start_end(row: pd.Series) -> Tuple[Optional[datetime], Optional[datetime]]:
    start = parse_datetime(row.get("date_start"))
    end = parse_datetime(row.get("date_end"))
    if start is None:
        start = parse_datetime(row.get("meeting_start"))
    if end is None:
        end = parse_datetime(row.get("meeting_end"))
    return start, end


def choose_auto_meeting(year: int, cfg: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    meetings, _ = openf1("meetings", {"year": year})
    state: Dict[str, Any] = {
        "auto_event": True,
        "meeting_selection": "none",
        "meeting_reason": "",
        "now_utc": now_iso(),
        "meetings_rows": len(meetings),
    }

    if meetings.empty:
        return meetings, {**state, "meeting_reason": "No meetings returned by OpenF1."}

    current = now_utc()
    lead_hours = int(cfg.get("auto_event_lead_hours", 48))
    lag_hours = int(cfg.get("auto_event_lag_hours", 36))
    next_event_days = int(cfg.get("auto_event_next_days", 10))
    recent_days = int(cfg.get("auto_event_recent_days", 3))

    candidates = []
    for idx, row in meetings.iterrows():
        start, end = meeting_start_end(row)
        if start is None:
            continue
        if end is None:
            end = start + timedelta(days=3)
        candidates.append((idx, start, end, row))

    active = [(idx, start, end, row) for idx, start, end, row in candidates
              if start - timedelta(hours=lead_hours) <= current <= end + timedelta(hours=lag_hours)]
    if active:
        active.sort(key=lambda x: x[1])
        idx, start, end, _ = active[0]
        return meetings.loc[[idx]].copy(), {
            **state,
            "meeting_selection": "active_window",
            "meeting_reason": f"now is within start-{lead_hours}h to end+{lag_hours}h",
            "meeting_start_utc": start.isoformat(),
            "meeting_end_utc": end.isoformat(),
        }

    future = [(idx, start, end, row) for idx, start, end, row in candidates
              if current < start <= current + timedelta(days=next_event_days)]
    if future:
        future.sort(key=lambda x: x[1])
        idx, start, end, _ = future[0]
        return meetings.loc[[idx]].copy(), {
            **state,
            "meeting_selection": "next_event",
            "meeting_reason": f"next meeting within {next_event_days} days",
            "meeting_start_utc": start.isoformat(),
            "meeting_end_utc": end.isoformat(),
        }

    recent = [(idx, start, end, row) for idx, start, end, row in candidates
              if end <= current <= end + timedelta(days=recent_days)]
    if recent:
        recent.sort(key=lambda x: x[2], reverse=True)
        idx, start, end, _ = recent[0]
        return meetings.loc[[idx]].copy(), {
            **state,
            "meeting_selection": "recent_event",
            "meeting_reason": f"recent meeting ended within {recent_days} days",
            "meeting_start_utc": start.isoformat(),
            "meeting_end_utc": end.isoformat(),
        }

    return meetings.head(0).copy(), {**state, "meeting_selection": "no_active_or_nearby_event", "meeting_reason": "No active/near/fresh meeting found."}


def choose_manual_meeting(year: int, country_name: str, event_name: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    state = {
        "auto_event": False,
        "meeting_selection": "manual_override",
        "meeting_reason": "Manual event_name/country_name supplied.",
        "now_utc": now_iso(),
    }
    meetings = pd.DataFrame()
    if country_name:
        meetings, _ = openf1("meetings", {"year": year, "country_name": country_name})
    if meetings.empty and event_name:
        all_meetings, _ = openf1("meetings", {"year": year})
        if not all_meetings.empty:
            target = slug(event_name)
            mask = all_meetings.apply(lambda row: target in slug(" ".join(str(v) for v in row.values)), axis=1)
            meetings = all_meetings[mask.values].copy()
    return meetings, state


def derive_event_fields(meeting_row: pd.Series, fallback_event_name: str = "", fallback_country_name: str = "") -> Tuple[str, str]:
    event_name = (
        meeting_row.get("meeting_name")
        or meeting_row.get("meeting_official_name")
        or meeting_row.get("event_name")
        or fallback_event_name
        or "Unknown Grand Prix"
    )
    country_name = meeting_row.get("country_name") or fallback_country_name or ""
    return str(event_name), str(country_name)


def choose_event_date_from_openf1(selected_meeting: pd.DataFrame) -> Optional[datetime]:
    if selected_meeting.empty:
        return None
    start, end = meeting_start_end(selected_meeting.iloc[0])
    return start


def resolve_fastf1_event(
    year: int,
    openf1_event_name: str,
    openf1_country_name: str,
    selected_meeting: pd.DataFrame,
    cfg: Dict[str, Any],
) -> Tuple[Any, Dict[str, Any], pd.DataFrame]:
    """
    Return event reference usable by fastf1.get_session plus diagnostic state.
    FastF1 is matched using:
    - date proximity
    - country/location similarity
    - event-name similarity
    """
    state: Dict[str, Any] = {
        "fastf1_resolver": "v4.1",
        "fastf1_event_match": "not_run",
        "openf1_event_name": openf1_event_name,
        "openf1_country_name": openf1_country_name,
    }

    if fastf1 is None:
        return openf1_event_name, {**state, "fastf1_event_match": "fastf1_import_failed"}, pd.DataFrame()

    try:
        schedule = fastf1.get_event_schedule(year)
    except Exception as exc:
        return openf1_event_name, {**state, "fastf1_event_match": "schedule_error", "message": str(exc)}, pd.DataFrame()

    if schedule is None or len(schedule) == 0:
        return openf1_event_name, {**state, "fastf1_event_match": "schedule_empty"}, pd.DataFrame()

    schedule_df = pd.DataFrame(schedule.copy())
    openf1_date = choose_event_date_from_openf1(selected_meeting)

    best = None
    scored_rows = []

    for idx, row in schedule_df.iterrows():
        event_name_candidates = [
            row.get("EventName", ""),
            row.get("OfficialEventName", ""),
            row.get("EventName", ""),
        ]
        country_candidates = [
            row.get("Country", ""),
            row.get("Location", ""),
        ]

        event_name_score = max(similarity(openf1_event_name, str(x)) for x in event_name_candidates if str(x).strip()) if event_name_candidates else 0.0
        country_score = max(similarity(openf1_country_name, str(x)) for x in country_candidates if str(x).strip()) if country_candidates else 0.0

        fastf1_date = None
        for col in ["EventDate", "Session5Date", "Session4Date", "Session1Date"]:
            if col in schedule_df.columns:
                fastf1_date = parse_datetime(row.get(col))
                if fastf1_date:
                    break

        if openf1_date and fastf1_date:
            days_diff = abs((fastf1_date.date() - openf1_date.date()).days)
            date_score = max(0.0, 1.0 - (days_diff / 7.0))
        else:
            days_diff = None
            date_score = 0.0

        round_score = 0.0
        if "RoundNumber" in schedule_df.columns and "round" in selected_meeting.columns:
            try:
                round_score = 1.0 if int(row.get("RoundNumber")) == int(selected_meeting.iloc[0].get("round")) else 0.0
            except Exception:
                round_score = 0.0

        total = (event_name_score * 0.45) + (country_score * 0.20) + (date_score * 0.25) + (round_score * 0.10)

        scored = {
            "idx": int(idx) if str(idx).isdigit() else str(idx),
            "fastf1_event_name": str(row.get("EventName", "")),
            "fastf1_official_event_name": str(row.get("OfficialEventName", "")),
            "fastf1_country": str(row.get("Country", "")),
            "fastf1_location": str(row.get("Location", "")),
            "event_name_score": round(event_name_score, 3),
            "country_score": round(country_score, 3),
            "date_score": round(date_score, 3),
            "round_score": round(round_score, 3),
            "days_diff": days_diff,
            "total_score": round(total, 3),
        }
        scored_rows.append(scored)

        if best is None or total > best[0]:
            best = (total, idx, row, scored)

    scored_df = pd.DataFrame(scored_rows).sort_values("total_score", ascending=False) if scored_rows else pd.DataFrame()

    threshold = float(cfg.get("fastf1_match_threshold", 0.55))
    if best and best[0] >= threshold:
        _, idx, row, scored = best
        event_ref = row.get("EventName") or openf1_event_name
        confidence = "high" if best[0] >= 0.80 else "medium"
        state.update({
            "fastf1_event_match": "ok",
            "fastf1_event_name_used": str(event_ref),
            "fastf1_match_confidence": confidence,
            "fastf1_match_score": round(best[0], 3),
            "fastf1_match_details": scored,
        })
        return event_ref, state, scored_df

    fallback = openf1_event_name
    state.update({
        "fastf1_event_match": "fallback_openf1_name",
        "fastf1_event_name_used": fallback,
        "fastf1_match_confidence": "low",
        "fastf1_match_score": round(best[0], 3) if best else 0.0,
        "fastf1_match_details": best[3] if best else {},
        "message": "No FastF1 schedule match cleared threshold; falling back to OpenF1 event name.",
    })
    return fallback, state, scored_df


def run_openf1(outdir: Path, year: int, event_name: str, sessions: List[str], selected_meeting: pd.DataFrame) -> List[Dict[str, Any]]:
    manifest: List[Dict[str, Any]] = []
    source_dir = outdir / "openf1"
    source_dir.mkdir(parents=True, exist_ok=True)

    save_csv(selected_meeting, source_dir / "openf1_selected_meeting.csv")
    manifest.append({
        "source": "openf1",
        "table": "selected_meeting",
        "rows": len(selected_meeting),
        "status": "ok" if len(selected_meeting) else "empty",
        "message": "",
    })

    if selected_meeting.empty:
        return manifest

    meeting_key = int(selected_meeting.iloc[0]["meeting_key"])
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

    for _, s in selected.iterrows():
        session_key = int(s["session_key"])
        session_name = str(s.get("session_name", session_key))
        session_slug = slug(session_name)
        session_code = session_name_to_code(session_name)

        for endpoint in CORE_OPENF1_ENDPOINTS:
            try:
                df, status_code = openf1(endpoint, {"session_key": session_key}, allow_404_empty=(endpoint != "drivers"))
                filename = f"openf1_{year}_{slug(event_name)}_{session_slug}_{endpoint}.csv"
                save_csv(df, source_dir / filename)

                if len(df):
                    status = "ok"
                    message = ""
                elif status_code == 404:
                    status = "empty_or_unavailable"
                    message = "404 from OpenF1; likely future/unpopulated endpoint."
                else:
                    status = "empty_or_unavailable"
                    message = ""

                manifest.append({
                    "source": "openf1",
                    "session": session_name,
                    "session_code": session_code,
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
                    "session_code": session_code,
                    "table": endpoint,
                    "rows": 0,
                    "columns": 0,
                    "status": "error",
                    "message": str(exc),
                })

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


def run_fastf1(
    outdir: Path,
    year: int,
    event_ref: Any,
    sessions: List[str],
    cfg: Dict[str, Any],
    resolver_state: Dict[str, Any],
    scored_df: pd.DataFrame,
) -> List[Dict[str, Any]]:
    manifest: List[Dict[str, Any]] = []
    source_dir = outdir / "fastf1"
    source_dir.mkdir(parents=True, exist_ok=True)

    save_json(resolver_state, source_dir / "fastf1_event_resolver_state.json")
    if not scored_df.empty:
        save_csv(scored_df, source_dir / "fastf1_event_match_candidates.csv")

    manifest.append({
        "source": "fastf1",
        "table": "event_resolver",
        "rows": 1,
        "status": resolver_state.get("fastf1_event_match", "unknown"),
        "message": json.dumps({
            "event_name_used": resolver_state.get("fastf1_event_name_used"),
            "confidence": resolver_state.get("fastf1_match_confidence"),
            "score": resolver_state.get("fastf1_match_score"),
        }),
    })

    if not bool(cfg.get("include_fastf1", True)):
        manifest.append({"source": "fastf1", "table": "fastf1_run", "rows": 0, "status": "skipped", "message": "include_fastf1=false"})
        return manifest

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
            session = fastf1.get_session(year, event_ref, code)
            load_message = ""
            try:
                session.load(laps=True, telemetry=False, weather=True, messages=True)
            except Exception as first_exc:
                load_message = f"primary_load_failed={first_exc}"
                try:
                    session.load()
                except Exception as second_exc:
                    load_message += f"; fallback_load_failed={second_exc}"

            prefix = f"fastf1_{year}_{slug(str(event_ref))}_{slug(code)}"
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

    def status(source: str, table: str) -> str:
        if not {"source", "table", "status"}.issubset(df.columns):
            return ""
        subset = df[(df["source"].eq(source)) & (df["table"].eq(table))]
        return str(subset["status"].iloc[0]) if not subset.empty else ""

    selected_meeting = rows("openf1", "selected_meeting")
    selected_sessions = rows("openf1", "selected_sessions")
    openf1_laps = rows("openf1", "laps")
    openf1_weather = rows("openf1", "weather")
    openf1_race_control = rows("openf1", "race_control")
    fastf1_laps = rows("fastf1", "laps")
    fastf1_results = rows("fastf1", "results")
    fastf1_resolver_status = status("fastf1", "event_resolver")

    if openf1_laps > 0 and openf1_weather > 0:
        overall = "model_ready_primary_openf1"
        rec = "Use OpenF1 as primary row-level source; use FastF1 as cross-check."
    elif fastf1_laps > 0:
        overall = "model_ready_primary_fastf1"
        rec = "Use FastF1 as primary timing source."
    elif fastf1_results > 0:
        overall = "result_only_crosscheck"
        rec = "Use as results cross-check only; rerun later for timing/weather."
    elif selected_sessions > 0:
        overall = "scheduled_but_not_populated"
        rec = "Race weekend/session metadata exists, but row-level timing endpoints are not populated yet."
    elif selected_meeting > 0:
        overall = "meeting_found_no_sessions"
        rec = "Meeting was found but requested sessions are not available yet."
    else:
        overall = "no_active_event_window"
        rec = "No active/nearby event found by auto-selection."

    return {
        "overall": overall,
        "openf1_selected_meeting": selected_meeting,
        "openf1_selected_sessions": selected_sessions,
        "openf1_laps": openf1_laps,
        "openf1_weather": openf1_weather,
        "openf1_race_control": openf1_race_control,
        "fastf1_laps": fastf1_laps,
        "fastf1_results": fastf1_results,
        "fastf1_resolver_status": fastf1_resolver_status,
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
    parser.add_argument("--config", default="config/race_config.json")
    parser.add_argument("--year", type=int)
    parser.add_argument("--event-name")
    parser.add_argument("--country-name")
    parser.add_argument("--sessions")
    parser.add_argument("--out-public", default="public")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.year is not None:
        cfg["year"] = args.year
    if args.event_name is not None and str(args.event_name).strip():
        cfg["event_name"] = args.event_name
    if args.country_name is not None and str(args.country_name).strip():
        cfg["country_name"] = args.country_name
    if args.sessions is not None:
        cfg["sessions"] = parse_sessions(args.sessions)

    year = int(cfg.get("year", now_utc().year))
    sessions = parse_sessions(cfg.get("sessions", ["FP1", "FP2", "FP3", "Q", "R"]))
    manual_event_name = cfg.get("event_name", "")
    manual_country_name = cfg.get("country_name", "")
    auto_event = bool(cfg.get("auto_event", True))

    if auto_event and not (manual_event_name and manual_country_name):
        selected_meeting, event_state = choose_auto_meeting(year, cfg)
    else:
        selected_meeting, event_state = choose_manual_meeting(year, manual_country_name, manual_event_name)

    if selected_meeting.empty:
        event_name = manual_event_name or "No Active F1 Event"
        country_name = manual_country_name or ""
    else:
        event_name, country_name = derive_event_fields(selected_meeting.iloc[0], manual_event_name, manual_country_name)

    fastf1_event_ref, fastf1_state, fastf1_candidates = resolve_fastf1_event(
        year=year,
        openf1_event_name=event_name,
        openf1_country_name=country_name,
        selected_meeting=selected_meeting,
        cfg=cfg,
    )

    run_tag = now_tag()
    event_slug = slug(event_name)
    work = Path("_work") / f"{year}_{event_slug}_{run_tag}"
    work.mkdir(parents=True, exist_ok=True)

    event_state = {**event_state, "fastf1": fastf1_state}

    run_config = {
        **cfg,
        "year": year,
        "event_name": event_name,
        "country_name": country_name,
        "sessions": sessions,
        "auto_event_state": event_state,
        "fastf1_event_ref": str(fastf1_event_ref),
        "run_tag": run_tag,
        "run_started_utc": now_iso(),
    }
    save_json(run_config, work / "run_config.json")
    save_json(event_state, work / "auto_event_state.json")

    manifest: List[Dict[str, Any]] = []
    if bool(cfg.get("include_openf1", True)):
        manifest.extend(run_openf1(work, year, event_name, sessions, selected_meeting))
    if bool(cfg.get("include_fastf1", True)) and not selected_meeting.empty:
        manifest.extend(run_fastf1(work, year, fastf1_event_ref, sessions, cfg, fastf1_state, fastf1_candidates))

    manifest_df = pd.DataFrame(manifest)
    save_csv(manifest_df, work / "combined_source_manifest.csv")

    ready = readiness(manifest)
    save_json(ready, work / "data_readiness.json")
    save_csv(pd.DataFrame([ready]), work / "data_readiness.csv")

    (work / "README_OUTPUT.md").write_text(
        f"""# F1 universal auto publisher output

Year: {year}
Event: {event_name}
Country: {country_name}
FastF1 event ref: {fastf1_event_ref}
Run: {run_tag}

Auto event state:
{json.dumps(event_state, indent=2)}

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
        "country_name": country_name,
        "event_slug": event_slug,
        "run_tag": run_tag,
        "generated_utc": now_iso(),
        "auto_event_state": event_state,
        "fastf1_event_ref": str(fastf1_event_ref),
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
<p>Country: {country_name}</p>
<p>FastF1 event ref: {fastf1_event_ref}</p>
<p>Run: {run_tag}</p>
<p>Auto selection: {event_state.get('meeting_selection')}</p>
<p>FastF1 match: {fastf1_state.get('fastf1_event_match')}</p>
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
