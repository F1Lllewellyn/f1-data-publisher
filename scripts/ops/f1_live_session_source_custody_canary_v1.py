#!/usr/bin/env python3
"""Read-only, single-run OpenF1 live session evidence canary.

Captures ORIGINAL returned bytes with actual observation clocks. Never writes
history/latest, never calls a model, and never asserts prospective eligibility.
A live snapshot is not a complete closed-session publication.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "https://api.openf1.org/v1/"
ENDPOINTS = ("sessions", "drivers", "laps", "weather", "race_control")
REQUIRED = ("sessions", "drivers", "laps")
MAX_BYTES = 4 * 1024 * 1024


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def retrieve(endpoint, session_key):
    url = URL + endpoint + "?" + urllib.parse.urlencode({"session_key": session_key})
    req = urllib.request.Request(url, headers={"User-Agent": "F1-Session-Custody-Canary/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=24) as resp:
            return url, int(resp.status), resp.read(MAX_BYTES + 1), ""
    except urllib.error.HTTPError as exc:
        return url, int(exc.code), exc.read(MAX_BYTES + 1), f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return url, 0, b"", f"{type(exc).__name__}: {str(exc)[:160]}"


def capture_session(meeting_key, session_key, output_dir, sleep_seconds=2.1):
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    original = {
        "schema": "f1-live-session-source-custody-canary-v1",
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "head_sha": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "meeting_key": meeting_key,
        "session_key": session_key,
        "started_utc": utcnow(),
        "requests": [],
        "forecast_eligible": False,
        "stable_engine_executed": False,
        "prediction_locked": False,
        "production_published": False,
        "claim": "Original provider bytes observed at recorded times only; not complete session or prospective prediction",
    }
    valid = {}
    for index, endpoint in enumerate(ENDPOINTS):
        requested_at = utcnow()
        url, code, raw, error = retrieve(endpoint, session_key)
        observed_after_read = utcnow()
        # Retain the original bytes, even for non-200/partial provider responses.
        filename = endpoint + "_response.bin"
        (out / filename).write_bytes(raw)
        oversized = len(raw) > MAX_BYTES
        row = {
            "endpoint": endpoint,
            "url": url,
            "http_status": code,
            "requested_at_utc": requested_at,
            "observed_at_utc": observed_after_read,
            "original_response_filename": filename,
            "original_response_bytes_retained": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "truncated": oversized,
            "error": error,
            "row_count": None,
            "identity_verified": False,
        }
        if code == 200 and not oversized:
            try:
                decoded = json.loads(raw)
                if not isinstance(decoded, list):
                    row["error"] = "HOLD_NON_LIST_PROVIDER_RESPONSE"
                elif not all(
                    isinstance(entry, dict)
                    and entry.get("session_key") == session_key
                    and (entry.get("meeting_key", meeting_key) == meeting_key)
                    for entry in decoded
                ):
                    row["error"] = "HOLD_SESSION_OR_MEETING_IDENTITY"
                else:
                    row["row_count"] = len(decoded)
                    row["identity_verified"] = True
                    valid[endpoint] = len(decoded)
            except (ValueError, UnicodeError):
                row["error"] = "HOLD_INVALID_PROVIDER_JSON"
        elif oversized:
            row["error"] = "HOLD_ORIGINAL_RESPONSE_EXCEEDS_CANARY_CAP"
        original["requests"].append(row)
        if index + 1 < len(ENDPOINTS) and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    original["finished_utc"] = utcnow()
    original["required_endpoints"] = list(REQUIRED)
    original["verified_row_counts"] = valid
    original["result"] = (
        "VERIFIED_LIVE_PROVIDER_SNAPSHOT_CONTEXT_ONLY"
        if all(valid.get(name, 0) > 0 for name in REQUIRED)
        else "HOLD_LIVE_SOURCE_SNAPSHOT_INCOMPLETE"
    )
    (out / "original_source_canary_manifest.json").write_text(
        json.dumps(original, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return original


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting-key", type=int, required=True)
    parser.add_argument("--session-key", type=int, required=True)
    parser.add_argument("--output-dir", default="_runtime/fp3_source_canary")
    args = parser.parse_args()
    if args.meeting_key <= 0 or args.session_key <= 0:
        parser.error("Positive exact meeting and session IDs required")
    result = capture_session(args.meeting_key, args.session_key, args.output_dir)
    print(json.dumps({
        "result": result["result"], "meeting_key": args.meeting_key,
        "session_key": args.session_key,
        "counts": result["verified_row_counts"],
        "requests": [{"endpoint": r["endpoint"], "http_status": r["http_status"],
                      "sha256": r["sha256"], "row_count": r["row_count"],
                      "error": r["error"]}
                     for r in result["requests"]]
    }, indent=2))
    return 0 if result["result"].startswith("VERIFIED_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
