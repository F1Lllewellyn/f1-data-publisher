#!/usr/bin/env python3
"""
OpenF1 High-Frequency Auto Ingest for F1 Prediction Engine.

This is intended to run in GitHub Actions.

Modes:
  race    -> Race/Sprint car_data+location, race reliability early-warning features
  prerace -> Practice/Qualifying/Sprint Qualifying car_data+location, pre-race warning metric
  all     -> both

Outputs:
  manifests/*.csv
  features/*.parquet
  metrics/*.csv
  reports/*.md

Authority:
  Risk/fantasy/reporting only. No stable P1-P20 or qualifying P1-P5 rank changes.
"""

import os
import sys
import time
import json
import hashlib
import math
import re
from urllib.parse import urlencode
import zipfile
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests
from dateutil import parser as dtparser
from tqdm.auto import tqdm


BASE_URL = "https://api.openf1.org/v1"

SESSION_TYPES = {
    "race": ["Race", "Sprint"],
    "prerace": ["Practice", "Qualifying", "Sprint Qualifying"],
    "all": ["Practice", "Qualifying", "Sprint Qualifying", "Race", "Sprint"],
}

EXPECTED_ZERO_CANCELLED = ["Bahrain", "Saudi"]


def parse_dt(x):
    if pd.isna(x) or x is None:
        return None
    return dtparser.parse(str(x))


def dt_to_openf1(dt):
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class OpenF1Client:
    def __init__(self, token="", sleep_seconds=0.35, max_retries=5):
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries

    def get(self, endpoint, params=None, timeout=120):
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        params = params or {}
        last_status = None
        last_text = ""

        for attempt in range(self.max_retries):
            try:
                r = requests.get(url, params=params, headers=self.headers, timeout=timeout)
                last_status = r.status_code
                last_text = r.text[:300]

                if r.status_code == 404:
                    return [], {"status_code": 404, "note": "not_found"}
                if r.status_code == 429:
                    sleep = min(90, 2 ** attempt) + 1
                    print(f"429 rate limit: sleeping {sleep}s")
                    time.sleep(sleep)
                    continue
                if r.status_code >= 500:
                    sleep = min(90, 2 ** attempt)
                    print(f"{r.status_code} server error on {endpoint} {params}; sleeping {sleep}s")
                    time.sleep(sleep)
                    continue

                r.raise_for_status()
                time.sleep(self.sleep_seconds)
                return r.json(), {"status_code": r.status_code, "note": "ok"}

            except Exception as e:
                sleep = min(90, 2 ** attempt)
                print(f"Request error on {endpoint} {params}: {e}; sleeping {sleep}s")
                time.sleep(sleep)

        return None, {"status_code": last_status, "note": "failed_after_retries", "text": last_text}


def write_frame(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    elif path.suffix == ".csv":
        df.to_csv(path, index=False)
    else:
        raise ValueError(path)


def discover_sessions(client, year, mode, event_filter=""):
    data, meta = client.get("sessions", {"year": year})
    if data is None:
        raise RuntimeError(f"Could not fetch sessions: {meta}")
    sessions = pd.DataFrame(data)
    if sessions.empty:
        raise RuntimeError(f"No sessions for {year}")

    for col in ["date_start", "date_end"]:
        if col in sessions.columns:
            sessions[col + "_dt"] = sessions[col].apply(lambda x: parse_dt(x) if pd.notna(x) else None)

    now = datetime.now(timezone.utc)
    completed = sessions[sessions["date_end_dt"].notna() & (sessions["date_end_dt"] <= now)].copy()
    completed = completed[completed["session_type"].isin(SESSION_TYPES[mode])].copy()

    if event_filter:
        mask = (
            completed["country_name"].astype(str).str.contains(event_filter, case=False, na=False)
            | completed["meeting_name"].astype(str).str.contains(event_filter, case=False, na=False)
            | completed["location"].astype(str).str.contains(event_filter, case=False, na=False)
        )
        completed = completed[mask].copy()

    # Treat Bahrain/Saudi 2026 as expected-zero cancellations/non-events in this project.
    if "country_name" in completed.columns:
        cancelled_mask = completed["country_name"].astype(str).str.contains("Bahrain|Saudi", case=False, na=False)
        completed = completed[~cancelled_mask].copy()

    sort_cols = [c for c in ["date_start_dt", "meeting_key", "session_key"] if c in completed.columns]
    return completed.sort_values(sort_cols).reset_index(drop=True)


def get_drivers(client, session_key):
    rows, meta = client.get("drivers", {"session_key": int(session_key)})
    df = pd.DataFrame(rows or [])
    if df.empty or "driver_number" not in df.columns:
        return []
    return sorted(df["driver_number"].dropna().astype(int).unique().tolist())


def fetch_endpoint_driver(client, endpoint, session_key, driver_number, fetch_mode):
    # Default safest mode: full driver/session request. OpenF1 can throw 500s on date chunk filters.
    params = {"session_key": int(session_key), "driver_number": int(driver_number)}
    data, meta = client.get(endpoint, params)
    return data, meta, params, "driver_full_session"


def extract_raw(client, sessions, output_dir, fetch_mode):
    raw_dir = output_dir / "raw"
    manifest_dir = output_dir / "manifests"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    driver_rows = []
    session_drivers = {}

    for _, s in tqdm(sessions.iterrows(), total=len(sessions), desc="drivers"):
        sk = int(s["session_key"])
        drivers = get_drivers(client, sk)
        session_drivers[sk] = drivers
        for dn in drivers:
            driver_rows.append({
                "meeting_key": s.get("meeting_key"),
                "session_key": sk,
                "session_name": s.get("session_name"),
                "session_type": s.get("session_type"),
                "country_name": s.get("country_name"),
                "driver_number": dn,
            })

    pd.DataFrame(driver_rows).to_csv(manifest_dir / "session_driver_manifest.csv", index=False)

    for _, s in tqdm(sessions.iterrows(), total=len(sessions), desc="sessions"):
        sk = int(s["session_key"])
        for endpoint in ["car_data", "location"]:
            for dn in tqdm(session_drivers.get(sk, []), desc=f"{endpoint} sk={sk}", leave=False):
                out_path = raw_dir / endpoint / f"session_key={sk}" / f"driver_number={dn}" / "chunk_0000.parquet"

                if out_path.exists():
                    try:
                        n = len(pd.read_parquet(out_path))
                    except Exception:
                        n = ""
                    rows.append({
                        "endpoint": endpoint, "meeting_key": s.get("meeting_key"), "session_key": sk,
                        "session_name": s.get("session_name"), "session_type": s.get("session_type"),
                        "country_name": s.get("country_name"), "driver_number": dn,
                        "rows": n, "file_path": str(out_path.relative_to(output_dir)),
                        "status": "skipped_existing"
                    })
                    continue

                data, meta, params, mode_used = fetch_endpoint_driver(client, endpoint, sk, dn, fetch_mode)
                if data is None:
                    rows.append({
                        "endpoint": endpoint, "meeting_key": s.get("meeting_key"), "session_key": sk,
                        "session_name": s.get("session_name"), "session_type": s.get("session_type"),
                        "country_name": s.get("country_name"), "driver_number": dn,
                        "rows": 0, "file_path": "", "status": f"failed: {meta}", "status_code": meta.get("status_code", "")
                    })
                    continue

                df = pd.DataFrame(data or [])
                if not df.empty:
                    write_frame(df, out_path)
                    file_path = str(out_path.relative_to(output_dir))
                else:
                    file_path = ""

                rows.append({
                    "endpoint": endpoint, "meeting_key": s.get("meeting_key"), "session_key": sk,
                    "session_name": s.get("session_name"), "session_type": s.get("session_type"),
                    "country_name": s.get("country_name"), "driver_number": dn,
                    "rows": len(df), "file_path": file_path,
                    "status": meta.get("note", "ok"), "status_code": meta.get("status_code", "")
                })

                pd.DataFrame(rows).to_csv(manifest_dir / "high_frequency_extraction_manifest.csv", index=False)

    manifest = pd.DataFrame(rows)
    manifest.to_csv(manifest_dir / "high_frequency_extraction_manifest.csv", index=False)
    return session_drivers, manifest


def load_chunks(output_dir, endpoint, session_key, driver_number):
    folder = output_dir / "raw" / endpoint / f"session_key={int(session_key)}" / f"driver_number={int(driver_number)}"
    files = sorted(folder.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    parts = []
    for fp in files:
        df = pd.read_parquet(fp)
        if not df.empty:
            parts.append(df)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], utc=True, errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date")
    return out.reset_index(drop=True)


def build_driver_features(output_dir, session_key, driver_number, tolerance_ms=750):
    car = load_chunks(output_dir, "car_data", session_key, driver_number)
    loc = load_chunks(output_dir, "location", session_key, driver_number)
    if car.empty or "date" not in car.columns:
        return pd.DataFrame()

    for col in ["rpm", "speed", "n_gear", "throttle", "brake"]:
        if col in car.columns:
            car[col] = pd.to_numeric(car[col], errors="coerce")

    if not loc.empty and "date" in loc.columns:
        for col in ["x", "y", "z"]:
            if col in loc.columns:
                loc[col] = pd.to_numeric(loc[col], errors="coerce")
        merged = pd.merge_asof(
            car.sort_values("date"),
            loc[["date", "x", "y", "z"]].rename(columns={"date": "date_location"}).sort_values("date_location"),
            left_on="date",
            right_on="date_location",
            direction="nearest",
            tolerance=pd.Timedelta(milliseconds=tolerance_ms)
        )
    else:
        merged = car.copy()
        merged["date_location"] = pd.NaT
        merged["x"] = pd.NA
        merged["y"] = pd.NA
        merged["z"] = pd.NA

    merged["rpm_safe"] = merged["rpm"].replace(0, pd.NA)
    merged["efficiency_ratio_speed_per_rpm"] = merged["speed"] / merged["rpm_safe"]
    baseline = (
        merged.dropna(subset=["efficiency_ratio_speed_per_rpm", "n_gear"])
        .groupby("n_gear")["efficiency_ratio_speed_per_rpm"].median().to_dict()
    )
    merged["efficiency_ratio_norm"] = merged["efficiency_ratio_speed_per_rpm"] / merged["n_gear"].map(baseline)

    merged["speed_delta"] = merged["speed"].diff()
    merged["throttle_speed_mismatch"] = (
        (merged["throttle"] >= 95) & (merged["rpm"] >= 9000) &
        (merged["brake"].fillna(0) < 1) & (merged["speed_delta"].fillna(0) < 0.5)
    )

    merged["prev_gear"] = merged["n_gear"].shift(1)
    merged["prev_rpm"] = merged["rpm"].shift(1)
    merged["upshift_event"] = merged["n_gear"] > merged["prev_gear"]
    upshift_rpms = merged.loc[merged["upshift_event"], "prev_rpm"].dropna()
    threshold = upshift_rpms.quantile(0.20) if len(upshift_rpms) >= 8 else 9200
    merged["upshift_rpm"] = merged["prev_rpm"].where(merged["upshift_event"])
    merged["short_shift_flag"] = merged["upshift_event"] & (merged["upshift_rpm"] < threshold) & (merged["throttle"] >= 85)

    merged["efficiency_loss_flag"] = (
        (merged["efficiency_ratio_norm"] < 0.965) &
        (merged["throttle"] >= 85) & (merged["brake"].fillna(0) < 1)
    )

    rpm_max = max(1, merged["rpm"].max(skipna=True))
    merged["load_proxy"] = (merged["throttle"].fillna(0) / 100.0) * (merged["rpm"].fillna(0) / rpm_max)
    merged["low_efficiency_proxy"] = (1 - merged["efficiency_ratio_norm"].clip(lower=0.0, upper=1.2)).clip(lower=0.0)
    merged["thermal_stress_proxy"] = (merged["load_proxy"] * 0.7 + merged["low_efficiency_proxy"] * 0.3).fillna(0)

    merged["reliability_proxy_score"] = (
        merged["throttle_speed_mismatch"].astype(int) * 0.35 +
        merged["short_shift_flag"].astype(int) * 0.20 +
        merged["efficiency_loss_flag"].astype(int) * 0.25 +
        merged["thermal_stress_proxy"].clip(0, 1) * 0.20
    ).clip(0, 1)

    merged["bucket_start"] = merged["date"].dt.floor("30s")
    grouped = merged.groupby(["session_key", "driver_number", "bucket_start"], dropna=False)
    out = grouped.agg(
        samples=("date", "count"),
        reliability_proxy_mean=("reliability_proxy_score", "mean"),
        reliability_proxy_max=("reliability_proxy_score", "max"),
        efficiency_ratio_norm_mean=("efficiency_ratio_norm", "mean"),
        efficiency_ratio_norm_min=("efficiency_ratio_norm", "min"),
        throttle_speed_mismatch_count=("throttle_speed_mismatch", "sum"),
        short_shift_count=("short_shift_flag", "sum"),
        efficiency_loss_count=("efficiency_loss_flag", "sum"),
        thermal_stress_mean=("thermal_stress_proxy", "mean"),
        thermal_stress_max=("thermal_stress_proxy", "max"),
    ).reset_index()
    return out


def build_feature_mart(output_dir, sessions, session_drivers):
    feature_dir = output_dir / "features"
    manifest_dir = output_dir / "manifests"
    feature_dir.mkdir(exist_ok=True)
    rows = []
    manifest = []

    for _, s in tqdm(sessions.iterrows(), total=len(sessions), desc="features"):
        sk = int(s["session_key"])
        for dn in session_drivers.get(sk, []):
            try:
                comp = build_driver_features(output_dir, sk, dn)
                if not comp.empty:
                    comp["meeting_key"] = s.get("meeting_key")
                    comp["session_name"] = s.get("session_name")
                    comp["session_type"] = s.get("session_type")
                    comp["country_name"] = s.get("country_name")
                    rows.append(comp)
                manifest.append({"session_key": sk, "driver_number": dn, "rows_30s": len(comp), "status": "ok"})
            except Exception as e:
                manifest.append({"session_key": sk, "driver_number": dn, "rows_30s": 0, "status": f"error: {e}"})

    pd.DataFrame(manifest).to_csv(manifest_dir / "feature_manifest.csv", index=False)
    if not rows:
        return pd.DataFrame()

    fm = pd.concat(rows, ignore_index=True)
    fm.to_parquet(feature_dir / "openf1_high_frequency_reliability_features_30s.parquet", index=False)
    return fm


def compute_driver_session_risk(fm):
    if fm.empty:
        return pd.DataFrame()
    f = fm.copy()
    for col in [
        "reliability_proxy_max",
        "efficiency_loss_count",
        "short_shift_count",
        "thermal_stress_mean",
        "throttle_speed_mismatch_count",
    ]:
        f[col] = pd.to_numeric(f[col], errors="coerce").fillna(0)
        f[col + "_pct"] = f.groupby(["meeting_key", "session_key"])[col].rank(pct=True).fillna(0)

    f["risk_score"] = (
        0.30 * f["reliability_proxy_max_pct"] +
        0.20 * f["efficiency_loss_count_pct"] +
        0.15 * f["short_shift_count_pct"] +
        0.25 * f["thermal_stress_mean_pct"] +
        0.10 * f["throttle_speed_mismatch_count_pct"]
    )

    idx = f.groupby(["meeting_key", "session_key", "driver_number"])["risk_score"].idxmax()
    ds = f.loc[idx, [
        "meeting_key", "session_key", "session_name", "session_type", "country_name",
        "driver_number", "bucket_start", "risk_score"
    ]].copy()
    ds = ds.rename(columns={"bucket_start": "max_risk_time", "risk_score": "driver_session_risk"})
    return ds


def fetch_race_ground_truth(client, year):
    sessions = discover_sessions(client, year, "race")
    rows = []
    for _, s in tqdm(sessions.iterrows(), total=len(sessions), desc="race truth"):
        sk = int(s["session_key"])
        data, meta = client.get("session_result", {"session_key": sk})
        df = pd.DataFrame(data or [])
        if df.empty:
            continue
        df["session_key"] = sk
        df["meeting_key"] = s.get("meeting_key")
        df["session_name"] = s.get("session_name")
        df["session_type"] = s.get("session_type")
        df["country_name"] = s.get("country_name")
        rows.append(df)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_metrics(output_dir, mode, fm, client, year):
    metrics_dir = output_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)
    ds = compute_driver_session_risk(fm)
    ds.to_csv(metrics_dir / "driver_session_risk_scores.csv", index=False)

    if mode not in ["prerace", "all"]:
        return

    race_gt = fetch_race_ground_truth(client, year)
    race_gt.to_csv(output_dir / "manifests" / "race_session_result_ground_truth.csv", index=False)
    if race_gt.empty or ds.empty:
        return

    # Recommended mode from prior work: top-3 risk handoff per pre-race session.
    ds["rank_in_session"] = ds.groupby(["meeting_key", "session_key"])["driver_session_risk"].rank(method="first", ascending=False)
    top3 = ds[ds["rank_in_session"] <= 3].sort_values(["meeting_key", "driver_number", "max_risk_time"])
    first_warn = top3.groupby(["meeting_key", "driver_number"], as_index=False).first()

    race_gt["driver_number"] = pd.to_numeric(race_gt["driver_number"], errors="coerce").astype("Int64")
    race_gt["dnf"] = race_gt["dnf"].fillna(False).astype(bool)
    dnf = race_gt[race_gt["dnf"]].copy()

    dnf_summary = dnf.merge(first_warn, on=["meeting_key", "driver_number"], how="left", suffixes=("_race", "_first_warning"))
    dnf_summary["had_pre_race_warning"] = dnf_summary["max_risk_time"].notna()
    dnf_summary.to_csv(metrics_dir / "pre_race_first_warning_to_dnf_driver_summary.csv", index=False)

    all_race = race_gt.merge(first_warn[["meeting_key", "driver_number", "max_risk_time"]], on=["meeting_key", "driver_number"], how="left")
    all_race["had_pre_race_warning"] = all_race["max_risk_time"].notna()

    warned_dnf = int(dnf_summary["had_pre_race_warning"].sum())
    total_dnf = len(dnf_summary)
    warned_total = int(all_race["had_pre_race_warning"].sum())
    non_dnf = all_race[~all_race["dnf"]]
    warned_non = int(non_dnf["had_pre_race_warning"].sum())

    agg = pd.DataFrame([
        {
            "metric": "pre_race_warning_to_later_dnf_recall",
            "value": warned_dnf / total_dnf if total_dnf else np.nan,
            "numerator": warned_dnf,
            "denominator": total_dnf,
        },
        {
            "metric": "pre_race_warning_precision_for_dnf",
            "value": warned_dnf / warned_total if warned_total else np.nan,
            "numerator": warned_dnf,
            "denominator": warned_total,
        },
        {
            "metric": "pre_race_warning_false_positive_rate_non_dnf",
            "value": warned_non / len(non_dnf) if len(non_dnf) else np.nan,
            "numerator": warned_non,
            "denominator": len(non_dnf),
        }
    ])
    agg.to_csv(metrics_dir / "pre_race_first_warning_to_dnf_aggregate.csv", index=False)

    phase = (
        dnf_summary[dnf_summary["had_pre_race_warning"]]
        .groupby("session_type_first_warning")
        .size()
        .reset_index(name="dnf_count_first_warned_in_phase")
        if "session_type_first_warning" in dnf_summary.columns else pd.DataFrame()
    )
    if not phase.empty:
        phase.to_csv(metrics_dir / "pre_race_first_warning_phase_breakdown.csv", index=False)


def write_report(output_dir, year, mode):
    manifest_path = output_dir / "manifests" / "high_frequency_extraction_manifest.csv"
    feature_manifest_path = output_dir / "manifests" / "feature_manifest.csv"
    metrics_path = output_dir / "metrics" / "pre_race_first_warning_to_dnf_aggregate.csv"

    report_dir = output_dir / "reports"
    report_dir.mkdir(exist_ok=True)

    lines = [f"# OpenF1 High-Frequency Auto Ingest Report", "", f"Year: {year}", f"Mode: {mode}", ""]
    if manifest_path.exists():
        m = pd.read_csv(manifest_path)
        lines += ["## Extraction", "", f"- Files/driver-endpoint rows: {len(m)}", f"- Total extracted rows: {int(pd.to_numeric(m['rows'], errors='coerce').fillna(0).sum())}", ""]
    if feature_manifest_path.exists():
        fm = pd.read_csv(feature_manifest_path)
        lines += ["## Features", "", f"- Driver-session feature rows: {len(fm)}", f"- 30s rows: {int(pd.to_numeric(fm['rows_30s'], errors='coerce').fillna(0).sum())}", ""]
    if metrics_path.exists():
        met = pd.read_csv(metrics_path)
        lines += ["## Pre-race warning metric", "", met.to_markdown(index=False), ""]

    lines += [
        "## Authority",
        "",
        "- Risk/fantasy/reporting only.",
        "- No automatic qualifying P1-P5 reorder.",
        "- No automatic stable race P1-P20 reorder.",
        "- Bahrain/Saudi 2026 are treated as expected-zero cancelled events.",
        ""
    ]

    (report_dir / "openf1_high_frequency_auto_ingest_report.md").write_text("\n".join(lines), encoding="utf-8")


# Opt-in experimental capture. Legacy discovery/feature interfaces above remain
# unchanged. Input hashes must come from separately reviewed retained evidence;
# this boundary verifies bytes/identity, not independent publisher attestation.
TARGET_SCHEMA = "openf1-targeted-high-frequency-v1"
TARGET_ENDPOINTS = ("car_data", "location")
TARGET_TRUST = {
    "source_readiness_promoted": False,
    "prospective_forecast_eligibility_established": False,
    "independent_publisher_authentication_established": False,
    "dr002_activated": False,
    "stable_engine_modified": False,
}
TARGET_MAX_FILE_BYTES = 32 * 1024 * 1024
TARGET_MAX_TOTAL_BYTES = 512 * 1024 * 1024
TARGET_MAX_INPUT_BYTES = 8 * 1024 * 1024


class TargetHold(ValueError):
    """Deterministic experimental HOLD, never a production readiness verdict."""


def target_require(condition, reason):
    if not condition:
        raise TargetHold(reason)


def target_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def target_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            target_require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def constant(_):
        raise TargetHold("nonfinite_json")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, TargetHold):
            raise
        raise TargetHold("invalid_json") from exc


def target_time(value):
    target_require(type(value) is str, "invalid_utc_time")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TargetHold("invalid_utc_time") from exc
    target_require(result.tzinfo is not None and result.utcoffset() == timedelta(0),
                   "invalid_utc_time")
    return result


def target_integer(value):
    target_require(type(value) is int and value > 0, "invalid_integer_identity")
    return value


def target_read(path, limit):
    path = Path(path).absolute()
    target_require(not any(p.is_symlink() for p in (path, *path.parents)), "unsafe_input_path")
    target_require(path.is_file() and 0 < path.stat().st_size <= limit, "input_size_or_missing")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    target_require(0 < len(raw) <= limit, "input_size_or_missing")
    return raw


def target_pinned(path, sha):
    target_require(type(sha) is str and re.fullmatch(r"[0-9a-f]{64}", sha), "input_pin_missing")
    raw = target_read(path, TARGET_MAX_INPUT_BYTES)
    target_require(target_sha(raw) == sha, "input_hash_mismatch")
    return target_json(raw)


def target_historical_after(session):
    # A scheduled end alone cannot prove completion (red flags/delays). The
    # separately pinned metadata must explicitly attest an observed completion.
    target_require(session.get("completion_confirmed") is True, "session_completion_unverified")
    completed = target_time(session.get("completion_observed_at_utc"))
    target_require(completed >= target_time(session["date_end"]), "completion_chronology_invalid")
    return completed + timedelta(minutes=30)


def load_target_plan(spec_path, metadata_path, metadata_sha256, roster_path, roster_sha256, *, now):
    """Cross-check explicit targets with independently pinned offline snapshots.

    Spec: year, meeting_key, targets [{session_key, driver_numbers}]. Metadata:
    observed_at_utc, sessions [OpenF1 identity/date fields plus explicit
    completion_confirmed and completion_observed_at_utc]. Roster:
    observed_at_utc, drivers [{meeting_key, session_key, driver_number}]. A stale
    pre-session snapshot cannot establish a completed-session roster. No live
    window bypass is provided, including when a token exists in the environment.
    """
    observed_now = target_time(now)
    spec_raw = target_read(spec_path, TARGET_MAX_INPUT_BYTES)
    spec = target_json(spec_raw)
    metadata = target_pinned(metadata_path, metadata_sha256)
    roster = target_pinned(roster_path, roster_sha256)
    target_require(all(type(item) is dict for item in (spec, metadata, roster)), "input_schema")
    year = target_integer(spec.get("year"))
    meeting = target_integer(spec.get("meeting_key"))
    targets = spec.get("targets")
    target_require(type(targets) is list and 0 < len(targets) <= 10, "target_sessions_invalid")
    sessions = metadata.get("sessions")
    drivers = roster.get("drivers")
    target_require(type(sessions) is list and type(drivers) is list, "metadata_schema")
    meta_time = target_time(metadata.get("observed_at_utc"))
    roster_time = target_time(roster.get("observed_at_utc"))
    target_require(max(meta_time, roster_time) <= observed_now, "future_metadata_observation")
    selected = []
    seen = set()
    for target in targets:
        target_require(type(target) is dict, "target_sessions_invalid")
        sk = target_integer(target.get("session_key"))
        target_require(sk not in seen, "duplicate_target_session")
        seen.add(sk)
        matches = [s for s in sessions if type(s) is dict and s.get("session_key") == sk]
        target_require(len(matches) == 1, "session_metadata_missing_or_duplicate")
        session = matches[0]
        target_require(target_integer(session.get("session_key")) == sk and
                       target_integer(session.get("meeting_key")) == meeting and
                       target_integer(session.get("year")) == year, "session_identity_mismatch")
        for field in ("country_name", "location", "circuit_short_name", "session_name", "session_type"):
            value = session.get(field)
            target_require(type(value) is str and bool(value.strip()) and value.strip() == value,
                           "session_text_identity_missing")
        target_require(session["session_type"] in SESSION_TYPES["all"], "session_type_invalid")
        start, end = target_time(session.get("date_start")), target_time(session.get("date_end"))
        target_require(start.year == year and start < end, "session_chronology_invalid")
        eligible_after = target_historical_after(session)
        target_require(eligible_after < observed_now, "session_incomplete_or_live_window")
        target_require(eligible_after - timedelta(minutes=30) <= min(meta_time, roster_time),
                       "stale_precompletion_metadata")
        target_require(session.get("is_cancelled", False) is False, "cancelled_session")
        numbers = target.get("driver_numbers")
        target_require(type(numbers) is list and 0 < len(numbers) <= 30, "target_roster_invalid")
        numbers = [target_integer(n) for n in numbers]
        target_require(len(numbers) == len(set(numbers)), "duplicate_target_driver")
        roster_rows = [r for r in drivers if type(r) is dict and r.get("session_key") == sk]
        roster_numbers = []
        for row in roster_rows:
            target_require(target_integer(row.get("session_key")) == sk and
                           target_integer(row.get("meeting_key")) == meeting, "roster_identity_mismatch")
            roster_numbers.append(target_integer(row.get("driver_number")))
        target_require(len(roster_numbers) == len(set(roster_numbers)), "duplicate_roster_evidence")
        target_require(set(numbers) == set(roster_numbers), "roster_coverage_mismatch")
        selected.append({"session": session, "driver_numbers": sorted(numbers)})
    return {"year": year, "meeting_key": meeting, "targets": selected,
            "spec_sha256": target_sha(spec_raw), "metadata_sha256": metadata_sha256,
            "roster_sha256": roster_sha256,
            "metadata_observed_at_utc": metadata["observed_at_utc"],
            "roster_observed_at_utc": roster["observed_at_utc"]}


def target_expected(plan):
    target_require(type(plan) is dict and type(plan.get("targets")) is list and bool(plan["targets"]),
                   "target_sessions_invalid")
    return [(item["session"], dn, endpoint) for item in plan["targets"]
            for endpoint in TARGET_ENDPOINTS for dn in item["driver_numbers"]]


def validate_target_rows(raw, session, driver_number, endpoint):
    rows = target_json(raw)
    target_require(type(rows) is list and bool(rows), "empty_or_invalid_endpoint")
    fields = ("rpm", "speed", "n_gear", "throttle", "brake") if endpoint == "car_data" else ("x", "y", "z")
    start, end = target_time(session["date_start"]), target_time(session["date_end"])
    seen = set()
    for row in rows:
        target_require(type(row) is dict, "row_schema")
        target_require(all(type(row.get(k)) is int and row[k] == value for k, value in (
            ("session_key", session["session_key"]), ("meeting_key", session["meeting_key"]),
            ("driver_number", driver_number))), "row_identity_mismatch")
        stamp = target_time(row.get("date"))
        target_require(start <= stamp <= end, "row_time_outside_session")
        target_require(stamp not in seen, "duplicate_sample_time")
        seen.add(stamp)
        target_require(all(type(row.get(k)) in (int, float) and -1e100 < row[k] < 1e100 for k in fields),
                       "endpoint_measurement_invalid")
    # Complete response and every matrix cell are verified. Provider sampling
    # density/completeness is UNKNOWN: a small nonempty response is not proof of
    # all telemetry the provider ever observed.
    return rows


def target_budget(**kwargs):
    # Reuse the collector's single budget for all requests in this process.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.openf1.publish_openf1_lightweight_source_closure import NormalRequestBudget
    return NormalRequestBudget(**kwargs)


class TargetClient:
    """Bounded no-retry transport using the existing driver/session extraction API."""
    def __init__(self, *, budget, http_get, utc_clock, max_file_bytes, max_total_bytes):
        self.budget, self.http_get, self.utc_clock = budget, http_get, utc_clock
        self.max_file_bytes, self.max_total_bytes = max_file_bytes, max_total_bytes
        self.transferred = 0
        self.requests_sent = 0
        self.last_raw = b""
        self.last_meta = {}

    def get(self, endpoint, params=None, timeout=120):
        self.last_raw = b""
        self.last_meta = {"attempted": False}
        target_require(endpoint in TARGET_ENDPOINTS and set(params) == {"session_key", "driver_number"},
                       "target_request_scope_invalid")
        remaining = self.max_total_bytes - self.transferred
        target_require(remaining > 0, "total_transfer_budget_exhausted")
        try:
            self.budget.acquire()
        except RuntimeError as exc:
            raise TargetHold(str(exc)) from exc
        cap = min(self.max_file_bytes, remaining)
        self.last_meta = {"attempted": False, "request_started_at_utc": self.utc_clock(),
                          "url": f"{BASE_URL}/{endpoint}", "params": dict(params)}
        response = None
        try:
            remaining_time = self.budget.max_elapsed_seconds - (self.budget.clock() - self.budget.started)
            target_require(remaining_time > 0, "run_time_budget_exhausted")
            self.last_meta["attempted"] = True
            self.requests_sent += 1
            response = self.http_get(self.last_meta["url"], params=params, stream=True,
                                     allow_redirects=False, headers={"Accept-Encoding": "identity"},
                                     timeout=min(timeout, remaining_time))
            code = response.status_code
            self.last_meta["status_code"] = code
            target_require(type(code) is int and code == 200, f"provider_http_{code}")
            target_require(response.url == self.last_meta["url"] + "?" + urlencode(params),
                           "response_url_mismatch")
            target_require(response.headers.get("Content-Encoding", "identity").lower() == "identity",
                           "encoded_response_rejected")
            length = response.headers.get("Content-Length")
            if length is not None:
                target_require(type(length) is str and length.isdecimal() and 0 < int(length) <= cap,
                               "response_length_invalid_or_excessive")
            chunks = []
            size = 0
            for chunk in response.iter_content(chunk_size=65536):
                target_require(type(chunk) is bytes, "response_chunk_invalid")
                size += len(chunk)
                self.transferred += len(chunk)
                target_require(size <= cap, "response_transfer_limit")
                target_require(self.budget.clock() - self.budget.started <= self.budget.max_elapsed_seconds,
                               "run_time_budget_exhausted")
                chunks.append(chunk)
            self.last_raw = b"".join(chunks)
            self.last_meta["observed_at_utc"] = self.utc_clock()
            target_require(length is None or size == int(length), "response_length_mismatch")
            target_require(size > 0, "empty_response")
            return target_json(self.last_raw), dict(self.last_meta)
        except TargetHold:
            raise
        except Exception as exc:
            raise TargetHold("transport_failure") from exc
        finally:
            if response is not None:
                response.close()


def target_output_path(path):
    path = Path(path).absolute()
    target_require(".." not in path.parts and "experimental" in path.parts and not any(
        p.lower() in {"latest", "history", "engine_2026-06-07_stable"} for p in path.parts),
        "unsafe_experimental_output")
    target_require(not any(p.is_symlink() for p in (path, *path.parents)), "unsafe_experimental_output")
    target_require(not path.exists(), "output_already_exists")
    return path


def capture_targeted(plan, output_dir, *, http_get=None, utc_clock=None, budget=None,
                     max_file_bytes=TARGET_MAX_FILE_BYTES, max_total_bytes=TARGET_MAX_TOTAL_BYTES,
                     cache_dir=None, cache_manifest_sha256=None):
    """Stage a distinct evidence packet; never publish or promote its contents.

    Cache reuse is deliberately whole-packet only and requires an externally
    pinned manifest plus independent matrix replay. Partial packets remain HOLD.
    """
    utc_clock = utc_clock or (lambda: datetime.now(timezone.utc).isoformat())
    budget = budget or target_budget()
    result = {"schema_version": TARGET_SCHEMA, "status": "HOLD", "hold": True,
              "reason": None, **TARGET_TRUST, "plan": plan, "entries": [],
              "provider_sampling_completeness_established": False}
    output = None
    created = False
    client = None
    try:
        target_require(type(max_file_bytes) is int and 0 < max_file_bytes <= TARGET_MAX_FILE_BYTES and
                       type(max_total_bytes) is int and 0 < max_total_bytes <= TARGET_MAX_TOTAL_BYTES,
                       "invalid_transfer_limits")
        output = target_output_path(output_dir)
        now = target_time(utc_clock())
        target_require(max(target_time(plan["metadata_observed_at_utc"]),
                           target_time(plan["roster_observed_at_utc"])) < now, "metadata_observation_invalid")
        expected = target_expected(plan)
        for session, _, _ in expected:
            target_require(target_historical_after(session) < now,
                           "session_incomplete_or_live_window")
        cached = None
        if cache_dir is not None:
            target_require(type(cache_manifest_sha256) is str, "cache_pin_missing")
            raw = target_read(Path(cache_dir) / "targeted_manifest.json", TARGET_MAX_INPUT_BYTES)
            target_require(target_sha(raw) == cache_manifest_sha256, "cache_manifest_hash_mismatch")
            cached = verify_targeted_packet(cache_dir, plan, now=utc_clock())
            target_require(cached["status"] == "PASS", "cache_coverage_or_provenance_invalid")
            target_require(sum(e["size_bytes"] for e in cached["entries"]) <= max_total_bytes and
                           all(e["size_bytes"] <= max_file_bytes for e in cached["entries"]),
                           "cache_transfer_limit")
        # Create only after all preflight and cache checks; never reuse an
        # existing destination, including a previous interrupted capture.
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(exist_ok=False)
        created = True
        client = TargetClient(budget=budget, http_get=http_get or requests.get, utc_clock=utc_clock,
                              max_file_bytes=max_file_bytes, max_total_bytes=max_total_bytes)
        stop = None
        for index, (session, dn, endpoint) in enumerate(expected):
            sk = session["session_key"]
            relative = f"raw/{endpoint}/session_key={sk}/driver_number={dn}/response.json"
            entry = {"session_key": sk, "meeting_key": session["meeting_key"],
                     "driver_number": dn, "endpoint": endpoint, "status": "deferred",
                     "attempted": False, "reason": stop}
            result["entries"].append(entry)
            if stop:
                continue
            try:
                if cached is not None:
                    original = cached["entries"][index]
                    raw = target_read(Path(cache_dir) / relative, max_file_bytes)
                    target_require(target_sha(raw) == original["sha256"], "cache_changed_during_copy")
                    entry.update(original)
                    entry.update(attempted=False, reused_from_manifest_sha256=cache_manifest_sha256)
                else:
                    _, meta, _, _ = fetch_endpoint_driver(client, endpoint, sk, dn, "driver_full_session")
                    raw = client.last_raw
                    entry.update(meta)
                rows = validate_target_rows(raw, session, dn, endpoint)
                observed = target_time(entry["observed_at_utc"])
                started = target_time(entry["request_started_at_utc"])
                target_require(max(target_time(plan["metadata_observed_at_utc"]),
                                   target_time(plan["roster_observed_at_utc"]),
                                   target_historical_after(session)) < started <= observed <= target_time(utc_clock()),
                               "capture_observation_invalid")
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as handle:
                    handle.write(raw)
                entry.update(status="complete", reason=None, file_path=relative, rows=len(rows),
                             sha256=target_sha(raw), size_bytes=len(raw))
            except (TargetHold, OSError) as exc:
                stop = str(exc) if isinstance(exc, TargetHold) else "output_io_failure"
                if cached is None:
                    entry.update(client.last_meta)
                budget.block(stop)
                entry.update(status="hold", reason=stop)
                # Retain bounded malformed/identity-mixed response evidence in
                # quarantine; it is not a complete raw matrix cell.
                if cached is None and client.last_raw:
                    evidence = f"rejected_response_{index}.bin"
                    (output / evidence).write_bytes(client.last_raw)
                    entry.update(rejected_path=evidence, rejected_sha256=target_sha(client.last_raw))
        result.update(status="HOLD" if stop else "PASS", hold=bool(stop), reason=stop)
    except (TargetHold, OSError, KeyError, TypeError, ValueError) as exc:
        result["reason"] = str(exc) if isinstance(exc, TargetHold) else "target_input_or_io_invalid"
    result["generated_at_utc"] = utc_clock()
    result["request_budget"] = budget.evidence()
    result["request_budget"]["request_permits_acquired"] = budget.total_requests
    result["request_budget"]["provider_requests_performed"] = client.requests_sent if client else 0
    result["transferred_bytes"] = client.transferred if client else 0
    if created:
        with (output / "targeted_manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
    return result


def verify_targeted_packet(root, plan, *, now):
    """Re-enumerate expected cells from independent inputs, not manifest totals."""
    failure = {"status": "HOLD", "hold": True, **TARGET_TRUST}
    try:
        root = Path(root)
        manifest = target_json(target_read(root / "targeted_manifest.json", TARGET_MAX_INPUT_BYTES))
        target_require(type(manifest) is dict and manifest.get("schema_version") == TARGET_SCHEMA,
                       "packet_schema_invalid")
        target_require(manifest.get("plan") == plan, "packet_target_identity_mismatch")
        target_require(all(manifest.get(k) is False for k in TARGET_TRUST) and
                       manifest.get("provider_sampling_completeness_established") is False,
                       "packet_trust_ceiling_invalid")
        target_require(manifest.get("status") == "PASS" and manifest.get("hold") is False and
                       manifest.get("reason") is None, "packet_held")
        generated = target_time(manifest.get("generated_at_utc"))
        target_require(generated <= target_time(now), "packet_future_observation")
        expected = target_expected(plan)
        entries = manifest.get("entries")
        target_require(type(entries) is list and len(entries) == len(expected), "matrix_coverage_incomplete")
        total = 0
        for entry, (session, dn, endpoint) in zip(entries, expected):
            target_require(type(entry) is dict and entry.get("status") == "complete" and entry.get("reason") is None,
                           "matrix_cell_incomplete")
            target_require(entry.get("attempted") is True or
                           (entry.get("attempted") is False and
                            type(entry.get("reused_from_manifest_sha256")) is str and
                            re.fullmatch(r"[0-9a-f]{64}", entry["reused_from_manifest_sha256"])),
                           "packet_request_provenance_invalid")
            sk = session["session_key"]
            target_require(all(type(entry.get(k)) is int and entry[k] == value for k, value in (
                ("session_key", sk), ("meeting_key", session["meeting_key"]), ("driver_number", dn))) and
                entry.get("endpoint") == endpoint, "matrix_cell_identity_mismatch")
            relative = f"raw/{endpoint}/session_key={sk}/driver_number={dn}/response.json"
            target_require(entry.get("file_path") == relative, "packet_path_mismatch")
            raw = target_read(root / relative, TARGET_MAX_FILE_BYTES)
            total += len(raw)
            target_require(total <= TARGET_MAX_TOTAL_BYTES, "packet_transfer_limit")
            target_require(type(entry.get("size_bytes")) is int and entry["size_bytes"] == len(raw) and
                           entry.get("sha256") == target_sha(raw), "packet_bytes_mismatch")
            rows = validate_target_rows(raw, session, dn, endpoint)
            target_require(type(entry.get("rows")) is int and entry["rows"] == len(rows), "packet_row_count_mismatch")
            observed = target_time(entry.get("observed_at_utc"))
            started = target_time(entry.get("request_started_at_utc"))
            target_require(max(target_time(plan["metadata_observed_at_utc"]),
                               target_time(plan["roster_observed_at_utc"]),
                               target_historical_after(session)) < started <= observed <= generated,
                           "packet_observation_chronology_invalid")
            target_require(entry.get("url") == f"{BASE_URL}/{endpoint}" and
                           entry.get("params") == {"session_key": sk, "driver_number": dn} and
                           type(entry.get("status_code")) is int and entry["status_code"] == 200,
                           "packet_request_provenance_invalid")
        return manifest
    except (TargetHold, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        failure["reason"] = str(exc) if isinstance(exc, TargetHold) else "packet_invalid"
        return failure


def add_target_arguments(parser):
    parser.add_argument("--target-spec", help="Opt-in offline-pinned event/session/roster specification")
    parser.add_argument("--target-metadata")
    parser.add_argument("--target-metadata-sha256")
    parser.add_argument("--target-roster")
    parser.add_argument("--target-roster-sha256")
    parser.add_argument("--target-cache-dir")
    parser.add_argument("--target-cache-manifest-sha256")


def run_target_cli(args):
    try:
        plan = load_target_plan(args.target_spec, args.target_metadata, args.target_metadata_sha256,
                                args.target_roster, args.target_roster_sha256,
                                now=datetime.now(timezone.utc).isoformat())
        result = capture_targeted(plan, args.output_dir, cache_dir=args.target_cache_dir,
                                  cache_manifest_sha256=args.target_cache_manifest_sha256)
    except (TargetHold, OSError, TypeError, ValueError) as exc:
        result = {"status": "HOLD", "hold": True, **TARGET_TRUST,
                  "reason": str(exc) if isinstance(exc, TargetHold) else "target_input_invalid"}
    print(json.dumps(result, indent=2))
    return 1 if result["hold"] else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--mode", choices=["race", "prerace", "all"], default="prerace")
    p.add_argument("--event-filter", default="")
    p.add_argument("--fetch-mode", choices=["driver_full_session", "chunked_then_fallback"], default="driver_full_session")
    p.add_argument("--output-dir", default="output/openf1_high_frequency")
    p.add_argument("--request-sleep", type=float, default=0.35)
    p.add_argument("--warning-threshold", type=float, default=0.80)
    p.add_argument("--strict-threshold", type=float, default=0.90)
    add_target_arguments(p)
    args = p.parse_args()
    if any(value is not None for key, value in vars(args).items() if key.startswith("target_")):
        return run_target_cli(args)

    output_dir = Path(args.output_dir)
    for sub in ["raw", "features", "metrics", "manifests", "reports"]:
        (output_dir / sub).mkdir(parents=True, exist_ok=True)

    token = os.environ.get("OPENF1_TOKEN", "").strip()
    client = OpenF1Client(token=token, sleep_seconds=args.request_sleep)

    sessions = discover_sessions(client, args.year, args.mode, event_filter=args.event_filter)
    sessions.to_csv(output_dir / "manifests" / "completed_sessions_selected.csv", index=False)

    session_drivers, manifest = extract_raw(client, sessions, output_dir, args.fetch_mode)
    fm = build_feature_mart(output_dir, sessions, session_drivers)
    build_metrics(output_dir, args.mode, fm, client, args.year)
    write_report(output_dir, args.year, args.mode)

    policy = {
        "year": args.year,
        "mode": args.mode,
        "event_filter": args.event_filter,
        "fetch_mode": args.fetch_mode,
        "stable_rank_change_allowed": False,
        "fantasy_and_reporting_use": True,
        "generated_utc": datetime.now(timezone.utc).isoformat()
    }
    (output_dir / "openf1_auto_ingest_run_policy.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")

    print(f"Done. Output: {output_dir}")


if __name__ == "__main__":
    sys.exit(main())
