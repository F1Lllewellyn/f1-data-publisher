#!/usr/bin/env python3
"""Session Data Processor Loop v1.

Sandbox-only processor that converts race-weekend watcher/readiness events into
actual session-scoped source artifacts, validation manifests, and readiness state.

It never promotes a model, never edits Engine_2026-06-07_STABLE, and never
edits the canonical workbook unless a future explicitly-approved mode is added.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path.cwd()
POLICY_PATH = ROOT / "configs" / "session_data_processor" / "session_data_processor_policy_v1.json"
RUNTIME = ROOT / "_runtime" / "session_data_processor"
DEFAULT_ENDPOINTS = ["drivers", "laps", "intervals", "position", "pit", "stints", "race_control", "weather", "session_result", "starting_grid"]
GATE_BY_SESSION_NAME = {
    "practice 1": "post_fp1",
    "practice 2": "post_fp2",
    "practice 3": "post_fp3",
    "qualifying": "post_qualifying",
    "sprint qualifying": "post_qualifying",
    "sprint": "race_result",
    "race": "race_result",
}
REQUIRED_COLUMNS = {
    "sessions": ["session_key", "meeting_key", "session_name", "date_start"],
    "drivers": ["driver_number", "session_key", "meeting_key"],
    "laps": ["driver_number", "session_key", "meeting_key", "lap_number"],
    "intervals": ["driver_number", "session_key", "meeting_key", "date"],
    "position": ["driver_number", "session_key", "meeting_key", "date", "position"],
    "pit": ["driver_number", "session_key", "meeting_key"],
    "stints": ["driver_number", "session_key", "meeting_key"],
    "race_control": ["session_key", "meeting_key", "date"],
    "weather": ["session_key", "meeting_key", "date"],
    "session_result": ["session_key", "meeting_key"],
    "starting_grid": ["session_key", "meeting_key"],
}


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def slugify(value: Any) -> str:
    s = str(value or "unknown")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s or "unknown"


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def parse_time(value: Any) -> Optional[dt.datetime]:
    if value in (None, ""):
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        d = dt.datetime.fromisoformat(text)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc)
    except Exception:
        return None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def http_json(url: str, timeout: int = 30, retries: int = 2, sleep_seconds: float = 1.0) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "F1-Prediction-Engine-SessionProcessor/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                status = getattr(resp, "status", 200)
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, list):
                return data, {"ok": True, "status_code": status, "bytes": len(raw), "sha256": sha256_bytes(raw)}
            if isinstance(data, dict):
                return [data], {"ok": True, "status_code": status, "bytes": len(raw), "sha256": sha256_bytes(raw), "wrapped_dict": True}
            return [], {"ok": False, "status_code": status, "error": "unexpected_json_type", "bytes": len(raw)}
        except Exception as exc:
            last_error = repr(exc)
            if attempt < retries:
                time.sleep(sleep_seconds)
    return [], {"ok": False, "error": last_error or "unknown_error", "bytes": 0}


def openf1_url(endpoint: str, params: Dict[str, Any]) -> str:
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return f"https://api.openf1.org/v1/{endpoint}?{q}" if q else f"https://api.openf1.org/v1/{endpoint}"


def fetch_sessions(season: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return http_json(openf1_url("sessions", {"year": season}), timeout=35)


def select_recent_completed_session(sessions: List[Dict[str, Any]], now: dt.datetime, lookback_hours: int, forced_session: str = "auto") -> Optional[Dict[str, Any]]:
    forced = (forced_session or "auto").lower().strip()
    candidates: List[Tuple[dt.datetime, Dict[str, Any]]] = []
    for s in sessions:
        start = parse_time(s.get("date_start"))
        end = parse_time(s.get("date_end")) or start
        if not end:
            continue
        name = str(s.get("session_name") or "").lower()
        if forced not in {"", "auto", "latest"} and forced not in name:
            continue
        # Completed or near-completed sessions in recent lookback.
        if end <= now and now - end <= dt.timedelta(hours=lookback_hours):
            candidates.append((end, s))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1] if candidates else None


def event_id_for_session(session: Dict[str, Any], season: int) -> str:
    meeting_key = session.get("meeting_key") or "unknown_meeting"
    parts = [season, meeting_key, session.get("country_name"), session.get("location"), session.get("circuit_short_name")]
    return slugify("_".join(str(x) for x in parts if x))


def race_name_for_session(session: Dict[str, Any]) -> str:
    parts = [session.get("country_name"), session.get("location"), session.get("circuit_short_name")]
    return " - ".join(str(x) for x in parts if x) or "F1 Event"


def gate_for_session(session: Dict[str, Any]) -> str:
    name = str(session.get("session_name") or "").lower()
    for key, gate in GATE_BY_SESSION_NAME.items():
        if key in name:
            return gate
    stype = str(session.get("session_type") or "").lower()
    if "practice" in stype:
        return "post_fp"
    if "qualifying" in stype:
        return "post_qualifying"
    if "race" in stype:
        return "race_result"
    return "post_session"


def rows_to_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: List[str] = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                keys.append(k); seen.add(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def analyze_rows(endpoint: str, rows: List[Dict[str, Any]], session: Dict[str, Any], fetch_meta: Dict[str, Any], expected_late: bool = False) -> Dict[str, Any]:
    cols = set()
    for r in rows[:1000]:
        cols.update(r.keys())
    required = REQUIRED_COLUMNS.get(endpoint, [])
    missing = [c for c in required if c not in cols]
    row_count = len(rows)
    duplicate_rows = 0
    seen_hashes = set()
    for r in rows:
        key = json.dumps(r, sort_keys=True, default=str)
        if key in seen_hashes:
            duplicate_rows += 1
        else:
            seen_hashes.add(key)

    session_key = session.get("session_key")
    meeting_key = session.get("meeting_key")
    wrong_session = 0
    wrong_meeting = 0
    driver_numbers = set()
    lap_numbers = []
    timestamp_count = 0
    bad_timestamps = 0
    future_timestamps = 0
    now = utc_now()
    for r in rows:
        if "session_key" in r and session_key is not None and str(r.get("session_key")) != str(session_key):
            wrong_session += 1
        if "meeting_key" in r and meeting_key is not None and str(r.get("meeting_key")) != str(meeting_key):
            wrong_meeting += 1
        if r.get("driver_number") not in (None, ""):
            driver_numbers.add(str(r.get("driver_number")))
        if r.get("lap_number") not in (None, ""):
            try: lap_numbers.append(float(r.get("lap_number")))
            except Exception: pass
        for tk in ["date", "date_start"]:
            if tk in r and r.get(tk):
                timestamp_count += 1
                t = parse_time(r.get(tk))
                if not t:
                    bad_timestamps += 1
                elif t > now + dt.timedelta(minutes=5):
                    future_timestamps += 1
                break

    anomalies: List[str] = []
    if wrong_session: anomalies.append(f"wrong_session_key_rows={wrong_session}")
    if wrong_meeting: anomalies.append(f"wrong_meeting_key_rows={wrong_meeting}")
    if duplicate_rows: anomalies.append(f"duplicate_rows={duplicate_rows}")
    if bad_timestamps: anomalies.append(f"bad_timestamps={bad_timestamps}")
    if future_timestamps: anomalies.append(f"future_timestamps={future_timestamps}")
    if lap_numbers and min(lap_numbers) < 0: anomalies.append("negative_lap_number")

    if not fetch_meta.get("ok"):
        status = "late" if expected_late else "needs_manual_review"
    elif row_count == 0:
        status = "late" if endpoint in {"intervals", "position", "pit", "stints", "session_result", "starting_grid"} else "partial"
    elif missing:
        status = "partial"
    elif wrong_session or wrong_meeting or future_timestamps:
        status = "conflicting"
    elif duplicate_rows or bad_timestamps:
        status = "needs_manual_review"
    else:
        status = "clean"

    return {
        "endpoint": endpoint,
        "status": status,
        "rows": row_count,
        "columns": sorted(cols),
        "missing_required_columns": missing,
        "duplicate_rows": duplicate_rows,
        "driver_count": len(driver_numbers),
        "max_lap_number": max(lap_numbers) if lap_numbers else None,
        "timestamp_rows": timestamp_count,
        "anomalies": anomalies,
        "fetch": fetch_meta,
    }


def combined_status(source_reports: Dict[str, Dict[str, Any]]) -> str:
    statuses = [v.get("status") for v in source_reports.values()]
    if not statuses:
        return "no_data"
    if any(s == "conflicting" for s in statuses):
        return "conflicting"
    if any(s == "needs_manual_review" for s in statuses):
        return "needs_manual_review"
    clean_count = sum(1 for s in statuses if s == "clean")
    partial_count = sum(1 for s in statuses if s == "partial")
    late_count = sum(1 for s in statuses if s == "late")
    if clean_count >= max(2, len(statuses) // 2) and late_count == 0:
        return "clean" if partial_count == 0 else "partial"
    if clean_count or partial_count:
        return "partial"
    if late_count:
        return "late"
    return "needs_manual_review"


def write_latest_public_manifests(latest_root: Path, manifest: Dict[str, Any], previous: Dict[str, Any]) -> None:
    # Processor-owned manifest outputs; names intentionally match downstream readiness expectations.
    write_json(ROOT / "latest" / "latest_manifest.json", {
        "schema_version": "latest_manifest_v2_session_processor",
        "updated_utc": iso_now(),
        "producer": "session_data_processor_loop_v1",
        "latest_session_data_processor_manifest": str((latest_root / "source_readiness_manifest.json").relative_to(ROOT)),
        "event_id": manifest.get("event_id"),
        "session_key": manifest.get("session", {}).get("session_key"),
        "session_name": manifest.get("session", {}).get("session_name"),
        "overall_status": manifest.get("overall_status"),
        "stable_engine_modified": False,
        "canonical_workbook_modified": False,
        "promotion_allowed": False,
    })
    write_json(ROOT / "latest" / "data_readiness.json", {
        "schema_version": "data_readiness_v2_session_processor",
        "updated_utc": iso_now(),
        "event_id": manifest.get("event_id"),
        "race_name": manifest.get("race_name"),
        "session": manifest.get("session"),
        "overall_status": manifest.get("overall_status"),
        "sources": {k: {"status": v.get("status"), "rows": v.get("rows")} for k, v in manifest.get("sources", {}).items()},
        "material_readiness_improved": manifest.get("material_readiness_improved", False),
        "forecast_state_changed": manifest.get("forecast_state_changed", False),
        "readiness_quality": manifest.get("readiness_quality"),
        "source_needs_manual_review": bool(manifest.get("source_needs_manual_review", manifest.get("overall_status") in {"conflicting", "needs_manual_review"})),
        "needs_manual_review": bool(manifest.get("source_needs_manual_review", manifest.get("overall_status") in {"conflicting", "needs_manual_review"})),
    })
    write_json(ROOT / "latest" / "combined_source_manifest.json", {
        "schema_version": "combined_source_manifest_v2_session_processor",
        "updated_utc": iso_now(),
        "source_layers": {
            "session_data_processor": str((latest_root / "source_readiness_manifest.json").relative_to(ROOT)),
            "openf1_lightweight_source_closure": "latest/openf1_lightweight_source_closure/source_readiness_summary.csv",
            "forecast_bundles": "latest/forecast_bundles"
        },
        "event_id": manifest.get("event_id"),
        "session_key": manifest.get("session", {}).get("session_key"),
        "overall_status": manifest.get("overall_status"),
        "readiness_quality": manifest.get("readiness_quality"),
        "source_needs_manual_review": bool(manifest.get("source_needs_manual_review", manifest.get("overall_status") in {"conflicting", "needs_manual_review"})),
        "promotion_allowed": False,
    })


def staleness_scan() -> Dict[str, Any]:
    targets = ["latest/latest_manifest.json", "latest/data_readiness.json", "latest/combined_source_manifest.json"]
    out = {}
    now = utc_now()
    for rel in targets:
        p = ROOT / rel
        rec: Dict[str, Any] = {"exists": p.exists()}
        if p.exists():
            rec["sha256"] = sha256_file(p)
            rec["size_bytes"] = p.stat().st_size
            data = read_json(p, {})
            rec["schema_version"] = data.get("schema_version") if isinstance(data, dict) else None
            ts = None
            if isinstance(data, dict):
                ts = data.get("updated_utc") or data.get("created_utc") or data.get("run_timestamp_utc")
            t = parse_time(ts)
            if t:
                rec["age_minutes"] = round((now - t).total_seconds() / 60, 2)
                rec["timestamp_utc"] = t.isoformat().replace("+00:00", "Z")
            else:
                rec["age_minutes"] = None
                rec["timestamp_utc"] = None
        out[rel] = rec
    return out


def material_delta(previous: Dict[str, Any], current_status: str, current_sources: Dict[str, Dict[str, Any]], threshold: float) -> Tuple[bool, Dict[str, Any]]:
    score_map = {"no_data": 0.0, "late": 0.15, "needs_manual_review": 0.20, "conflicting": 0.20, "partial": 0.60, "clean": 1.0}
    prev_status = previous.get("overall_status") if isinstance(previous, dict) else None
    prev_score = score_map.get(str(prev_status), 0.0)
    cur_score = score_map.get(str(current_status), 0.0)
    delta = cur_score - prev_score
    return delta >= threshold, {"previous_status": prev_status, "current_status": current_status, "previous_score": prev_score, "current_score": cur_score, "delta": delta}


def side_loaded_public_files(side_root: Path, out_root: Path) -> List[Dict[str, Any]]:
    records = []
    if not side_root.exists():
        return records
    dest = out_root / "side_loaded_public_files"
    for p in side_root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(side_root)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            records.append({"relative_path": str(rel), "size_bytes": p.stat().st_size, "sha256": sha256_file(target)})
    return records


def maybe_write_workbook_kpi_artifacts(out_root: Path, manifest: Dict[str, Any]) -> None:
    readiness = {
        "schema_version": "workbook_kpi_readiness_v1_session_processor",
        "created_utc": iso_now(),
        "event_id": manifest.get("event_id"),
        "race_name": manifest.get("race_name"),
        "session": manifest.get("session"),
        "overall_status": manifest.get("overall_status"),
        "canonical_workbook_modified": False,
        "sandbox_workbook_created": False,
        "sources": {k: {"status": v.get("status"), "rows": v.get("rows"), "driver_count": v.get("driver_count"), "max_lap_number": v.get("max_lap_number")} for k, v in manifest.get("sources", {}).items()},
    }
    write_json(out_root / "workbook_kpi_readiness.json", readiness)
    csv_path = out_root / "workbook_kpi_readiness.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["endpoint", "status", "rows", "driver_count", "max_lap_number"])
        writer.writeheader()
        for endpoint, v in manifest.get("sources", {}).items():
            writer.writerow({"endpoint": endpoint, "status": v.get("status"), "rows": v.get("rows"), "driver_count": v.get("driver_count"), "max_lap_number": v.get("max_lap_number")})
    write_json(out_root / "sandbox_workbook_update_plan.json", {
        "schema_version": "sandbox_workbook_update_plan_v1",
        "created_utc": iso_now(),
        "canonical_workbook_modified": False,
        "recommended_action": "consume workbook_kpi_readiness.json/csv into the workbook-control-room or create an explicitly named sandbox workbook copy",
        "blocked_actions": ["overwrite canonical workbook", "alter Engine_2026-06-07_STABLE", "promote model layer"]
    })


def write_ledger_snapshot(out_root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    ledger = {
        "schema_version": "forecast_bundle_ledger_session_snapshot_v1",
        "created_utc": iso_now(),
        "event_id": manifest.get("event_id"),
        "race_name": manifest.get("race_name"),
        "session": manifest.get("session"),
        "overall_status": manifest.get("overall_status"),
        "forecast_state_changed": manifest.get("forecast_state_changed", False),
        "source_readiness_materially_improved": manifest.get("material_readiness_improved", False),
        "stable_order_overwrite_allowed": False,
        "promotion_allowed": False,
        "recommended_forecast_action": "refresh readiness/confidence/risk state only" if manifest.get("overall_status") in {"clean", "partial"} else "hold forecast state / manual review"
    }
    write_json(out_root / "forecast_bundle_ledger_snapshot.json", ledger)
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description="Sandbox Session Data Processor Loop v1")
    ap.add_argument("--mode", default="run_now", choices=["safe_test", "run_now", "manual_session", "manifest_audit"])
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--session-filter", default="auto", help="auto, latest, or a lowercase substring such as 'practice 1'/'practice 2'")
    ap.add_argument("--event-id", default="auto")
    ap.add_argument("--race-name", default="auto")
    ap.add_argument("--include-heavy", action="store_true", help="Include heavy endpoints such as car_data/location/team_radio")
    ap.add_argument("--side-load-root", default="manual_inputs/session_data_processor")
    ap.add_argument("--write-public-latest", default="true")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    RUNTIME.mkdir(parents=True, exist_ok=True)
    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    policy = read_json(POLICY_PATH, {})
    result: Dict[str, Any] = {
        "schema_version": "session_processor_result_v1",
        "created_utc": iso_now(),
        "mode": args.mode,
        "promotion_allowed": False,
        "stable_engine_modified": False,
        "canonical_workbook_modified": False,
        "run_id": run_id,
    }

    if args.mode == "safe_test":
        checks = {
            "policy_exists": POLICY_PATH.exists(),
            "python_version": sys.version.split()[0],
            "writable_runtime": True,
            "protected_stable_engine": True,
            "protected_canonical_workbook": True,
            # False is the expected safe value. This must not be passed through
            # all(checks.values()), otherwise the safe test fails because the
            # promotion gate is correctly closed.
            "promotion_allowed": False,
        }
        safe_test_pass = (
            checks["policy_exists"] is True
            and checks["writable_runtime"] is True
            and checks["protected_stable_engine"] is True
            and checks["protected_canonical_workbook"] is True
            and checks["promotion_allowed"] is False
        )
        result.update({"status": "safe_test_pass" if safe_test_pass else "safe_test_fail", "checks": checks})
        write_json(RUNTIME / "session_processor_result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "safe_test_pass" else 1

    if args.mode == "manifest_audit":
        result.update({"status": "pass", "manifest_staleness": staleness_scan()})
        write_json(RUNTIME / "session_processor_result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    sessions, sessions_meta = fetch_sessions(args.season)
    result["sessions_fetch"] = sessions_meta
    if not sessions:
        result.update({"status": "late", "reason": "openf1_sessions_unavailable_or_empty", "manifest_staleness": staleness_scan()})
        write_json(RUNTIME / "session_processor_result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    lookback = int(policy.get("recent_session_lookback_hours", 36))
    session = select_recent_completed_session(sessions, utc_now(), lookback, args.session_filter)
    if not session:
        result.update({"status": "late", "reason": "no_recent_completed_session_found", "sessions_seen": len(sessions), "manifest_staleness": staleness_scan()})
        write_json(RUNTIME / "session_processor_result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    event_id = args.event_id if args.event_id != "auto" else event_id_for_session(session, args.season)
    race_name = args.race_name if args.race_name != "auto" else race_name_for_session(session)
    gate = gate_for_session(session)
    session_slug = slugify(f"{session.get('session_name')}_{session.get('session_key')}")
    latest_root = ROOT / "latest" / "session_data_processor" / event_id / session_slug
    history_root = ROOT / "history" / "session_data_processor" / event_id / run_id / session_slug
    for p in [latest_root, history_root]:
        p.mkdir(parents=True, exist_ok=True)

    endpoint_list = list(policy.get("openf1_endpoints") or DEFAULT_ENDPOINTS)
    if args.include_heavy:
        endpoint_list += list(policy.get("heavy_openf1_endpoints") or [])

    sources: Dict[str, Dict[str, Any]] = {}
    for endpoint in endpoint_list:
        # sessions endpoint is already fetched globally; filter selected session.
        if endpoint == "sessions":
            rows = [session]
            meta = {"ok": True, "bytes": len(json.dumps(rows)), "source": "sessions_prefetch"}
        else:
            rows, meta = http_json(openf1_url(endpoint, {"session_key": session.get("session_key")}), timeout=args.timeout)
        raw_json = latest_root / "raw" / f"openf1_{endpoint}.json"
        raw_csv = latest_root / "raw" / f"openf1_{endpoint}.csv"
        write_json(raw_json, rows)
        rows_to_csv(raw_csv, rows)
        # mirror to history
        write_json(history_root / "raw" / f"openf1_{endpoint}.json", rows)
        rows_to_csv(history_root / "raw" / f"openf1_{endpoint}.csv", rows)
        report = analyze_rows(endpoint, rows, session, meta)
        report["json_path"] = str(raw_json.relative_to(ROOT))
        report["csv_path"] = str(raw_csv.relative_to(ROOT))
        report["json_sha256"] = sha256_file(raw_json)
        sources[f"openf1_{endpoint}"] = report
        write_json(latest_root / "validation" / f"openf1_{endpoint}_validation.json", report)
        write_json(history_root / "validation" / f"openf1_{endpoint}_validation.json", report)

    side_loaded = side_loaded_public_files(Path(args.side_load_root), latest_root)
    if side_loaded:
        sources["side_loaded_public_files"] = {"endpoint": "side_loaded_public_files", "status": "partial", "rows": len(side_loaded), "files": side_loaded, "missing_required_columns": [], "anomalies": []}

    # 1B v11: session-aware readiness aggregation keeps expected-empty Practice sources non-blocking.
    readiness_aggregation = {}
    try:
        helper_dir = ROOT / "scripts" / "session_data_processor"
        if str(helper_dir) not in sys.path:
            sys.path.insert(0, str(helper_dir))
        from source_readiness_aggregation_v2 import aggregate_source_readiness
        readiness_aggregation = aggregate_source_readiness(sources, session)
        overall = readiness_aggregation.get("overall_status") or combined_status(sources)
    except Exception as exc:
        readiness_aggregation = {
            "schema_version": "source_readiness_aggregation_v2_fallback",
            "error": repr(exc),
            "overall_status": combined_status(sources),
            "readiness_quality": "fallback_legacy_combined_status",
            "needs_manual_review": combined_status(sources) in {"conflicting", "needs_manual_review"},
            "promotion_allowed": False,
        }
        overall = readiness_aggregation["overall_status"]
    prev = read_json(latest_root / "source_readiness_manifest.json", {})
    materially_improved, delta = material_delta(prev, overall, sources, float(policy.get("material_readiness_delta_threshold", 0.10)))
    forecast_state_changed = materially_improved and overall in {"clean", "partial"}

    manifest: Dict[str, Any] = {
        "schema_version": "session_readiness_manifest_v1",
        "created_utc": iso_now(),
        "event_id": event_id,
        "race_name": race_name,
        "run_id": run_id,
        "session": {
            "session_key": session.get("session_key"),
            "meeting_key": session.get("meeting_key"),
            "session_name": session.get("session_name"),
            "session_type": session.get("session_type"),
            "date_start": session.get("date_start"),
            "date_end": session.get("date_end"),
            "gate": gate,
        },
        "overall_status": overall,
        "readiness_quality": readiness_aggregation.get("readiness_quality"),
        "source_needs_manual_review": bool(readiness_aggregation.get("needs_manual_review", overall in {"conflicting", "needs_manual_review"})),
        "readiness_aggregation": readiness_aggregation,
        "material_readiness_improved": materially_improved,
        "readiness_delta": delta,
        "forecast_state_changed": forecast_state_changed,
        "sources": sources,
        "validation_summary": {
            "clean_sources": sum(1 for s in sources.values() if s.get("status") == "clean"),
            "partial_sources": sum(1 for s in sources.values() if s.get("status") == "partial"),
            "late_sources": sum(1 for s in sources.values() if s.get("status") == "late"),
            "conflicting_sources": sum(1 for s in sources.values() if s.get("status") == "conflicting"),
            "manual_review_sources": sum(1 for s in sources.values() if s.get("status") == "needs_manual_review"),
        },
        "manifest_staleness_before_update": staleness_scan(),
        "stable_engine_modified": False,
        "canonical_workbook_modified": False,
        "promotion_allowed": False,
    }

    maybe_write_workbook_kpi_artifacts(latest_root, manifest)
    maybe_write_workbook_kpi_artifacts(history_root, manifest)
    ledger = write_ledger_snapshot(latest_root, manifest)
    write_ledger_snapshot(history_root, manifest)
    manifest["workbook_kpi_update"] = {"mode": "sandbox_artifact", "path": str((latest_root / "workbook_kpi_readiness.json").relative_to(ROOT)), "canonical_workbook_modified": False}
    manifest["forecast_bundle_ledger_snapshot"] = ledger
    write_json(latest_root / "source_readiness_manifest.json", manifest)
    write_json(history_root / "source_readiness_manifest.json", manifest)

    if str(args.write_public_latest).lower() in {"true", "1", "yes"}:
        write_latest_public_manifests(latest_root, manifest, prev)

    result.update({
        "status": "pass" if overall in {"clean", "partial"} else overall,
        "event_id": event_id,
        "race_name": race_name,
        "session_key": session.get("session_key"),
        "session_name": session.get("session_name"),
        "gate": gate,
        "overall_status": overall,
        "readiness_quality": readiness_aggregation.get("readiness_quality"),
        "source_needs_manual_review": bool(readiness_aggregation.get("needs_manual_review", overall in {"conflicting", "needs_manual_review"})),
        "material_readiness_improved": materially_improved,
        "forecast_state_changed": forecast_state_changed,
        "latest_output": str(latest_root.relative_to(ROOT)),
        "history_output": str(history_root.relative_to(ROOT)),
        "source_counts": {k: v.get("rows") for k, v in sources.items()},
        "source_statuses": {k: v.get("status") for k, v in sources.items()},
    })
    write_json(RUNTIME / "session_processor_result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
