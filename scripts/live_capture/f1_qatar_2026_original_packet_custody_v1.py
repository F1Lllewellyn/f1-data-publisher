#!/usr/bin/env python3
"""Qatar 2026 original SignalR packet custody: narrow, nonpublishing intake.

Source of schedule: official F1 Qatar 2026 full timetable (Qatar UTC+3).
https://www.formula1.com/en/latest/article/formula-1-qatar-airways-qatar-grand-prix-2026.3XJyoYSnpJEcuZovstTdcG

The observer's schedule is not provider session identity. A successful recorder
proves original bytes only, never FIA identity, complete capture, stable-engine
execution, a pre-race forecast or an immutable prediction lock.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

UTC = dt.timezone.utc
EVENT = "2026_qatar_grand_prix"
SCHEDULE_SOURCE = ("https://www.formula1.com/en/latest/article/"
                   "formula-1-qatar-airways-qatar-grand-prix-2026.3XJyoYSnpJEcuZovstTdcG")
# UTC windows cover prestart context and limited delayed arrivals. Never accept
# an original packet timestamp outside the associated 2026 session envelope.
WINDOWS = (
    ("fp1", "2026-11-27T13:20:00Z", "2026-11-27T14:55:00Z",
     "2026-11-27T13:30:00Z"),
    ("fp2", "2026-11-27T16:50:00Z", "2026-11-27T18:25:00Z",
     "2026-11-27T17:00:00Z"),
    ("fp3", "2026-11-28T14:20:00Z", "2026-11-28T15:55:00Z",
     "2026-11-28T14:30:00Z"),
    ("qualifying", "2026-11-28T17:50:00Z", "2026-11-28T19:25:00Z",
     "2026-11-28T18:00:00Z"),
    ("race", "2026-11-29T15:50:00Z", "2026-11-29T18:35:00Z",
     "2026-11-29T16:00:00Z"),
)


def timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("HOLD_UNVERIFIED_UTC_TIMESTAMP")
    parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None:
        raise ValueError("HOLD_UNVERIFIED_UTC_TIMESTAMP")
    return parsed


def utc_now():
    return dt.datetime.now(UTC)


def as_utc(value):
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        raise ValueError("HOLD_NAIVE_OBSERVER_CLOCK")
    return value.astimezone(UTC)


def active_window(at):
    observed = as_utc(at)
    for name, start, end, scheduled in WINDOWS:
        if timestamp(start) <= observed < timestamp(end):
            return {"session_label": name, "window_start_utc": start,
                    "window_end_utc": end, "scheduled_start_utc": scheduled}
    return None


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def capture(output, *, at=None, duration_minutes=5, recorder=None, indexer=None):
    at = as_utc(at if at is not None else utc_now())
    if type(duration_minutes) is not int or not 1 <= duration_minutes <= 10:
        raise ValueError("HOLD_UNBOUNDED_RECORDING_DURATION")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    window = active_window(at)
    manifest = {
        "schema": "qatar-2026-original-live-packet-custody-v1",
        "event_id_context_only": EVENT,
        "schedule_reference": SCHEDULE_SOURCE,
        "observer_at_utc": at.isoformat().replace("+00:00", "Z"),
        "session_identity_status": "SCHEDULE_CONTEXT_ONLY_NOT_PROVIDER_VERIFIED",
        "provider_meeting_key": None, "provider_session_key": None,
        "source_complete": False, "production_published": False,
        "forecast_eligible": False, "prediction_locked": False,
        "stable_engine_executed": False, "promotion_allowed": False,
        "original_packet_bytes": 0, "original_packet_sha256": None,
        "packet_lines": 0, "result": "HOLD_OUTSIDE_QATAR_2026_WINDOW",
        "reason_codes": ["NO_VERIFIED_ACTIVE_SESSION_WINDOW"],
    }
    if window is not None:
        manifest.update(window)
        if recorder is None or indexer is None:
            # Reuse the existing original authenticated recorder: no new feed
            # protocol, authentication stack or provider endpoint.
            from f1_vegas_2026_live_packet_probe_v1 import (
                record_live_timing, build_packet_index)
            recorder = recorder or record_live_timing
            indexer = indexer or build_packet_index
        raw = output / "original_live_timing_packets.txt"
        index_path = output / "packet_index.csv"
        result = recorder(raw, duration_minutes)
        size = raw.stat().st_size if raw.is_file() and not raw.is_symlink() else 0
        try:
            index = indexer(raw, index_path) if size else {}
        except (OSError, ValueError, UnicodeError, TypeError):
            index = {}
        start = result.get("recording_started_utc")
        end = result.get("recording_finished_utc")
        clocks_ok = False
        try:
            clocks_ok = (timestamp(window["window_start_utc"]) <= timestamp(start)
                         <= timestamp(end) <= timestamp(window["window_end_utc"]))
        except (ValueError, TypeError):
            pass
        lines = int(index.get("line_count", 0)) if isinstance(index, dict) else 0
        metadata = {
            "original_packet_bytes": size,
            "original_packet_sha256": sha256(raw) if size else None,
            "packet_lines": max(0, lines),
            "topic_counts": index.get("topic_counts", {}) if isinstance(index, dict) else {},
            "recording_status": result.get("recording_status"),
            "recording_started_utc": start, "recording_finished_utc": end,
            "auth_credentials_configured": result.get("auth_credentials_configured") is True,
            "error_category": result.get("error"),
            "recording_clock_valid": clocks_ok,
        }
        manifest.update(metadata)
        passed = (result.get("recording_status") == "completed"
                  and not result.get("error")
                  and manifest["auth_credentials_configured"]
                  and clocks_ok and size > 0 and lines > 0)
        manifest["result"] = ("CAPTURED_ORIGINAL_PACKETS_UNBOUND" if passed
                              else "HOLD_ORIGINAL_CAPTURE_UNVERIFIED")
        manifest["reason_codes"] = ([] if passed else ["RECORDING_ORIGINAL_CUSTODY_NOT_PROVEN"])
    path = output / "custody_manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--duration-minutes", type=int, default=5)
    args = parser.parse_args(argv)
    result = capture(args.output_dir, duration_minutes=args.duration_minutes)
    print(json.dumps({key: result.get(key) for key in (
        "result", "session_label", "original_packet_bytes", "packet_lines",
        "original_packet_sha256", "session_identity_status", "reason_codes",
    )}, sort_keys=True))
    return (0 if result["result"] in {
        "CAPTURED_ORIGINAL_PACKETS_UNBOUND", "HOLD_OUTSIDE_QATAR_2026_WINDOW"
    } else 2)


if __name__ == "__main__":
    raise SystemExit(main())
