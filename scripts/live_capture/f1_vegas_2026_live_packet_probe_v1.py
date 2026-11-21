#!/usr/bin/env python3
"""Bounded, non-publishing 2026 Las Vegas original live-timing packet custody.

This is an independent fallback while the normal periodic source collector
is validated. A schedule selects an observation window but NEVER proves a
provider session identity or prospective model authority.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from run_live_source_feed_capture import build_packet_index, record_live_timing

UTC = dt.timezone.utc
WINDOWS = (
    ("qualifying", 11416, dt.datetime(2026, 11, 21, 3, 52, tzinfo=UTC),
     dt.datetime(2026, 11, 21, 5, 15, tzinfo=UTC)),
    ("race", 11420, dt.datetime(2026, 11, 22, 3, 52, tzinfo=UTC),
     dt.datetime(2026, 11, 22, 6, 35, tzinfo=UTC)),
)
MEETING = 1300


def utc_now():
    return dt.datetime.now(UTC)


def observe_window(at):
    if at.tzinfo is None:
        raise ValueError("Observation requires timezone-aware UTC clock")
    instant = at.astimezone(UTC)
    for name, session, start, end in WINDOWS:
        if start <= instant < end:
            return {"session_label": name, "session_key": session, "meeting_key": MEETING,
                    "source_window_start_utc": start.isoformat(), "source_window_end_utc": end.isoformat()}
    return None


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def capture(out, *, at=None, duration_minutes=5, recorder=record_live_timing, indexer=build_packet_index):
    observed = at if at is not None else utc_now()
    window = observe_window(observed)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "schema": "f1-vegas-2026-authenticated-signalr-original-packet-probe-v1",
        "observed_start_utc": observed.astimezone(UTC).isoformat(),
        "intended_recording_minutes": duration_minutes,
        "source_method": "FastF1_3.9.2_authenticated_signalr_core",
        "session_identity_status": "SCHEDULE_CONTEXT_ONLY_NOT_PROVIDER_VERIFIED",
        "production_published": False,
        "source_complete": False,
        "forecast_eligible": False,
        "stable_engine_executed": False,
        "prediction_locked": False,
        "original_packet_sha256": None,
        "original_packet_bytes": 0,
        "packet_lines": 0,
        "result": "HOLD_NOT_IN_EXACT_2026_SESSION_WINDOW",
    }
    if window:
        meta.update(window)
        raw_path = out / "original_live_timing_packets.txt"
        index_path = out / "packet_index.csv"
        result = recorder(raw_path, duration_minutes)
        actual_bytes = raw_path.stat().st_size if raw_path.is_file() else 0
        try:
            packet = indexer(raw_path, index_path) if actual_bytes else {}
        except Exception:
            packet = {}
        meta.update({
            "observed_finished_utc": utc_now().isoformat(),
            "recording_status": result.get("recording_status"),
            "recording_started_utc": result.get("recording_started_utc"),
            "recording_finished_utc": result.get("recording_finished_utc"),
            "auth_credentials_configured": bool(result.get("auth_credentials_configured")),
            "error_category": result.get("error"),
            "original_packet_bytes": actual_bytes,
            "original_packet_sha256": sha256_file(raw_path) if actual_bytes else None,
            "packet_lines": int(packet.get("line_count", 0)),
            "topic_counts": packet.get("topic_counts", {}),
        })
        meta["result"] = (
            "LIVE_ORIGINAL_SIGNALR_PACKET_BYTES_CONTEXT_ONLY"
            if result.get("recording_status") == "completed" and actual_bytes > 0
            and meta["packet_lines"] > 0
            else "HOLD_LIVE_ORIGINAL_SIGNALR_PACKETS_UNVERIFIED"
        )
    (out / "custody_manifest.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="_runtime/f1_vegas_live_packet_probe")
    ap.add_argument("--duration-minutes", type=int, default=5)
    args = ap.parse_args(argv)
    if not 1 <= args.duration_minutes <= 6:
        ap.error("Live proof is bounded to 1–6 minutes")
    result = capture(args.output_dir, duration_minutes=args.duration_minutes)
    # Avoid displaying provider bytes, credentials, token, raw packet excerpts,
    # or unfiltered exception text. Only sanitized bounded metadata are shown.
    print(json.dumps({
        "result": result["result"],
        "session": result.get("session_label"),
        "meeting_key_context_only": result.get("meeting_key"),
        "session_key_context_only": result.get("session_key"),
        "original_packet_bytes": result["original_packet_bytes"],
        "original_packet_sha256": result["original_packet_sha256"],
        "packet_lines": result["packet_lines"],
        "recording_status": result.get("recording_status"),
    }, sort_keys=True))
    return 0 if result["result"] in (
        "LIVE_ORIGINAL_SIGNALR_PACKET_BYTES_CONTEXT_ONLY",
        "HOLD_NOT_IN_EXACT_2026_SESSION_WINDOW") else 2


if __name__ == "__main__":
    raise SystemExit(main())
