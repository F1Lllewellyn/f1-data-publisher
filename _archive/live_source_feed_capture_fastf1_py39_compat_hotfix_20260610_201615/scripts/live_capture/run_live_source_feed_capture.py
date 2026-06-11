#!/usr/bin/env python3
"""
F1 Live Source Feed Capture Layer v0 EXPERIMENTAL

Purpose:
- GitHub-led live source feed capture using FastF1 SignalRClient.
- Records raw live timing packets for post-session replay and proof-loop reconciliation.
- Does not update stable predictions and does not touch canonical workbooks.

Important:
- FastF1 live timing capture is a source-feed recorder, not a real-time prediction processor.
- Outputs are experimental and must be reconciled against post-session OpenF1/FIA/F1 data.
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
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Python compatibility:
# - Python 3.11+ exposes datetime.UTC
# - FastF1 live timing compatibility currently drives us toward Python 3.9,
#   where datetime.UTC does not exist. Use timezone.utc as fallback.
UTC = getattr(dt, "UTC", dt.timezone.utc)

OPENF1_SESSIONS_URL = "https://api.openf1.org/v1/sessions"


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso_now() -> str:
    return now_utc().isoformat().replace("+00:00", "Z")


def parse_dt(value: Any) -> Optional[dt.datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip())
    return text.strip("_") or "session"


def load_policy(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_openf1_sessions(season: int) -> List[Dict[str, Any]]:
    params = {"year": season}
    r = requests.get(OPENF1_SESSIONS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise ValueError("OpenF1 sessions response was not a list")
    return data


def choose_active_window(policy: Dict[str, Any], capture_mode: str, manual_label: str, manual_minutes: Optional[int]) -> Dict[str, Any]:
    capture_cfg = policy.get("capture", {})
    sched_cfg = policy.get("schedule_detection", {})

    if capture_mode == "manual":
        minutes = manual_minutes or int(capture_cfg.get("manual_test_default_minutes", 20))
        return {
            "should_capture": True,
            "reason": "manual_dispatch",
            "session_label": manual_label or "manual_test",
            "duration_minutes": max(1, min(minutes, int(capture_cfg.get("max_capture_minutes", 170)))),
            "session_key": None,
            "meeting_key": None,
            "session_name": manual_label or "manual_test",
            "country_name": None,
            "date_start": None,
            "date_end": None,
        }

    # Scheduled/auto-window mode
    if not capture_cfg.get("enabled_for_schedule", True):
        return {"should_capture": False, "reason": "schedule_capture_disabled"}

    season = int(sched_cfg.get("season", 2026))
    allowlist = set(sched_cfg.get("session_name_allowlist", []))
    pre = dt.timedelta(minutes=int(capture_cfg.get("pre_session_buffer_minutes", 8)))
    post = dt.timedelta(minutes=int(capture_cfg.get("post_session_buffer_minutes", 20)))
    default_minutes = int(capture_cfg.get("auto_window_default_minutes", 145))
    max_minutes = int(capture_cfg.get("max_capture_minutes", 170))
    current = now_utc()

    try:
        sessions = fetch_openf1_sessions(season)
    except Exception as exc:
        return {"should_capture": False, "reason": f"schedule_lookup_failed: {exc}"}

    candidates = []
    for sess in sessions:
        name = sess.get("session_name") or sess.get("session_type") or "unknown_session"
        if allowlist and name not in allowlist:
            continue
        start = parse_dt(sess.get("date_start"))
        end = parse_dt(sess.get("date_end"))
        if not start:
            continue
        # If date_end absent, estimate using session type.
        if not end:
            est_minutes = 150 if "Race" in name else 90
            end = start + dt.timedelta(minutes=est_minutes)
        if start - pre <= current <= end + post:
            candidates.append((start, end, sess))

    if not candidates:
        return {"should_capture": False, "reason": "no_active_capture_window"}

    candidates.sort(key=lambda item: item[0])
    start, end, sess = candidates[0]
    remaining = max(1, int((end + post - current).total_seconds() // 60))
    duration = max(1, min(default_minutes, remaining, max_minutes))
    name = sess.get("session_name") or sess.get("session_type") or "session"
    label = f"{sess.get('country_name','event')}_{name}_{start.strftime('%Y%m%d_%H%MZ')}"
    return {
        "should_capture": True,
        "reason": "active_schedule_window",
        "session_label": label,
        "duration_minutes": duration,
        "session_key": sess.get("session_key"),
        "meeting_key": sess.get("meeting_key"),
        "session_name": name,
        "country_name": sess.get("country_name"),
        "date_start": start.isoformat(),
        "date_end": end.isoformat(),
    }


def record_live_timing(raw_path: Path, duration_minutes: int) -> Dict[str, Any]:
    """Record using FastF1 SignalRClient with defensive handling."""
    result = {
        "recording_attempted": True,
        "recording_started_utc": iso_now(),
        "recording_finished_utc": None,
        "duration_minutes_requested": duration_minutes,
        "raw_path": str(raw_path),
        "fastf1_import_ok": False,
        "recording_status": "not_started",
        "error": None,
    }
    try:
        from fastf1.livetiming.client import SignalRClient  # type: ignore
        result["fastf1_import_ok"] = True
    except Exception as exc:
        result["recording_status"] = "fastf1_import_failed"
        result["error"] = repr(exc)
        result["recording_finished_utc"] = iso_now()
        return result

    client = None
    try:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        client = SignalRClient(filename=str(raw_path), filemode="w")
        client.start()
        result["recording_status"] = "running"
        end_time = time.time() + max(1, duration_minutes) * 60
        while time.time() < end_time:
            time.sleep(5)
        result["recording_status"] = "completed"
    except Exception as exc:
        result["recording_status"] = "recording_error"
        result["error"] = repr(exc)
    finally:
        try:
            if client is not None:
                client.stop()
        except Exception as exc:
            result["stop_error"] = repr(exc)
        result["recording_finished_utc"] = iso_now()
    return result


def build_packet_index(raw_path: Path, index_path: Path) -> Dict[str, Any]:
    """Create a lightweight line/topic index without requiring full FastF1 parsing."""
    summary: Dict[str, Any] = {
        "raw_exists": raw_path.exists(),
        "raw_size_bytes": raw_path.stat().st_size if raw_path.exists() else 0,
        "line_count": 0,
        "topic_counts": {},
        "index_created": False,
    }
    rows = []
    if not raw_path.exists():
        return summary
    topic_re = re.compile(r'"([A-Za-z0-9_./-]+)"')
    with raw_path.open("r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f, start=1):
            if idx > 500000:  # safety cap for index only
                break
            summary["line_count"] += 1
            snippet = line[:240].strip().replace("\t", " ")
            topic = "unknown"
            # Try common SignalR topic hints
            for marker in ["TimingData", "TimingStats", "CarData", "Position", "SessionStatus", "TrackStatus", "WeatherData", "RaceControlMessages", "DriverList", "LapCount"]:
                if marker in line:
                    topic = marker
                    break
            if topic == "unknown":
                m = topic_re.search(line)
                if m:
                    topic = m.group(1)[:80]
            summary["topic_counts"][topic] = summary["topic_counts"].get(topic, 0) + 1
            if idx <= 25000:
                rows.append({"line_number": idx, "topic_hint": topic, "snippet": snippet})

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["line_number", "topic_hint", "snippet"])
        writer.writeheader()
        writer.writerows(rows)
    summary["index_created"] = True
    summary["indexed_rows"] = len(rows)
    return summary


def write_report(out_dir: Path, manifest: Dict[str, Any], readiness: Dict[str, Any], policy: Dict[str, Any]) -> None:
    lines = []
    lines.append("# F1 Live Source Feed Capture Report")
    lines.append("")
    lines.append(f"Generated UTC: {iso_now()}")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(readiness.get("verdict", "unknown"))
    lines.append("")
    lines.append("## Capture status")
    lines.append("")
    for key in ["should_capture", "reason", "session_label", "duration_minutes", "recording_status", "raw_size_bytes", "line_count"]:
        lines.append(f"- {key}: {manifest.get(key, readiness.get(key, ''))}")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for k, v in policy.get("guardrails", {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("This is an experimental live source-feed capture layer. It records source feed evidence for post-session replay and reconciliation. It does not update stable predictions or canonical workbooks.")
    (out_dir / policy["outputs"]["capture_report_filename"]).write_text("\n".join(lines), encoding="utf-8")


def zip_output(out_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out_dir.rglob("*"):
            if p.is_file() and p != zip_path:
                z.write(p, p.relative_to(out_dir))


def copy_to_latest_and_history(work_dir: Path, policy: Dict[str, Any], session_label: str) -> None:
    latest_dir = Path(policy["outputs"]["latest_dir"])
    history_root = Path(policy["outputs"]["history_dir"])
    stamp = now_utc().strftime("%Y%m%d_%H%M%S")
    hist_dir = history_root / f"{stamp}_{safe_slug(session_label)}"
    for target in [latest_dir, hist_dir]:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(work_dir, target)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--capture-mode", default="auto_window")
    ap.add_argument("--duration-minutes", default="")
    ap.add_argument("--session-label", default="")
    ap.add_argument("--github-run-id", default="")
    ap.add_argument("--github-run-attempt", default="")
    args = ap.parse_args()

    policy = load_policy(Path(args.policy))
    manual_minutes = int(args.duration_minutes) if str(args.duration_minutes).strip().isdigit() else None
    decision = choose_active_window(policy, args.capture_mode, args.session_label, manual_minutes)

    session_label = decision.get("session_label", "no_capture")
    run_stamp = now_utc().strftime("%Y%m%d_%H%M%S")
    work_dir = Path("_live_source_feed_capture_work") / f"{run_stamp}_{safe_slug(session_label)}"
    work_dir.mkdir(parents=True, exist_ok=True)

    outputs = policy["outputs"]
    raw_path = work_dir / outputs["raw_capture_filename"]
    index_path = work_dir / outputs["packet_index_filename"]

    recording_result: Dict[str, Any] = {}
    packet_summary: Dict[str, Any] = {}

    if decision.get("should_capture"):
        recording_result = record_live_timing(raw_path, int(decision.get("duration_minutes", 1)))
        packet_summary = build_packet_index(raw_path, index_path)

        # Diagnostic hardening:
        # A capture that fails before writing source-feed bytes should not look like a clean pass.
        # Manual validation can still be "Pass with warnings" when the infrastructure runs but no
        # live packets are available; actual FastF1 import/start errors are Fail so they are visible.
        status = recording_result.get("recording_status")
        raw_bytes = int(packet_summary.get("raw_size_bytes", 0) or 0)
        if status == "completed" and raw_bytes > 0:
            verdict = "Pass"
        elif status == "completed" and raw_bytes == 0:
            verdict = "Pass with warnings"
        elif status in {"fastf1_import_failed", "recording_error"}:
            verdict = "Fail"
        else:
            verdict = "Pass with warnings"
    else:
        verdict = "Pass with warnings"
        # Still write a no-capture manifest so schedule runs are auditable.
        packet_summary = {"raw_exists": False, "raw_size_bytes": 0, "line_count": 0, "topic_counts": {}, "index_created": False}

    manifest = {
        "schema_version": policy.get("schema_version"),
        "module_name": policy.get("module_name"),
        "generated_utc": iso_now(),
        "github_run_id": args.github_run_id,
        "github_run_attempt": args.github_run_attempt,
        **decision,
        **recording_result,
        **packet_summary,
        "source_labels": ["fastf1_live_signalr_raw"],
        "stable_engine_changed": False,
        "canonical_workbook_changed": False,
        "accuracy_claim_changed": False,
    }
    readiness = {
        "generated_utc": iso_now(),
        "verdict": verdict,
        "should_capture": decision.get("should_capture", False),
        "reason": decision.get("reason"),
        "raw_capture_evidence_bearing": packet_summary.get("raw_size_bytes", 0) > 0,
        "packet_index_created": packet_summary.get("index_created", False),
        "requires_post_session_reconciliation": bool(decision.get("should_capture")),
        "team_radio_policy": policy.get("team_radio_policy"),
        "guardrail_stable_engine_unchanged": True,
    }

    diagnostics = {
        "generated_utc": iso_now(),
        "verdict": verdict,
        "decision": decision,
        "recording_result": recording_result,
        "packet_summary": packet_summary,
        "operator_note": (
            "If this is a manual test outside an active F1 live timing window, zero raw bytes may be expected. "
            "If recording_status is recording_error or fastf1_import_failed, inspect the error field and patch before race-weekend use."
        ),
    }

    (work_dir / "live_source_feed_capture_diagnostics.json").write_text(json.dumps(diagnostics, indent=2, default=str), encoding="utf-8")
    (work_dir / outputs["manifest_filename"]).write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (work_dir / outputs["readiness_filename"]).write_text(json.dumps(readiness, indent=2), encoding="utf-8")
    write_report(work_dir, manifest, readiness, policy)
    zip_path = work_dir / outputs["zip_filename"]
    zip_output(work_dir, zip_path)
    (work_dir / f"{outputs['zip_filename']}.sha256.txt").write_text(f"{sha256_file(zip_path)}  {outputs['zip_filename']}\n", encoding="utf-8")

    copy_to_latest_and_history(work_dir, policy, session_label)
    print(json.dumps({
        "verdict": verdict,
        "decision": decision,
        "recording_status": recording_result.get("recording_status"),
        "recording_error": recording_result.get("error"),
        "raw_size_bytes": packet_summary.get("raw_size_bytes", 0),
        "line_count": packet_summary.get("line_count", 0),
        "work_dir": str(work_dir),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
