#!/usr/bin/env python3
"""Check actual Qatar original source artifact after each official session.

GitHub job SUCCESS is never evidence that original live packets were recorded.
A missing scheduled run, missing artifact, zero-byte packet file, altered hash
or fake provenance causes an actionable watchdog failure. Never downloads FIA
documents or creates a forecast, and never needs user F1TV credentials.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile

from f1_qatar_2026_original_packet_custody_v1 import WINDOWS, timestamp, UTC

REPO = "F1Lllewellyn/f1-data-publisher"
WORKFLOW_PATH = ".github/workflows/f1-qatar-2026-original-packet-custody.yml"
BASE = "https://api.github.com/repos/" + REPO
MAX_ZIP = 48 * 1024 * 1024


class StripCrossHostToken(urllib.request.HTTPRedirectHandler):
    """GitHub artifact ZIPs redirect to signed object storage; never send GH_TOKEN there."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        target = urlsplit(newurl)
        if target.scheme != "https" or not target.hostname:
            raise ValueError("FAIL_GITHUB_UNSAFE_ARTIFACT_REDIRECT")
        if result is not None and urlsplit(req.full_url).hostname != target.hostname:
            result.remove_header("Authorization")
        return result


def get(url, *, token):
    if not token:
        raise ValueError("FAIL_GITHUB_AUTH_UNAVAILABLE")
    if not url.startswith("https://api.github.com/repos/" + REPO + "/"):
        raise ValueError("FAIL_GITHUB_URL_SCOPE")
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.build_opener(StripCrossHostToken()).open(request, timeout=25) as response:
        payload = response.read(MAX_ZIP + 1)
    if len(payload) > MAX_ZIP:
        raise ValueError("FAIL_GITHUB_ARTIFACT_OVERSIZED")
    return payload


def artifact_verified(zip_bytes, session):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            files = archive.namelist()
            manifest_paths = [name for name in files
                              if name.split("/")[-1] == "custody_manifest.json"]
            packet_paths = [name for name in files
                            if name.split("/")[-1] == "original_live_timing_packets.txt"]
            if len(manifest_paths) != 1 or len(packet_paths) != 1:
                return False
            if any(info.file_size > MAX_ZIP for info in archive.infolist()):
                return False
            m = json.loads(archive.read(manifest_paths[0]))
            raw = archive.read(packet_paths[0])
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
        return False
    if (m.get("schema") != "qatar-2026-original-live-packet-custody-v1"
            or m.get("session_label") != session
            or m.get("result") != "CAPTURED_ORIGINAL_PACKETS_UNBOUND"
            or m.get("provider_session_key") is not None
            or m.get("source_complete") is not False
            or any(m.get(x) is not False for x in
                   ("forecast_eligible", "prediction_locked", "promotion_allowed"))
            or type(m.get("original_packet_bytes")) is not int
            or m["original_packet_bytes"] != len(raw) or not raw
            or m.get("original_packet_sha256") != hashlib.sha256(raw).hexdigest()
            or type(m.get("packet_lines")) is not int or m["packet_lines"] < 1
            or m.get("recording_clock_valid") is not True):
        return False
    return True


def session_due(now):
    if now.tzinfo is None:
        raise ValueError("FAIL_WATCHDOG_NAIVE_CLOCK")
    at = now.astimezone(UTC)
    for name, start, end, _ in WINDOWS:
        boundary = timestamp(end)
        # 35 to 150 minutes after the observation window closed.
        if boundary + dt.timedelta(minutes=35) <= at < boundary + dt.timedelta(minutes=150):
            return name, start, end
    return None


def assess(*, now=None, token=None, fetch=get, expected_session=None):
    now = now or dt.datetime.now(UTC)
    session = session_due(now)
    if expected_session:
        matches = [w for w in WINDOWS if w[0] == expected_session]
        if len(matches) != 1:
            raise ValueError("FAIL_UNKNOWN_EXPECTED_SESSION")
        name, start, end, _ = matches[0]
        if now.astimezone(UTC) < timestamp(end) + dt.timedelta(minutes=35):
            raise ValueError("FAIL_WATCHDOG_BEFORE_SESSION_CLOSE")
        session = name, start, end
    if not session:
        return {"status": "HOLD_WATCHDOG_NOT_DUE",
                "source_complete": False, "forecast_eligible": False}
    name, start, end = session
    token = token or os.environ.get("GH_TOKEN", "")
    runs_url = BASE + "/actions/workflows/f1-qatar-2026-original-packet-custody.yml/runs?per_page=100"
    runs = json.loads(fetch(runs_url, token=token))
    if not isinstance(runs, dict) or not isinstance(runs.get("workflow_runs"), list):
        raise ValueError("FAIL_ORIGINAL_RUN_CATALOG_MALFORMED")
    candidates = []
    for run in runs["workflow_runs"]:
        if not isinstance(run, dict):
            continue
        try:
            created = timestamp(run["created_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (timestamp(start) <= created <= timestamp(end)
                and run.get("status") == "completed"
                and run.get("conclusion") == "success"
                and run.get("event") in {"schedule", "workflow_dispatch"}
                and run.get("head_branch") == "main"
                and run.get("path") == WORKFLOW_PATH
                and run.get("head_repository", {}).get("full_name") == REPO):
            continue
        if (type(run.get("id")) is int and run["id"] > 0
                and type(run.get("run_attempt")) is int and run["run_attempt"] > 0):
            candidates.append((run["id"], run["run_attempt"]))
    for run_id, attempt in candidates:
        artifact_url = BASE + f"/actions/runs/{run_id}/artifacts?per_page=100"
        listing = json.loads(fetch(artifact_url, token=token))
        if not isinstance(listing.get("artifacts"), list):
            raise ValueError("FAIL_GITHUB_ARTIFACT_CATALOG_MALFORMED")
        for artifact in listing["artifacts"]:
            if (artifact.get("name") != f"f1-qatar-2026-original-packets-{run_id}-{attempt}"
                    or artifact.get("expired") is True
                    or type(artifact.get("id")) is not int):
                continue
            raw = fetch(BASE + f"/actions/artifacts/{artifact['id']}/zip", token=token)
            if artifact_verified(raw, name):
                return {"status": "ORIGINAL_PACKETS_RETAINED_SESSION_UNBOUND",
                        "source_complete": False, "forecast_eligible": False,
                        "session_label": name, "original_run_id": run_id,
                        "original_run_attempt": attempt}
    return {"status": "FAIL_NO_AUTHENTIC_ORIGINAL_CAPTURE_IN_SESSION",
            "source_complete": False, "forecast_eligible": False,
            "session_label": name, "observed_candidate_runs": len(candidates)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected-session", default=None)
    opts = parser.parse_args(argv)
    try:
        result = assess(expected_session=opts.expected_session)
    except (OSError, ValueError, TypeError, KeyError, urllib.error.HTTPError) as exc:
        # No exception message: GitHub/provider errors may carry credentials.
        result = {"status": "FAIL_CAPTURE_WATCHDOG_API_OR_CUSTODY",
                  "error_category": type(exc).__name__,
                  "source_complete": False, "forecast_eligible": False}
    opts.report.parent.mkdir(parents=True, exist_ok=True)
    opts.report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("## Qatar original packet watchdog\n\n" + str(result["status"]) + "\n")
    return 2 if result["status"].startswith("FAIL_") else 0


if __name__ == "__main__":
    raise SystemExit(main())
