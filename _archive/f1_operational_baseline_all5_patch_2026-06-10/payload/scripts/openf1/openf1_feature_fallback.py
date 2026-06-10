#!/usr/bin/env python3
"""
Robust OpenF1 post-race feature fallback builder.

Purpose:
- Repairs race-mode runs where extraction succeeds but the normal feature mart is empty.
- Builds conservative 30-second features from public/proxy car_data only.
- Location is treated as optional. No private/internal telemetry is used.

Guardrails:
- Output is risk/fantasy/reporting input only.
- No automatic stable P1-P20 or qualifying P1-P5 ranking changes.
- DNF_ALL broad precursor-search policy preserved.
"""

from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd


FEATURE_FILE = "openf1_high_frequency_reliability_features_30s.parquet"


def _load_driver_raw(output_dir: Path, endpoint: str, session_key: int, driver_number: int) -> pd.DataFrame:
    folder = output_dir / "raw" / endpoint / f"session_key={int(session_key)}" / f"driver_number={int(driver_number)}"
    files = sorted(folder.glob("*.parquet"))
    parts = []
    for fp in files:
        try:
            df = pd.read_parquet(fp)
            if not df.empty:
                parts.append(df)
        except Exception:
            continue

    if not parts:
        return pd.DataFrame()

    out = pd.concat(parts, ignore_index=True)
    if "date" not in out.columns:
        for candidate in ["timestamp", "time", "created_at"]:
            if candidate in out.columns:
                out["date"] = out[candidate]
                break

    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], utc=True, errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    return out


def _ensure_numeric(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default).astype("float64")


def build_driver_features_fallback(output_dir: Path, session_key: int, driver_number: int) -> tuple[pd.DataFrame, dict]:
    car = _load_driver_raw(output_dir, "car_data", session_key, driver_number)
    loc = _load_driver_raw(output_dir, "location", session_key, driver_number)

    diagnostic = {
        "session_key": int(session_key),
        "driver_number": int(driver_number),
        "car_rows": int(len(car)),
        "location_rows": int(len(loc)),
        "rows_30s": 0,
        "status": "not_started",
        "builder": "fallback_car_data_only_v1",
    }

    if car.empty or "date" not in car.columns:
        diagnostic["status"] = "no_car_date_rows"
        return pd.DataFrame(), diagnostic

    car = car.copy()
    car["session_key"] = int(session_key)
    car["driver_number"] = int(driver_number)

    car["rpm"] = _ensure_numeric(car, "rpm")
    car["speed"] = _ensure_numeric(car, "speed")
    car["n_gear"] = _ensure_numeric(car, "n_gear")
    car["throttle"] = _ensure_numeric(car, "throttle")
    car["brake"] = _ensure_numeric(car, "brake")

    # Defensive ordering and finite cleanup.
    car = car.sort_values("date").reset_index(drop=True)
    for col in ["rpm", "speed", "n_gear", "throttle", "brake"]:
        car[col] = car[col].replace([np.inf, -np.inf], np.nan).fillna(0)

    rpm_safe = car["rpm"].mask(car["rpm"] <= 0, np.nan)
    car["efficiency_ratio_speed_per_rpm"] = car["speed"] / rpm_safe

    baseline = (
        car.dropna(subset=["efficiency_ratio_speed_per_rpm", "n_gear"])
        .query("n_gear > 0")
        .groupby("n_gear")["efficiency_ratio_speed_per_rpm"]
        .median()
        .to_dict()
    )

    if baseline:
        car["efficiency_ratio_norm"] = car["efficiency_ratio_speed_per_rpm"] / car["n_gear"].map(baseline)
    else:
        car["efficiency_ratio_norm"] = np.nan

    car["speed_delta"] = car["speed"].diff().fillna(0)
    car["throttle_speed_mismatch"] = (
        (car["throttle"] >= 95)
        & (car["rpm"] >= 9000)
        & (car["brake"] < 1)
        & (car["speed_delta"] < 0.5)
    )

    car["prev_gear"] = car["n_gear"].shift(1)
    car["prev_rpm"] = car["rpm"].shift(1)
    car["upshift_event"] = car["n_gear"] > car["prev_gear"]
    upshift_rpms = car.loc[car["upshift_event"], "prev_rpm"].dropna()
    threshold = float(upshift_rpms.quantile(0.20)) if len(upshift_rpms) >= 8 else 9200.0
    car["short_shift_flag"] = car["upshift_event"] & (car["prev_rpm"] < threshold) & (car["throttle"] >= 85)

    car["efficiency_loss_flag"] = (
        (car["efficiency_ratio_norm"].fillna(1.0) < 0.965)
        & (car["throttle"] >= 85)
        & (car["brake"] < 1)
    )

    rpm_max = float(car["rpm"].max()) if len(car) else 1.0
    if not np.isfinite(rpm_max) or rpm_max <= 0:
        rpm_max = 1.0

    car["load_proxy"] = (car["throttle"].clip(0, 100) / 100.0) * (car["rpm"].clip(lower=0) / rpm_max)
    car["low_efficiency_proxy"] = (1.0 - car["efficiency_ratio_norm"].fillna(1.0).clip(0.0, 1.2)).clip(lower=0.0)
    car["thermal_stress_proxy"] = (0.70 * car["load_proxy"] + 0.30 * car["low_efficiency_proxy"]).fillna(0).clip(0, 1)

    car["reliability_proxy_score"] = (
        car["throttle_speed_mismatch"].astype(int) * 0.35
        + car["short_shift_flag"].astype(int) * 0.20
        + car["efficiency_loss_flag"].astype(int) * 0.25
        + car["thermal_stress_proxy"] * 0.20
    ).clip(0, 1)

    car["bucket_start"] = car["date"].dt.floor("30s")
    grouped = car.groupby(["session_key", "driver_number", "bucket_start"], dropna=False)

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

    out["fallback_feature_builder_used"] = True
    out["fallback_builder_reason"] = "normal_feature_mart_empty_in_race_mode"
    out["location_rows_available"] = int(len(loc))
    out["location_optional"] = True

    diagnostic["rows_30s"] = int(len(out))
    diagnostic["status"] = "ok" if len(out) else "empty_after_bucket"
    return out, diagnostic


def build_feature_mart_fallback(output_dir: Path, sessions: pd.DataFrame, session_drivers: dict) -> pd.DataFrame:
    output_dir = Path(output_dir)
    feature_dir = output_dir / "features"
    manifest_dir = output_dir / "manifests"
    feature_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    # Preserve the normal feature manifest for audit if it exists.
    normal_manifest = manifest_dir / "feature_manifest.csv"
    if normal_manifest.exists():
        preserved = manifest_dir / "feature_manifest_normal_pre_fallback.csv"
        if not preserved.exists():
            preserved.write_bytes(normal_manifest.read_bytes())

    rows = []
    diagnostics = []

    for _, s in sessions.iterrows():
        sk = int(s["session_key"])
        for dn in session_drivers.get(sk, []):
            comp, diag = build_driver_features_fallback(output_dir, sk, int(dn))
            diag.update({
                "meeting_key": s.get("meeting_key"),
                "session_name": s.get("session_name"),
                "session_type": s.get("session_type"),
                "country_name": s.get("country_name"),
            })
            diagnostics.append(diag)

            if not comp.empty:
                comp["meeting_key"] = s.get("meeting_key")
                comp["session_name"] = s.get("session_name")
                comp["session_type"] = s.get("session_type")
                comp["country_name"] = s.get("country_name")
                rows.append(comp)

    diag_df = pd.DataFrame(diagnostics)
    diag_df.to_csv(manifest_dir / "feature_manifest_fallback.csv", index=False)

    if not diag_df.empty:
        # Keep the standard manifest path populated so downstream validators/readers work.
        standard = diag_df[[
            "session_key", "driver_number", "rows_30s", "status"
        ]].copy()
        standard["status"] = "fallback_" + standard["status"].astype(str)
        standard.to_csv(manifest_dir / "feature_manifest.csv", index=False)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "fallback_builder": "fallback_car_data_only_v1",
        "driver_sessions_checked": int(len(diag_df)),
        "driver_sessions_with_features": int((diag_df.get("rows_30s", pd.Series(dtype=int)) > 0).sum()) if not diag_df.empty else 0,
        "total_feature_rows_30s": int(diag_df.get("rows_30s", pd.Series(dtype=int)).sum()) if not diag_df.empty else 0,
        "guardrails": {
            "public_proxy_only": True,
            "location_optional": True,
            "stable_race_rank_change_allowed": False,
            "qualifying_top5_rank_change_allowed": False,
        },
    }
    (manifest_dir / "postrace_feature_fallback_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if not rows:
        return pd.DataFrame()

    fm = pd.concat(rows, ignore_index=True)
    fm.to_parquet(feature_dir / FEATURE_FILE, index=False)
    return fm
