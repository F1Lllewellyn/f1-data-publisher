#!/usr/bin/env python3
"""Isolated, resumable 2026 historical-session recovery using existing processor.

A bounded historical selector for audited missing session snapshots, NOT a new
production publisher, forecast source, pre-race provenance claim, or promotion.
Only writes under --output-dir. Does not dispatch Actions or edit the repository.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import sys
import urllib.parse
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

CUTOFF = dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc)
SOURCE_LANES = ("drivers", "weather", "race_control", "intervals", "position", "stints", "pit", "starting_grid")
APPROVED_OPENF1_HOST = "api.openf1.org"
APPROVED_OPENF1_ENDPOINTS = {"drivers", "laps", "intervals", "position", "pit", "stints", "race_control", "weather", "session_result", "starting_grid"}
NUMERIC_INT = {"session_key", "meeting_key", "driver_number", "position", "lap_number", "year", "circuit_key", "country_key"}
NUMERIC_FLOAT = {"lap_duration", "duration_sector_1", "duration_sector_2", "duration_sector_3",
                 "air_temperature", "track_temperature", "pressure", "humidity", "wind_speed",
                 "wind_direction", "rainfall", "pit_duration", "stint_number", "tyre_age_at_start"}



def approved_source_request(url: str, allowed_session_keys: set[int]) -> tuple[str, int]:
    """Fail closed unless URL is an exact OpenF1 REST v1 session endpoint.

    No search, scraping, third-party proxy, alternate host or arbitrary URLs.
    """
    parsed = urllib.parse.urlparse(url)
    if (parsed.scheme != "https" or parsed.netloc != APPROVED_OPENF1_HOST
            or parsed.username is not None or parsed.password is not None
            or parsed.port is not None or parsed.fragment or parsed.params):
        raise RuntimeError("UNAPPROVED_SOURCE_URL_HOLD")
    parts = parsed.path.split("/")
    if len(parts) != 3 or parts[0] != "" or parts[1] != "v1" or parts[2] not in APPROVED_OPENF1_ENDPOINTS:
        raise RuntimeError("UNAPPROVED_SOURCE_ENDPOINT_HOLD")
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if len(pairs) != 1 or pairs[0][0] != "session_key" or not pairs[0][1].isdigit():
        raise RuntimeError("UNAPPROVED_SOURCE_QUERY_HOLD")
    key = int(pairs[0][1])
    if key not in allowed_session_keys:
        raise RuntimeError("UNAUTHORIZED_SESSION_KEY_HOLD")
    return parts[2], key


def parse_utc(s: str) -> dt.datetime:
    result = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp has no UTC offset")
    return result.astimezone(dt.timezone.utc)


def parse_cell(key: str, value: str):
    if value == "":
        return None
    if key in NUMERIC_INT:
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"non-numeric integer field {key}") from exc
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError(f"non-integral integer field {key}")
        return int(number)
    if key in NUMERIC_FLOAT:
        return float(value)
    if key == "is_cancelled":
        if value not in ("True", "False"):
            raise ValueError("non-boolean is_cancelled")
        return value == "True"
    return value


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [{k: parse_cell(k, v) for k, v in row.items() if v is not None}
                for row in csv.DictReader(f)]


def index_cache(repo: Path, allowed_keys: set[int]) -> dict[str, dict[int, list[dict]]]:
    base = repo / "latest/openf1_lightweight_source_closure/data"
    indexed: dict[str, dict[int, list[dict]]] = {}
    for lane in SOURCE_LANES:
        file = base / f"openf1_{lane}.csv"
        selected = defaultdict(list)
        if file.exists():
            # One streaming pass per source file, not one download/read per session.
            with file.open(newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    key = int(row.get("session_key") or 0)
                    if key in allowed_keys:
                        selected[key].append({k: parse_cell(k, v) for k, v in row.items()
                                              if v is not None})
        indexed[lane] = dict(selected)
    return indexed


def merge_recovery_cache(out: Path, allowed_keys: set[int], indexed: dict[str, dict[int, list[dict]]]) -> None:
    """Reuse previously retained isolated output before any additional GET."""
    base = out / "latest/session_data_processor"
    if not base.is_dir():
        return
    for raw_json in base.glob("*/*/raw/openf1_*.json"):
        endpoint = raw_json.stem.removeprefix("openf1_")
        if endpoint not in APPROVED_OPENF1_ENDPOINTS:
            continue
        rows = json.loads(raw_json.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or not rows:
            continue
        keys = {int(row["session_key"]) for row in rows
                if isinstance(row, dict) and row.get("session_key") is not None}
        if len(keys) != 1:
            continue
        key = next(iter(keys))
        if key in allowed_keys and not indexed.setdefault(endpoint, {}).get(key):
            indexed[endpoint][key] = rows


def required_endpoints_for_session(session: dict) -> set[str]:
    """Mirror the accepted aggregation-v2 critical-source policy."""
    raw = f"{session.get('session_name', '')} {session.get('session_type', '')}".lower()
    if "practice" in raw or any(token in raw for token in ("fp1", "fp2", "fp3")):
        return {"drivers", "laps", "position", "weather"}
    if "sprint qualifying" in raw or "sprint_shootout" in raw or "qualifying" in raw:
        return {"drivers", "laps", "position", "session_result", "weather"}
    if ("sprint" in raw and "qual" not in raw) or "race" in raw:
        return {"drivers", "laps", "position", "race_control", "session_result", "starting_grid", "weather"}
    return {"drivers", "laps", "position", "weather"}


def provider_gets_needed(session: dict, cache: dict[str, dict[int, list[dict]]]) -> int:
    """Return the deterministic live-GET ceiling for one target session.

    Optional high-volume lanes and starting-grid evidence are deliberately not
    fetched by this recovery wrapper.  This preflight prevents a session from
    starting when the remaining batch budget cannot cover every permitted
    required request.
    """
    key = int(session["session_key"])
    # For Race/Sprint, the one starting-grid count covers the processor's
    # local target probe followed by at most one qualifying-source GET.
    required = required_endpoints_for_session(session)
    return sum(1 for endpoint in required if not cache.get(endpoint, {}).get(key))


def load_processor(repo: Path):
    path = repo / "scripts/session_data_processor/session_data_processor_loop_v1.py"
    helper = repo / "scripts/session_data_processor"
    if not path.is_file() or not (helper / "source_readiness_aggregation_v2.py").is_file():
        raise RuntimeError("Existing processor/aggregator missing; do not substitute alternate logic")
    sys.path.insert(0, str(helper))
    spec = importlib.util.spec_from_file_location("f1_2026_isolated_processor", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def audit_keys(repo: Path, branch_audit: Path, source_sessions: list[dict]) -> list[dict]:
    lookup = {int(s["session_key"]): s for s in source_sessions}
    with branch_audit.open(newline="", encoding="utf-8-sig") as f:
        candidates = {int(r["session_key"]): r for r in csv.DictReader(f)
                      if r["source"] == "sessions" and
                      r["processor_readiness"] == "NO_CURRENT_PROCESSOR_SNAPSHOT"}
    if len(candidates) != 39:
        raise RuntimeError(f"Expected exactly 39 audited absent snapshots; found {len(candidates)}: HOLD/reinventory")
    selected = []
    for k, row in sorted(candidates.items(), key=lambda x: (int(x[1]["round"]), x[1]["scheduled_start_utc"])):
        s = lookup.get(k)
        if (not s or int(s["year"]) != 2026 or s.get("is_cancelled") is not False or
                int(s["meeting_key"]) != int(row["meeting_key"]) or
                str(s["session_name"]) != row["session_name"] or
                parse_utc(str(s["date_end"])) >= CUTOFF):
            raise RuntimeError(f"Unverified/cancelled/future session identity {k}: HOLD")
        selected.append(s)
    return selected


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--max-sessions", type=int, default=4)
    ap.add_argument("--max-provider-gets", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--authorize-openf1-gets", action="store_true",
                    help="Explicit opt-in to source-limited direct api.openf1.org/v1 GETs")
    ap.add_argument("--retry-session-key", action="append", type=int, default=[],
                    help="Explicitly retry a previously failed session; never automatic")
    args = ap.parse_args()
    repo = args.repo.resolve()
    out = args.output_dir.resolve()
    if args.max_sessions < 1 or args.max_sessions > 4 or args.max_provider_gets < 0 or args.max_provider_gets > 8:
        raise SystemExit("BATCH_LIMIT_HOLD: <=4 sessions and <=8 provider GETs")
    if not args.dry_run and not args.offline and not args.authorize_openf1_gets:
        raise SystemExit("DIRECT_OPENF1_GETS_NOT_AUTHORIZED: use --offline or --authorize-openf1-gets")
    if args.offline and args.authorize_openf1_gets:
        raise SystemExit("AMBIGUOUS_SOURCE_MODE_HOLD: choose offline OR direct OpenF1 GET authorization")
    protected = (repo / "latest", repo / "history", repo / "Engine_2026-06-07_STABLE", repo / "workbooks", repo / ".github")
    if out == repo or any(out == p or p in out.parents for p in protected):
        raise SystemExit("PROTECTED_OUTPUT_PATH_HOLD")
    targets = read_csv(repo / "latest/openf1_lightweight_source_closure/data/target_sessions.csv")
    selected = audit_keys(repo, args.audit, targets)
    if args.dry_run:
        print(json.dumps({"status": "DRY_RUN_VALIDATED", "audited_missing": len(selected),
                          "first_sessions": [s["session_key"] for s in selected[:args.max_sessions]],
                          "writes": False, "provider_gets": 0}, indent=2))
        return 0
    out.mkdir(parents=True, exist_ok=True)
    state_file = out / "historical_recovery_checkpoint.json"
    state = json.loads(state_file.read_text()) if state_file.is_file() else {
        "attempted": [], "processed": [], "failed": [], "results": [], "provider_gets": 0,
    }
    for key, default in (("attempted", []), ("processed", []), ("failed", []),
                         ("results", []), ("batches", []), ("provider_gets", 0)):
        state.setdefault(key, default)
    # Repair candidate-v2 checkpoints that treated a required-source `late`
    # result as complete.  Such sessions remain explicitly retryable/HOLD.
    latest_result = {int(item["session_key"]): item for item in state["results"]
                     if item.get("session_key") is not None}
    late_keys = {key for key, item in latest_result.items() if item.get("status") == "late"}
    if late_keys:
        state["processed"] = [key for key in state["processed"] if int(key) not in late_keys]
        failed_map = {int(item["session_key"]): item for item in state["failed"]}
        for key in late_keys:
            failed_map[key] = {**latest_result[key], "status": "HOLD",
                               "error": "required_source_late_or_empty",
                               "processing_complete": False}
        state["failed"] = list(failed_map.values())
    audited_keys = {int(s["session_key"]) for s in selected}
    retry_keys = set(args.retry_session_key)
    if retry_keys - audited_keys:
        raise SystemExit("UNAUTHORIZED_RETRY_SESSION_KEY_HOLD")
    failed_keys = {int(item["session_key"]) for item in state["failed"]}
    if retry_keys - failed_keys:
        raise SystemExit("RETRY_REQUIRES_PREVIOUS_FAILED_CHECKPOINT_HOLD")
    attempted = {int(key) for key in state["attempted"]}
    candidates = [s for s in selected
                  if int(s["session_key"]) not in attempted or int(s["session_key"]) in retry_keys]
    candidates = candidates[:args.max_sessions]
    todo = list(candidates)
    if not todo:
        print(json.dumps({"status": "NO_NEW_SESSIONS", "attempted": len(attempted),
                          "processed": len(state["processed"]), "failed": len(state["failed"])}))
        return 0
    allowed_keys = {int(s["session_key"]) for s in todo} | {
        int(s["session_key"]) for s in targets if any(s["meeting_key"] == t["meeting_key"] for t in todo)
        and s["session_name"] in ("Qualifying", "Sprint Qualifying")}
    cache = index_cache(repo, allowed_keys)
    merge_recovery_cache(out, allowed_keys, cache)
    if args.authorize_openf1_gets:
        budgeted = []
        projected_gets = 0
        for session in todo:
            needed = provider_gets_needed(session, cache)
            if needed > args.max_provider_gets:
                raise SystemExit(f"SESSION_EXCEEDS_PROVIDER_BUDGET_HOLD:{session['session_key']}:{needed}")
            if projected_gets + needed > args.max_provider_gets:
                break
            budgeted.append(session)
            projected_gets += needed
        todo = budgeted
        if not todo:
            raise SystemExit("NO_SESSION_FITS_PROVIDER_BUDGET_HOLD")
        allowed_keys = {int(s["session_key"]) for s in todo} | {
            int(s["session_key"]) for s in targets if any(s["meeting_key"] == t["meeting_key"] for t in todo)
            and s["session_name"] in ("Qualifying", "Sprint Qualifying")
        }
        cache = index_cache(repo, allowed_keys)
        merge_recovery_cache(out, allowed_keys, cache)
    processor = load_processor(repo)
    original_http = processor.http_json
    budget = [0]
    requests_observed = []
    session_by_key = {int(s["session_key"]): s for s in targets}
    target_required = {
        int(s["session_key"]): required_endpoints_for_session(s) for s in todo
    }
    grid_source_keys = {
        int(candidate["session_key"])
        for target in todo
        if "starting_grid" in required_endpoints_for_session(target)
        for candidate in targets
        if candidate.get("meeting_key") == target.get("meeting_key")
        and str(candidate.get("session_name") or "").strip().lower()
        == ("sprint qualifying" if str(target.get("session_name") or "").strip().lower() == "sprint"
            else "qualifying")
    }

    def cached_or_provider(url: str, timeout: int = 30, **kwargs):
        endpoint, key = approved_source_request(url, allowed_keys)
        rows = cache.get(endpoint, {}).get(key, [])
        if rows:
            return rows, {"ok": True, "source": "REUSED_POSTEVENT_LIGHTWEIGHT_CACHE",
                          "url": url, "endpoint": endpoint, "session_key": key,
                          "rows": len(rows), "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        # An explicitly queried race grid is often empty; allow the original
        # processor to resolve its unique same-meeting qualifying source.
        if endpoint == "starting_grid" and endpoint in target_required.get(key, set()):
            return [], {"ok": True, "source": "cache_absent_unverified", "url": url,
                        "endpoint": endpoint, "session_key": key, "rows": 0,
                        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        permitted = endpoint in target_required.get(
            key, required_endpoints_for_session(session_by_key.get(key, {})))
        if endpoint == "starting_grid" and key in grid_source_keys:
            permitted = True
        if not permitted:
            return [], {"ok": False, "error": "optional_cache_absent_not_fetched", "url": url,
                        "endpoint": endpoint, "session_key": key, "rows": 0}
        if args.offline or budget[0] >= args.max_provider_gets:
            return [], {"ok": False, "error": "BOUNDED_SOURCE_FETCH_HOLD", "url": url,
                        "endpoint": endpoint, "session_key": key, "rows": 0}
        budget[0] += 1
        result = original_http(url, timeout=timeout, retries=0, sleep_seconds=0)
        result[1].update({"source": "LIVE_POSTEVENT_FETCH", "url": url, "endpoint": endpoint,
                          "session_key": key, "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
        requests_observed.append({"endpoint": endpoint, "session_key": key,
                                  "ok": bool(result[1].get("ok")), "status_code": result[1].get("status_code"),
                                  "rows": len(result[0]), "bytes": result[1].get("bytes"),
                                  "sha256": result[1].get("sha256"), "url": url,
                                  "observed_at_utc": result[1]["observed_at_utc"],
                                  "source": "LIVE_POSTEVENT_FETCH"})
        if result[1].get("ok") and result[0]:
            cache.setdefault(endpoint, {})[key] = result[0]
        return result

    processor.ROOT = out
    processor.RUNTIME = out / "_runtime" / "session_data_processor"
    processor.POLICY_PATH = repo / "configs/session_data_processor/session_data_processor_policy_v1.json"
    processor.fetch_sessions = lambda year: (targets, {"ok": True, "source": "reused_target_sessions_csv"})
    processor.http_json = cached_or_provider
    orig_argv = sys.argv
    counted_provider_gets = 0
    for s in todo:
        processor.select_recent_completed_session = lambda all_sessions, now, lookback, forced, target=s: target
        sys.argv = ["historical_processor", "--mode", "manual_session", "--season", "2026",
                    "--write-public-latest", "false", "--side-load-root", str(out / "no_side_load")]
        try:
            code = processor.main()
            result_path = processor.RUNTIME / "session_processor_result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if code != 0 or int(result.get("session_key") or 0) != int(s["session_key"]):
                raise RuntimeError("processor execution failed or wrong session identity")
            manifest_path = out / result["latest_output"] / "source_readiness_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            fetch_holds = []
            for source_name, source in manifest.get("sources", {}).items():
                error = str((source.get("fetch") or {}).get("error") or "")
                endpoint = str(source.get("endpoint") or source_name).removeprefix("openf1_")
                role = ((manifest.get("readiness_aggregation") or {}).get("per_source") or {}).get(
                    source_name, {}).get("role")
                if role == "required" and error == "BOUNDED_SOURCE_FETCH_HOLD":
                    fetch_holds.append(endpoint)
                if role == "required" and (source.get("fetch") or {}).get("source") == "LIVE_POSTEVENT_FETCH" \
                        and not (source.get("fetch") or {}).get("ok"):
                    fetch_holds.append(endpoint)
            for item in (manifest.get("readiness_aggregation") or {}).get("critical_late", []):
                fetch_holds.append(str(item.get("endpoint") or item.get("source") or "required_source"))
            record = {"session_key": s["session_key"], "status": result.get("overall_status"),
                      "source_counts": result.get("source_counts"),
                      "source_statuses": result.get("source_statuses"),
                      "latest_output": result.get("latest_output"),
                      "history_output": result.get("history_output"),
                      "processing_complete": not fetch_holds,
                      "note": "postevent historical recovery, not prospective; consumer untested"}
            if fetch_holds:
                record.update({"status": "HOLD", "error": "required_source_fetch_incomplete",
                               "affected_endpoints": sorted(set(fetch_holds))})
                state["failed"] = [item for item in state["failed"]
                                   if int(item["session_key"]) != int(s["session_key"])]
                state["failed"].append(record)
            else:
                if int(s["session_key"]) not in {int(key) for key in state["processed"]}:
                    state["processed"].append(s["session_key"])
                state["failed"] = [item for item in state["failed"]
                                   if int(item["session_key"]) != int(s["session_key"])]
            state["results"].append(record)
        except Exception as exc:
            record = {"session_key": s["session_key"], "status": "HOLD", "error": repr(exc),
                      "processing_complete": False}
            state["results"].append(record)
            state["failed"] = [item for item in state["failed"]
                               if int(item["session_key"]) != int(s["session_key"])]
            state["failed"].append(record)
        finally:
            if int(s["session_key"]) not in {int(key) for key in state["attempted"]}:
                state["attempted"].append(s["session_key"])
            state["provider_gets"] += budget[0] - counted_provider_gets
            counted_provider_gets = budget[0]
            state_file.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    sys.argv = orig_argv
    receipt = {"status": "BOUNDED_BATCH_COMPLETE", "attempted_in_batch": len(todo),
               "session_keys": [int(s["session_key"]) for s in todo],
               "processed_total": len(state["processed"]), "failed_total": len(state["failed"]),
               "provider_requests": requests_observed, "checkpoint": str(state_file),
               "promotion_allowed": False, "pre_race_availability_proven": False,
               "consumer_access_proven": False, "stable_engine_modified": False,
               "source_policy": "approved_direct_OpenF1_v1_only", "external_scrapers_allowed": False,
               "provider_requests_authorized": bool(args.authorize_openf1_gets)}
    receipt["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    state["batches"].append(receipt)
    state_file.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    receipt_dir = out / "batch_receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_name = "historical_batch_" + "_".join(str(s["session_key"]) for s in todo) + ".json"
    (receipt_dir / receipt_name).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    (out / "historical_batch_result.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
