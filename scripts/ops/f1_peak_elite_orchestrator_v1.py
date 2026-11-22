#!/usr/bin/env python3
"""F1 Peak-Elite Orchestrator v1.

One-button orchestration layer for the F1 Prediction Engine GitHub automation
system. It checks workflow syntax without modifying code, validates the automation layer,
runs the source-backed session -> workbook/KPI -> readiness chain, and writes a
machine-readable status for ChatGPT/Race/Fantasy chats.

Hard guards: no stable-engine modification, no canonical workbook overwrite, no
model promotion, no forced push, no prediction execution/change by itself.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

PROTECTED_STABLE = "Engine_2026-06-07_STABLE"
PROTECTED_WORKBOOKS = [
    "F1_2026_Prediction_Model_Data_Workbook.xlsx",
    "F1_2026_Prediction_Model_Data_Workbook_updated_2026-06-06_v15_fastf1_kpi_integrated.xlsx",
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def run(repo: Path, label: str, cmd: List[str], timeout: int = 1200, allow_fail: bool = False) -> Dict[str, Any]:
    print(f"\n--- {label} ---")
    print(" ".join(cmd))
    started = iso_now()
    try:
        proc = subprocess.run(cmd, cwd=str(repo), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        print(proc.stdout[-8000:])
        return {
            "label": label,
            "cmd": cmd,
            "started_utc": started,
            "finished_utc": iso_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "allow_fail": allow_fail,
            "output_tail": proc.stdout[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {"label": label, "cmd": cmd, "started_utc": started, "finished_utc": iso_now(), "returncode": 124, "ok": False, "timeout": True, "output_tail": str(exc)[-4000:]}
    except Exception as exc:
        return {"label": label, "cmd": cmd, "started_utc": started, "finished_utc": iso_now(), "returncode": 1, "ok": False, "exception": repr(exc), "output_tail": repr(exc)}


def protected_touched(repo: Path) -> List[str]:
    git = shutil.which("git")
    if not git:
        return ["HOLD_GIT_STATUS_UNAVAILABLE"]
    proc = subprocess.run([git, "status", "--porcelain"], cwd=str(repo), text=True, capture_output=True)
    if proc.returncode:
        return ["HOLD_GIT_STATUS_UNAVAILABLE"]
    touched: List[str] = []
    for line in proc.stdout.splitlines():
        rel = line[3:].strip() if len(line) > 3 else line.strip()
        if PROTECTED_STABLE.lower() in rel.lower() or any(w.lower() in rel.lower() for w in PROTECTED_WORKBOOKS):
            touched.append(rel)
    return touched


def byte_fingerprints(repo: Path, paths) -> Dict[str, str]:
    result = {}
    if not isinstance(paths, (dict, list, tuple, set)):
        return result
    for relative in sorted({p for p in paths if isinstance(p, str)}):
        path = repo / relative
        try:
            if (not Path(relative).is_absolute() and ".." not in Path(relative).parts
                    and path.is_file() and not path.is_symlink()
                    and path.resolve().is_relative_to(repo.resolve())):
                result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    return result


def execution_authority(operation, protected, hard_failed, soft_failed, downstream_current):
    """Diagnostic permission is not a verified context or forecast receipt."""
    operational_pass = not (protected or hard_failed or soft_failed)
    context_verified = operational_pass and operation == "full_run_chain" and downstream_current
    return dict(operational_execution="OPERATIONAL_PASS" if operational_pass else "OPERATIONAL_FAIL",
                diagnostic_commit_allowed=not (protected or hard_failed),
                context_verified=bool(context_verified), consumer_eligible=bool(context_verified),
                scientific_eligible=False, scientific_status="HOLD_STABLE_ENGINE_NOT_EXECUTED")


def verify_bridge_input(repo: Path, reference_time=None) -> Dict[str, Any]:
    """Bind a consumer to a successful recent capture and all committed input bytes.

    This attests operational context only, never engine execution or a forecast.
    A workflow_run trigger additionally pins the originating run/attempt/code SHA.
    """
    upstream = read_json(repo / "latest/peak_elite/orchestrator_status.json", {})
    upstream = upstream if isinstance(upstream, dict) else {}
    reasons = []
    now = reference_time or dt.datetime.now(dt.timezone.utc)
    try:
        created = dt.datetime.fromisoformat(upstream["created_utc"].replace("Z", "+00:00"))
        if created.tzinfo is None or not 0 <= (now - created).total_seconds() <= 90 * 60:
            raise ValueError("stale or future upstream report")
    except (KeyError, TypeError, ValueError, AttributeError):
        reasons.append("HOLD_UPSTREAM_TIME_INVALID_OR_STALE")
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_run" or any(
            os.environ.get(key) for key in ("UPSTREAM_RUN_ID", "UPSTREAM_RUN_ATTEMPT", "UPSTREAM_HEAD_SHA")):
        for field, env in (("github_run_id", "UPSTREAM_RUN_ID"),
                           ("github_run_attempt", "UPSTREAM_RUN_ATTEMPT"),
                           ("workflow_head_sha", "UPSTREAM_HEAD_SHA")):
            if not os.environ.get(env) or upstream.get(field) != os.environ[env]:
                reasons.append(f"HOLD_UPSTREAM_RUN_MISMATCH:{field}")
    if (upstream.get("operation") != "full_run_chain" or upstream.get("failed_steps") != []
            or upstream.get("downstream_current") is not True
            or upstream.get("commit_allowed") is not True):
        reasons.append("HOLD_UPSTREAM_CONTEXT_NOT_VERIFIED")
    steps = upstream.get("steps", [])
    steps = steps if isinstance(steps, list) else []
    required = ("session_data_processor_run_now", "workbook_kpi_refresh_apply", "dashboard_readiness_publish")
    for label in required:
        matches = [s for s in steps if isinstance(s, dict) and s.get("label") == label]
        if len(matches) != 1 or matches[0].get("ok") is not True:
            reasons.append(f"HOLD_UPSTREAM_STAGE_NOT_VERIFIED:{label}")
    # An exit-0 processor can be a no-op. Old source bytes cannot become a new capture.
    selector = read_json(repo / "latest/latest_manifest.json", {})
    try:
        capture = next(s for s in steps if s.get("label") == required[0])
        start = dt.datetime.fromisoformat(capture["started_utc"].replace("Z", "+00:00"))
        observed = dt.datetime.fromisoformat(selector["updated_utc"].replace("Z", "+00:00"))
        if not start <= observed <= created <= now:
            raise ValueError("source was not captured by the declared run")
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration, UnboundLocalError):
        reasons.append("HOLD_SOURCE_NOT_CAPTURED_IN_UPSTREAM_RUN")
    fingerprints = upstream.get("handoff_fingerprints")
    mandatory = {"latest/latest_manifest.json", "latest/data_readiness.json", "latest/combined_source_manifest.json",
                 "latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json",
                 "latest/readiness_dashboards/combined_readiness_dashboard.json"}
    if (not isinstance(fingerprints, dict) or not mandatory.issubset(fingerprints)
            or byte_fingerprints(repo, fingerprints) != fingerprints):
        reasons.append("HOLD_UPSTREAM_BYTES_CHANGED_OR_MISSING")
    spec = importlib.util.spec_from_file_location("bridge_dashboard", Path(__file__).resolve().parents[1] / "dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        current = module.discover_state(repo, reference_time=now)
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        current = {}
    state = upstream.get("latest_state", {})
    state = state if isinstance(state, dict) else {}
    if (current.get("downstream_eligible") is not True
            or current.get("event_id") != state.get("event_id")
            or str(current.get("session_key")) != str(state.get("session_key"))):
        reasons.append("HOLD_UPSTREAM_SESSION_NOT_CURRENT")
    # The originating report must bind every byte required by the current verifier.
    consumed = current.get("consumed_fingerprints", {})
    if not isinstance(fingerprints, dict) or any(fingerprints.get(p) != sha for p, sha in consumed.items()):
        reasons.append("HOLD_UPSTREAM_CUSTODY_INCOMPLETE")
    return {"status": "HOLD" if reasons else "VERIFIED_CONTEXT_ONLY", "reasons": reasons,
            "upstream_run_id": upstream.get("github_run_id"), "upstream_run_attempt": upstream.get("github_run_attempt"),
            "event_id": state.get("event_id"), "session_key": state.get("session_key"),
            "consumed_fingerprints": fingerprints, "prediction_locked": False,
            "stable_engine_executed": False, "promotion_allowed": False}


def verify_bridge_output(repo: Path, reference_time=None) -> Dict[str, Any]:
    """Check the actual legacy consumer selections before their outputs publish."""
    result = verify_bridge_input(repo, reference_time=reference_time)
    reasons = list(result["reasons"])
    selector = read_json(repo / "latest/latest_manifest.json", {})
    selector = selector if isinstance(selector, dict) else {}
    bundle_path = "latest/forecast_bundle_ledger/latest_bundle_snapshot.json"
    bundle = read_json(repo / bundle_path, {})
    bundle = bundle if isinstance(bundle, dict) else {}
    for field, expected in (("source", selector.get("latest_session_data_processor_manifest")),
                            ("workbook", "latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json")):
        value = bundle.get(field, {})
        if not isinstance(value, dict) or value.get("manifest_path") != expected or not expected:
            reasons.append(f"HOLD_CONSUMER_INPUT_SELECTION:{field}")
    relatives = [bundle_path, "latest/readiness_handoff/combined_readiness_handoff.json",
        "latest/downstream_consumers/combined_downstream_consumer_manifest.json",
        "latest/chat_context/combined_context_index.json",
        "latest/consumer_trigger_governor/trigger_decision.json",
        "latest/notification_routing/notification_decision.json"]
    relatives += [f"latest/downstream_consumers/{c}/consumer_input.json"
                  for c in ("race_predictions", "fantasy_predictions", "race_reports")]
    marker = repo / "_runtime/1b_output_contract/start.marker"
    now = reference_time or dt.datetime.now(dt.timezone.utc)
    upstream = read_json(repo / "latest/peak_elite/orchestrator_status.json", {})
    output_fingerprints = byte_fingerprints(repo, relatives)
    previous = read_json(repo / "latest/1b_output_contract/verified_context_custody.json", {})
    # G3 intentionally leaves identical outputs untouched. A retry can reuse
    # them only when the complete earlier verification receipt binds these exact
    # bytes to the same still-current original capture. Missing/changed receipts
    # do not waive the normal same-run modification-time requirement.
    verified_retry = (
        not reasons and isinstance(previous, dict)
        and previous.get("status") == "VERIFIED_CONTEXT_ONLY"
        and previous.get("reasons") == []
        and all(previous.get(key) == result.get(key) for key in
                ("upstream_run_id", "upstream_run_attempt", "event_id", "session_key", "consumed_fingerprints"))
        and previous.get("bundle_run_id") == bundle.get("run_id")
        and bool(bundle.get("run_id"))
        and set(output_fingerprints) == set(relatives)
        and previous.get("output_fingerprints") == output_fingerprints
        and all(previous.get(key) is False for key in
                ("prediction_locked", "stable_engine_executed", "promotion_allowed"))
    )
    for relative in relatives:
        path = repo / relative
        value = read_json(path, {})
        value = value if isinstance(value, dict) else {}
        event = value.get("event", {})
        event = event if isinstance(event, dict) else {}
        if (event.get("event_id") != result.get("event_id")
                or str(event.get("session_key")) != str(result.get("session_key"))):
            reasons.append(f"HOLD_CONSUMER_SESSION_MISMATCH:{relative}")
        if value.get("promotion_allowed") is not False or value.get("forecast_gate_activated", False) is not False:
            reasons.append(f"HOLD_CONSUMER_UNSAFE_AUTHORITY:{relative}")
        try:
            created = dt.datetime.fromisoformat(upstream["created_utc"].replace("Z", "+00:00"))
            observed = dt.datetime.fromisoformat(value["generated_at_utc"].replace("Z", "+00:00"))
            # Legacy consumer timestamps have second precision; no future time is allowed.
            if not created.replace(microsecond=0) <= observed <= now:
                raise ValueError("consumer chronology")
        except (KeyError, TypeError, ValueError, AttributeError):
            reasons.append(f"HOLD_CONSUMER_TIME_INVALID:{relative}")
        if "run_id" in value and value.get("run_id") != bundle.get("run_id"):
            reasons.append(f"HOLD_CONSUMER_BUNDLE_MISMATCH:{relative}")
        if (not marker.is_file() or not path.is_file()
                or (path.stat().st_mtime_ns <= marker.stat().st_mtime_ns and not verified_retry)):
            reasons.append(f"HOLD_CONSUMER_NOT_WRITTEN_THIS_RUN:{relative}")
    result.update(status="HOLD" if reasons else "VERIFIED_CONTEXT_ONLY", reasons=reasons,
                  bundle_run_id=bundle.get("run_id"), output_fingerprints=output_fingerprints)
    return result


def fetch_original_run(run_id: str) -> Dict[str, Any]:
    """One bounded authenticated GitHub read; never dispatch or retry a provider."""
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    if repository != "F1Lllewellyn/f1-data-publisher" or not token:
        raise ValueError("HOLD_UPSTREAM_API_AUTH_OR_REPOSITORY")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/runs/{run_id}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError(f"HOLD_UPSTREAM_API_HTTP_{response.status}")
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("HOLD_UPSTREAM_API_RESPONSE_TOO_LARGE")
    return json.loads(raw)


def verify_bridge_origin(repo: Path, reference_time=None, input_result=None) -> Dict[str, Any]:
    """A committed status alone does not prove the originating workflow completed."""
    result = verify_bridge_input(repo, reference_time=reference_time) if input_result is None else input_result
    if result["reasons"]:
        return result
    status = read_json(repo / "latest/peak_elite/orchestrator_status.json", {})
    reasons = result["reasons"]
    run_id, attempt, head = (status.get(k, "") for k in
                             ("github_run_id", "github_run_attempt", "workflow_head_sha"))
    if (not re.fullmatch(r"[1-9][0-9]*", str(run_id))
            or not re.fullmatch(r"[1-9][0-9]*", str(attempt))
            or not re.fullmatch(r"[0-9a-f]{40}", str(head))):
        reasons.append("HOLD_UPSTREAM_ORIGIN_IDENTITY")
    else:
        try:
            run_info = fetch_original_run(str(run_id))
            expected_repo = "F1Lllewellyn/f1-data-publisher"
            if (not isinstance(run_info, dict)
                    or str(run_info.get("id")) != str(run_id)
                    or str(run_info.get("run_attempt")) != str(attempt)
                    or run_info.get("head_sha") != head
                    or run_info.get("head_branch") != "main"
                    or run_info.get("path") != ".github/workflows/f1-peak-elite-control-room-one-click-v1.yml"
                    or run_info.get("repository", {}).get("full_name") != expected_repo
                    or run_info.get("head_repository", {}).get("full_name") != expected_repo
                    or run_info.get("event") not in {"schedule", "workflow_dispatch"}):
                reasons.append("HOLD_UPSTREAM_ORIGINAL_RUN_MISMATCH")
            elif run_info.get("status") != "completed" or run_info.get("conclusion") != "success":
                reasons.append("HOLD_UPSTREAM_ORIGINAL_RUN_NOT_SUCCESSFUL")
            else:
                times = [dt.datetime.fromisoformat(value.replace("Z", "+00:00")) for value in
                         (run_info["run_started_at"], status["created_utc"], run_info["updated_at"])]
                now = reference_time or dt.datetime.now(dt.timezone.utc)
                if not all(t.tzinfo is not None for t in times) or not times[0] <= times[1] <= times[2] <= now:
                    reasons.append("HOLD_UPSTREAM_ORIGINAL_RUN_CHRONOLOGY")
                result["original_event"] = run_info["event"]
                result["original_completed_utc"] = run_info["updated_at"]
        except urllib.error.HTTPError as exc:
            reasons.append(f"HOLD_UPSTREAM_API_HTTP_{exc.code}")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            # Exception messages can include network details. No credentials or
            # arbitrary response body may enter an operator report.
            reasons.append(f"HOLD_UPSTREAM_API_UNVERIFIED:{type(exc).__name__}")
    result.update(status="HOLD" if reasons else "VERIFIED_CONTEXT_ONLY", upstream_head_sha=head)
    return result


def reconcile_bridge_input(repo: Path, reference_time=None) -> Dict[str, Any]:
    """Recover omitted triggers from exact original completion, or verify a no-op.

    Scheduling is just an opportunity to check a receipt. It never establishes
    completion, data freshness or model authority. Delayed native triggers keep
    their own run pins and cannot silently select a newer run.
    """
    marker = repo / "_runtime/1b_output_contract/start.marker"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    if (repo / '.git').exists():
        return receipt_custody().reconcile(repo, sys.modules.get(__name__) or _module_api(),
            reference_time or dt.datetime.now(dt.timezone.utc))
    result = verify_bridge_origin(repo, reference_time=reference_time)
    result["action"] = "HOLD"
    if result["reasons"]:
        return result
    previous_path = repo / "latest/1b_output_contract/verified_context_custody.json"
    previous = read_json(previous_path, None)
    if previous_path.exists() and not isinstance(previous, dict):
        result["reasons"].append("HOLD_PRIOR_CONSUMER_RECEIPT_INVALID")
    elif (isinstance(previous, dict) and previous.get("upstream_run_id") == result["upstream_run_id"]
          and previous.get("upstream_run_attempt") == result["upstream_run_attempt"]):
        verified = verify_bridge_output(repo, reference_time=reference_time)
        if verified["reasons"]:
            result["reasons"] += verified["reasons"]
        else:
            result["action"] = "NOOP_ALREADY_VERIFIED"
    else:
        result["action"] = "PROCESS"
    if result["reasons"]:
        result["status"] = "HOLD"
    return result


def _module_api():
    # importlib fixtures need not insert their loaded module into sys.modules.
    from types import SimpleNamespace
    return SimpleNamespace(**globals())


def receipt_custody():
    spec = importlib.util.spec_from_file_location('peak_receipt_custody', Path(__file__).with_name('f1_peak_receipt_custody_v1.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_plain_report(result: Dict[str, Any]) -> str:
    steps = result.get("steps", [])
    step_lines = [f"- `{s.get('label')}`: {'PASS' if s.get('ok') else 'FAIL'} (`{s.get('returncode')}`)" for s in steps]
    if not step_lines:
        step_lines = ["- None"]
    latest = result.get("latest_state", {})
    return "\n".join([
        "# F1 Peak-Elite Orchestrator Report",
        "",
        f"Created UTC: `{result.get('created_utc')}`",
        f"Operation: `{result.get('operation')}`",
        f"Status: **{result.get('status')}**",
        "",
        "## Latest source state",
        f"- Race/event: `{latest.get('race_name')}`",
        f"- Session: `{latest.get('session_name')}`",
        f"- Source status: `{latest.get('source_status')}`",
        f"- Workbook source status: `{latest.get('workbook_source_status')}`",
        f"- Workbook commit allowed: `{latest.get('workbook_commit_allowed')}`",
        "",
        "## Steps",
        *step_lines,
        "",
        "## Governance",
        "- Stable engine modified: `false`",
        "- Canonical workbook overwritten: `false`",
        "- Model promotion: `false`",
        "- 2026 no-DRS rule: active by project governance; this layer does not create DRS assumptions",
        "",
        "## Interpretation",
        result.get("plain_english", "No interpretation available."),
        "",
    ])


def latest_state(repo: Path) -> Dict[str, Any]:
    readiness = read_json(repo / "latest" / "data_readiness.json", {})
    workbook = read_json(repo / "latest" / "workbook_kpi_refresh_applier" / "workbook_kpi_refresh_manifest.json", {})
    session = readiness.get("session") if isinstance(readiness.get("session"), dict) else {}
    return {
        "race_name": readiness.get("race_name"),
        "event_id": readiness.get("event_id"),
        "session_name": session.get("session_name"),
        "session_key": session.get("session_key"),
        "source_status": readiness.get("overall_status") or readiness.get("overall_classification"),
        "source_needs_manual_review": bool(readiness.get("needs_manual_review", False)),
        "workbook_source_status": workbook.get("source_status"),
        "workbook_commit_allowed": bool(workbook.get("commit_allowed", False)),
        "workbook_artifacts": [o.get("path") for o in workbook.get("outputs", []) if isinstance(o, dict)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--operation", default="full_safe_chain", choices=["health_only", "syntax_repair_only", "full_safe_chain", "full_run_chain", "scheduled_monitor", "verify_bridge_input", "verify_bridge_output", "reconcile_bridge_input", "verify_bridge_origin"])
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--session-filter", default="auto")
    parser.add_argument("--run-forecast-gate", default="false")
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    if args.operation in {"reconcile_bridge_input", "verify_bridge_origin"}:
        function = reconcile_bridge_input if args.operation == "reconcile_bridge_input" else verify_bridge_origin
        verification = function(repo)
        write_json(repo / f"_runtime/1b_output_contract/{args.operation}.json", verification)
        if args.operation == "reconcile_bridge_input":
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write(f"action={verification['action']}\n")
            if os.environ.get("GITHUB_ENV") and verification.get("action") == "PROCESS":
                with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as output:
                    for field, name in (("upstream_run_id", "UPSTREAM_RUN_ID"),
                                        ("upstream_run_attempt", "UPSTREAM_RUN_ATTEMPT"),
                                        ("upstream_head_sha", "UPSTREAM_HEAD_SHA")):
                        output.write(f"{name}={verification[field]}\n")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
                output.write("## Context handoff reconciliation\n\n```json\n" + json.dumps(verification, indent=2) + "\n```\n")
        print(json.dumps(verification, sort_keys=True))
        return 2 if verification["status"] == "HOLD" else 0
    if args.operation in {"verify_bridge_input", "verify_bridge_output"}:
        verification = (verify_bridge_output if args.operation == "verify_bridge_output" else verify_bridge_input)(repo)
        write_json(repo / "_runtime/1b_output_contract/upstream_verification.json", verification)
        if args.operation == "verify_bridge_output" and verification["status"] != "HOLD":
            receipt_custody().append_receipt(repo, verification, consumer=True)
            write_json(repo / "latest/1b_output_contract/verified_context_custody.json", verification)
        print(json.dumps(verification, sort_keys=True))
        return 2 if verification["status"] == "HOLD" else 0
    runtime = repo / "_runtime" / "peak_elite" / "orchestrator"
    latest = repo / "latest" / "peak_elite"
    runtime.mkdir(parents=True, exist_ok=True)
    latest.mkdir(parents=True, exist_ok=True)
    steps: List[Dict[str, Any]] = []
    py = sys.executable

    operation = args.operation
    if operation in {"syntax_repair_only", "full_safe_chain", "full_run_chain", "scheduled_monitor"}:
        steps.append(run(repo, "workflow_commit_block_check", [py, "scripts/ops/f1_workflow_commit_block_repair_v1.py", "--repo-root", str(repo)], timeout=300))

    if operation in {"health_only", "syntax_repair_only", "full_safe_chain", "full_run_chain", "scheduled_monitor"}:
        steps.append(run(repo, "workflow_static_validation", [py, "scripts/ops/f1_workflow_static_validator_v2.py", "--repo-root", str(repo)], timeout=300))
        if (repo / "scripts/ops/f1_workflow_meta_health_check_v1.py").exists():
            steps.append(run(repo, "workflow_meta_health_v1", [py, "scripts/ops/f1_workflow_meta_health_check_v1.py"], timeout=300))

    if operation in {"health_only", "full_safe_chain", "full_run_chain", "scheduled_monitor"}:
        if (repo / "scripts/ops/f1_repo_canonicalization_v1.py").exists():
            canon_mode = "report_only"
            steps.append(run(repo, "repo_canonicalization_" + canon_mode, [py, "scripts/ops/f1_repo_canonicalization_v1.py", "--repo-root", str(repo), "--mode", canon_mode], timeout=600, allow_fail=(operation == "scheduled_monitor")))
        if (repo / "scripts/session_data_processor/source_readiness_classifier_v2.py").exists():
            steps.append(run(repo, "source_readiness_classifier_v2_self_test", [py, "scripts/session_data_processor/source_readiness_classifier_v2.py", "--self-test"], timeout=300, allow_fail=(operation == "scheduled_monitor")))

    if operation in {"full_safe_chain", "scheduled_monitor"}:
        steps.append(run(repo, "peak_elite_health_safe", [py, "scripts/ops/f1_peak_elite_health_v1.py", "--repo-root", str(repo), "--run-safe-tests", "true"], timeout=600, allow_fail=(operation == "scheduled_monitor")))

    if operation == "full_run_chain":
        steps.append(run(repo, "session_data_processor_run_now", [py, "scripts/session_data_processor/session_data_processor_loop_v1.py", "--mode", "run_now", "--season", str(args.season), "--session-filter", args.session_filter], timeout=1500, allow_fail=True))
        steps.append(run(repo, "workbook_kpi_refresh_apply", [py, "scripts/workbook_kpi_refresh/apply_workbook_kpi_refresh_v1.py", "--repo-root", str(repo)], timeout=900, allow_fail=True))
        steps.append(run(repo, "dashboard_readiness_publish", [py, "scripts/dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py", "--mode", "run_now"], timeout=600, allow_fail=True))
        if str(args.run_forecast_gate).lower() in {"true", "1", "yes"}:
            steps.append(run(repo, "forecast_gate_orchestrator", [py, "scripts/forecast_bundles/orchestrate_forecast_gate_pipeline_v1.py", "--mode", "auto", "--season", str(args.season), "--run-source-closure", "true"], timeout=1800, allow_fail=True))
        steps.append(run(repo, "peak_elite_health_after_run", [py, "scripts/ops/f1_peak_elite_health_v1.py", "--repo-root", str(repo), "--run-safe-tests", "true"], timeout=600, allow_fail=True))

    if operation == "health_only":
        steps.append(run(repo, "peak_elite_health_only", [py, "scripts/ops/f1_peak_elite_health_v1.py", "--repo-root", str(repo), "--run-safe-tests", "true"], timeout=600))

    if (repo / "scripts/ops/f1_peak_elite_cleanup_report_v1.py").exists() and operation in {"full_safe_chain", "full_run_chain", "health_only"}:
        steps.append(run(repo, "cleanup_inventory_report_only", [py, "scripts/ops/f1_peak_elite_cleanup_report_v1.py", "--repo-root", str(repo)], timeout=600, allow_fail=True))

    protected = protected_touched(repo)
    hard_failed = [s for s in steps if not s.get("ok") and not s.get("allow_fail")]
    soft_failed = [s for s in steps if not s.get("ok") and s.get("allow_fail")]
    state = latest_state(repo)
    dashboard = read_json(repo / "latest" / "readiness_dashboards" / "combined_readiness_dashboard.json", {})
    downstream_current = (
        dashboard.get("downstream_eligible") is True
        and dashboard.get("event_id") == state.get("event_id")
        and str(dashboard.get("session_key")) == str(state.get("session_key"))
        and dashboard.get("source_backed") is True
    )
    source_status = str(state.get("source_status") or "missing")
    workbook_status = str(state.get("workbook_source_status") or "missing")
    if protected:
        status = "fail"
        plain = "Protected stable engine or canonical workbook files appear modified. The run is blocked until reviewed."
    elif hard_failed:
        status = "fail"
        plain = "The orchestration layer failed before reaching production-ready state. Review the failed step tails in the runtime artifact."
    elif operation == "full_run_chain" and (soft_failed or not downstream_current):
        status = "hold_downstream_not_verified"
        plain = "The capture-to-dashboard chain did not complete and verify the current source session. Do not treat earlier green readiness as current."
    elif operation == "syntax_repair_only":
        status = "pass"
        plain = "Read-only workflow syntax checks completed. Any required code repair must be reviewed through a development PR."
    elif source_status in {"missing", "unknown", "", "None"}:
        status = "pass_with_warnings"
        plain = "Automation health is available, but latest source readiness is not populated. Watchers may be running before source data exists."
    elif "manual" in source_status.lower() or "partial" in source_status.lower() or "late" in source_status.lower():
        status = "pass_with_warnings"
        plain = "The processor produced source-backed artifacts, but readiness is not clean. Use as confidence/risk context, not automatic stable-prediction promotion."
    else:
        status = "pass"
        plain = "Workflow health, source readiness, and workbook/KPI handoff are aligned. Stable engine remains protected."

    result = {
        **execution_authority(operation, protected, hard_failed, soft_failed, downstream_current),
        "created_utc": iso_now(),
        "operation": operation,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "workflow_head_sha": os.environ.get("GITHUB_SHA"),
        "handoff_fingerprints": byte_fingerprints(repo, [
            "latest/latest_manifest.json", "latest/data_readiness.json", "latest/combined_source_manifest.json",
            "latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json",
            "latest/readiness_dashboards/combined_readiness_dashboard.json",
            *dashboard.get("consumed_fingerprints", {}).keys(),
        ]),
        "status": status,
        "plain_english": plain,
        "latest_state": state,
        "steps": steps,
        "failed_steps": [s.get("label") for s in hard_failed + soft_failed],
        "downstream_current": downstream_current,
        "dashboard_readiness_reasons": dashboard.get("readiness_reasons"),
        "protected_modified": protected,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "commit_allowed": False if protected or hard_failed else True,
    }
    write_json(runtime / "peak_elite_orchestrator_result.json", result)
    write_json(latest / "orchestrator_status.json", result)
    if (operation == "full_run_chain" and not result["failed_steps"] and not protected
            and os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_RUN_ATTEMPT")):
        receipt_custody().append_receipt(repo, result)
    report_md = build_plain_report(result)
    (runtime / "PEAK_ELITE_ORCHESTRATOR_REPORT.md").write_text(report_md, encoding="utf-8")
    (latest / "ORCHESTRATOR_STATUS.md").write_text(report_md, encoding="utf-8")
    chat_dir = repo / "latest" / "chat_context"
    chat_dir.mkdir(parents=True, exist_ok=True)
    (chat_dir / "PEAK_ELITE_ORCHESTRATOR_BRIEF.md").write_text(report_md, encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if status == "fail" or result["operational_execution"] == "OPERATIONAL_FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
