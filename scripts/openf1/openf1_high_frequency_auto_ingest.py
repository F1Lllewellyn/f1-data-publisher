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
    args = p.parse_args()

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
    main()
