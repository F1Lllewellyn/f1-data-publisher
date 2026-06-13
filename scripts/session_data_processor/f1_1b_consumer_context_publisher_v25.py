#!/usr/bin/env python3
"""F1 1B consumer context publisher + trigger governor v25.

Consumes the v24 downstream consumer manifests and publishes read-only,
chat-ready context packs plus trigger/notification decisions.

Safety:
- Writes only latest/chat_context, latest/consumer_trigger_governor,
  latest/notification_routing, latest/downstream_consumers/*/consumer_bootstrap.json,
  and matching history folders.
- Does not run forecasts, generate reports, alter stable engine logic, overwrite
  canonical workbooks, activate forecast gates, or permit promotion.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "f1_1b_consumer_context_trigger_governor_v25"
CONSUMERS = ("race_predictions", "fantasy_predictions", "race_reports")
PROTECTED_MARKERS = ("Engine_2026-06-07_STABLE", "F1_2026_Prediction_Model_Data_Workbook")


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(value: Any) -> str:
    if value is None:
        return "unknown"
    return str(value).strip().lower()


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass", "ready", "clean"}


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_load_error": str(exc), "_path": path.as_posix()}
    return data if isinstance(data, dict) else {"value": data}


def safe_write_path(path: Path) -> None:
    parts = set(path.parts)
    if ".git" in parts:
        raise RuntimeError(f"Refusing to write inside .git: {path}")
    norm = path.as_posix()
    for marker in PROTECTED_MARKERS:
        if marker in norm:
            raise RuntimeError(f"Refusing to write protected path containing {marker}: {path}")


def write_text(path: Path, text: str) -> None:
    safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, data: Dict[str, Any]) -> None:
    safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def sha256_json(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def get_event(inputs: Dict[str, Any]) -> Dict[str, Any]:
    downstream = inputs.get("downstream", {})
    bundle = inputs.get("bundle", {})
    last_good = inputs.get("last_good", {})
    handoff = inputs.get("handoff", {})
    return first_dict(downstream.get("event"), bundle.get("event"), last_good.get("event"), handoff.get("event"))


def source_state(inputs: Dict[str, Any]) -> Dict[str, Any]:
    downstream = inputs.get("downstream", {})
    output = inputs.get("output_contract", {})
    bundle = inputs.get("bundle", {})
    source = first_dict(bundle.get("source"))
    workbook = first_dict(bundle.get("workbook"))
    source_status = downstream.get("source_status") or output.get("source_status") or source.get("status") or "unknown"
    workbook_status = downstream.get("workbook_source_status") or output.get("workbook_source_status") or workbook.get("status") or "unknown"
    readiness_quality = downstream.get("readiness_quality") or output.get("readiness_quality") or source.get("readiness_quality") or "unknown"
    source_clean = normalize(source_status) == "clean" or normalize(readiness_quality) == "usable_with_optional_context_gaps"
    workbook_clean = normalize(workbook_status) == "clean" or boolish(bundle.get("workbook_ready"))
    return {
        "source_status": source_status,
        "workbook_source_status": workbook_status,
        "readiness_quality": readiness_quality,
        "source_clean_or_usable": bool(source_clean),
        "workbook_clean_or_usable": bool(workbook_clean),
        "source_backed": boolish(bundle.get("source_backed")) or source_clean,
        "workbook_ready": boolish(bundle.get("workbook_ready")) or workbook_clean,
    }


def load_inputs(root: Path) -> Dict[str, Any]:
    paths = {
        "downstream": root / "latest" / "downstream_consumers" / "combined_downstream_consumer_manifest.json",
        "race_predictions": root / "latest" / "downstream_consumers" / "race_predictions" / "consumer_input.json",
        "fantasy_predictions": root / "latest" / "downstream_consumers" / "fantasy_predictions" / "consumer_input.json",
        "race_reports": root / "latest" / "downstream_consumers" / "race_reports" / "consumer_input.json",
        "bundle": root / "latest" / "forecast_bundle_ledger" / "latest_bundle_snapshot.json",
        "last_good": root / "latest" / "last_good_state.json",
        "material_change": root / "latest" / "material_change" / "material_change_report.json",
        "handoff": root / "latest" / "readiness_handoff" / "combined_readiness_handoff.json",
        "output_contract": root / "latest" / "1b_output_contract" / "output_contract_report.json",
    }
    data = {name: load_json(path) for name, path in paths.items()}
    data["paths"] = {name: relpath(path, root) for name, path in paths.items()}
    return data


def consumer_input(inputs: Dict[str, Any], consumer: str) -> Dict[str, Any]:
    direct = inputs.get(consumer, {})
    downstream = inputs.get("downstream", {})
    from_combined = first_dict(first_dict(downstream.get("consumers")).get(consumer))
    return direct if direct else from_combined


def is_consumer_ready(consumer: str, payload: Dict[str, Any]) -> bool:
    readiness = normalize(payload.get("consumer_readiness"))
    if consumer in {"race_predictions", "fantasy_predictions"}:
        return readiness == "ready" or boolish(payload.get("ready_for_use"))
    if consumer == "race_reports":
        return readiness in {"context_ready", "full_report_ready"} or boolish(payload.get("ready_for_readiness_context"))
    return False


def consumer_status_label(consumer: str, payload: Dict[str, Any]) -> str:
    label = payload.get("consumer_readiness")
    if label:
        return str(label)
    return "ready" if is_consumer_ready(consumer, payload) else "blocked"


def consumer_goal(consumer: str) -> str:
    if consumer == "race_predictions":
        return "Exact P1-P20 prediction context, confidence/risk flags, source-readiness proof."
    if consumer == "fantasy_predictions":
        return "Fantasy picks, constructor/value/risk context, chip/transfer readiness proof."
    return "Race Reports source context; Full Report only when post-race/result state supports it."


def make_context_markdown(consumer: str, payload: Dict[str, Any], inputs: Dict[str, Any], trigger: Dict[str, Any]) -> str:
    event = get_event(inputs)
    state = source_state(inputs)
    material = inputs.get("material_change", {})
    run_id = inputs.get("downstream", {}).get("run_id") or inputs.get("bundle", {}).get("run_id") or inputs.get("last_good", {}).get("run_id") or "unknown_run"
    title = {
        "race_predictions": "Race Predictions Context",
        "fantasy_predictions": "Fantasy Predictions Context",
        "race_reports": "Race Reports Context",
    }[consumer]
    readiness = consumer_status_label(consumer, payload)
    lines = [
        f"# F1 1B {title} v25",
        "",
        "## Confirmed Data",
        f"- Event: {event.get('race_name') or event.get('event_id') or 'unknown'}",
        f"- Session: {event.get('session_name') or 'unknown'} / key {event.get('session_key') or 'unknown'}",
        f"- Run ID: {run_id}",
        f"- Consumer readiness: {readiness}",
        f"- Source status: {state['source_status']}",
        f"- Workbook source status: {state['workbook_source_status']}",
        f"- Readiness quality: {state['readiness_quality']}",
        f"- Material change detected: {boolish(material.get('material_change_detected'))}",
        f"- Notification recommended: {boolish(material.get('notification_recommended'))}",
        "- Forecast gate: off",
        "- Promotion allowed: false",
        "- Stable engine modified: false",
        "- Canonical workbook overwrite: false",
        "",
        "## How This Context May Be Used",
        f"- {consumer_goal(consumer)}",
        f"- Trigger action: {trigger.get('action')}",
        f"- Trigger reason: {trigger.get('reason')}",
        "",
        "## Boundaries",
        "- Do not promote experimental logic from this context alone.",
        "- Do not overwrite Engine_2026-06-07_STABLE.",
        "- Do not overwrite the canonical workbook.",
        "- Do not activate forecast gate from this package.",
        "",
        "## Open Questions",
        "- Are newer session gates available after this run?",
        "- Are there critical source conflicts not represented in the current handoff?",
        "- Does the downstream lane need a human-readable prediction/report output now, or should it stay quiet?",
        "",
        "## Source Files",
    ]
    paths = inputs.get("paths", {})
    for name in ("downstream", consumer, "bundle", "last_good", "material_change", "handoff", "output_contract"):
        if paths.get(name):
            lines.append(f"- {name}: `{paths[name]}`")
    return "\n".join(lines)


def build_trigger_decisions(inputs: Dict[str, Any]) -> Dict[str, Any]:
    state = source_state(inputs)
    material = inputs.get("material_change", {})
    material_change = boolish(material.get("material_change_detected"))
    notification_recommended = boolish(material.get("notification_recommended"))
    safety_issue = not (state["source_clean_or_usable"] and state["workbook_clean_or_usable"])
    consumer_decisions: Dict[str, Dict[str, Any]] = {}
    for consumer in CONSUMERS:
        payload = consumer_input(inputs, consumer)
        ready = is_consumer_ready(consumer, payload) and not safety_issue
        if not ready:
            action = "blocked"
            reason = "consumer not ready or source/workbook state is not clean/usable"
        elif material_change or notification_recommended:
            action = "notify_and_update_context"
            reason = "material readiness or forecast-relevant state changed"
        else:
            action = "update_context_quiet"
            reason = "ready state unchanged; no notification needed"
        consumer_decisions[consumer] = {
            "consumer": consumer,
            "ready": bool(ready),
            "consumer_readiness": consumer_status_label(consumer, payload),
            "action": action,
            "reason": reason,
            "material_change_detected": material_change,
            "notification_recommended": notification_recommended,
            "promotion_allowed": False,
            "forecast_gate_activated": False,
        }
    should_notify = any(d["action"] == "notify_and_update_context" for d in consumer_decisions.values())
    blocked_consumers = [name for name, d in consumer_decisions.items() if d["action"] == "blocked"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "status": "blocked" if len(blocked_consumers) == len(CONSUMERS) else "pass",
        "decision_mode": "decision_only_no_external_send",
        "should_notify": bool(should_notify),
        "notification_recommended": bool(should_notify),
        "blocked_consumers": blocked_consumers,
        "consumer_decisions": consumer_decisions,
        "source_status": state["source_status"],
        "workbook_source_status": state["workbook_source_status"],
        "readiness_quality": state["readiness_quality"],
        "material_change_detected": material_change,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }


def build_notification_decision(inputs: Dict[str, Any], trigger: Dict[str, Any]) -> Dict[str, Any]:
    event = get_event(inputs)
    reasons: List[str] = []
    if trigger.get("material_change_detected"):
        reasons.append("material_change_detected")
    if trigger.get("should_notify"):
        reasons.append("consumer_trigger_recommends_notification")
    for name in trigger.get("blocked_consumers", []):
        reasons.append(f"{name}_blocked")
    notify = bool(trigger.get("should_notify"))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "decision_mode": "decision_only_no_external_send",
        "notification_recommended": notify,
        "send_external_notification": False,
        "event": event,
        "reasons": reasons,
        "routes": {
            "race_predictions_context": "latest/chat_context/race_predictions_context.md",
            "fantasy_predictions_context": "latest/chat_context/fantasy_predictions_context.md",
            "race_reports_context": "latest/chat_context/race_reports_context.md",
            "trigger_decision": "latest/consumer_trigger_governor/trigger_decision.json",
        },
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }


def notification_summary_md(decision: Dict[str, Any], trigger: Dict[str, Any]) -> str:
    event = decision.get("event", {}) if isinstance(decision.get("event"), dict) else {}
    lines = [
        "# F1 1B Notification Routing Summary v25",
        "",
        "## Decision",
        f"- Notification recommended: {decision.get('notification_recommended')}",
        "- External notification sent: false",
        "- Mode: decision-only; no ChatGPT automation, email, text, or forecast gate was activated.",
        "",
        "## Event",
        f"- Event: {event.get('race_name') or event.get('event_id') or 'unknown'}",
        f"- Session: {event.get('session_name') or 'unknown'}",
        "",
        "## Consumer Actions",
    ]
    for name, d in first_dict(trigger.get("consumer_decisions")).items():
        lines.append(f"- {name}: {d.get('action')} — {d.get('reason')}")
    lines += [
        "",
        "## Safety Locks",
        "- Forecast gate: off",
        "- Promotion allowed: false",
        "- Stable engine modified: false",
        "- Canonical workbook overwrite: false",
    ]
    return "\n".join(lines)


def build_bootstrap(consumer: str, payload: Dict[str, Any], context_path: str, trigger: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "consumer": consumer,
        "generated_at_utc": utc_now_iso(),
        "read_only": True,
        "ready": bool(trigger.get("ready")),
        "consumer_readiness": trigger.get("consumer_readiness"),
        "action": trigger.get("action"),
        "reason": trigger.get("reason"),
        "context_path": context_path,
        "input_manifest_path": f"latest/downstream_consumers/{consumer}/consumer_input.json",
        "allowed_input_paths": payload.get("allowed_input_paths", {}),
        "allowed_effect": payload.get("allowed_effect", "read-only context only"),
        "disallowed_effect": payload.get("disallowed_effect", "no forecast gate, no promotion, no stable-engine/workbook modification"),
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }


def write_outputs(root: Path, inputs: Dict[str, Any]) -> Dict[str, Any]:
    trigger = build_trigger_decisions(inputs)
    notification = build_notification_decision(inputs, trigger)
    event = get_event(inputs)
    downstream = inputs.get("downstream", {})
    bundle = inputs.get("bundle", {})
    run_id = downstream.get("run_id") or bundle.get("run_id") or inputs.get("last_good", {}).get("run_id") or "unknown_run"
    event_id = str(event.get("event_id") or "unknown_event").replace("/", "_").replace(" ", "_")
    latest_context = root / "latest" / "chat_context"
    latest_governor = root / "latest" / "consumer_trigger_governor"
    latest_notify = root / "latest" / "notification_routing"
    history_context = root / "history" / "chat_context" / event_id / str(run_id)
    history_governor = root / "history" / "consumer_trigger_governor" / event_id / str(run_id)
    history_notify = root / "history" / "notification_routing" / event_id / str(run_id)

    context_paths: Dict[str, str] = {}
    for consumer in CONSUMERS:
        payload = consumer_input(inputs, consumer)
        decision = first_dict(trigger.get("consumer_decisions", {})).get(consumer, {})
        md = make_context_markdown(consumer, payload, inputs, decision)
        filename = f"{consumer}_context.md"
        write_text(latest_context / filename, md)
        write_text(history_context / filename, md)
        context_path = f"latest/chat_context/{filename}"
        context_paths[consumer] = context_path
        bootstrap = build_bootstrap(consumer, payload, context_path, decision, inputs)
        write_json(root / "latest" / "downstream_consumers" / consumer / "consumer_bootstrap.json", bootstrap)
        write_json(root / "history" / "downstream_consumers" / event_id / str(run_id) / consumer / "consumer_bootstrap.json", bootstrap)

    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "event": event,
        "run_id": run_id,
        "context_paths": context_paths,
        "trigger_decision_path": "latest/consumer_trigger_governor/trigger_decision.json",
        "notification_decision_path": "latest/notification_routing/notification_decision.json",
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }
    write_json(latest_context / "combined_context_index.json", index)
    write_json(history_context / "combined_context_index.json", index)

    trigger["event"] = event
    trigger["run_id"] = run_id
    trigger["context_paths"] = context_paths
    trigger["signature"] = sha256_json({"event": event, "run_id": run_id, "trigger": trigger.get("consumer_decisions"), "contexts": context_paths})
    write_json(latest_governor / "trigger_decision.json", trigger)
    write_json(latest_governor / "consumer_trigger_report.json", trigger)
    write_json(history_governor / "trigger_decision.json", trigger)
    write_json(history_governor / "consumer_trigger_report.json", trigger)

    write_json(latest_notify / "notification_decision.json", notification)
    write_text(latest_notify / "notification_summary.md", notification_summary_md(notification, trigger))
    write_json(history_notify / "notification_decision.json", notification)
    write_text(history_notify / "notification_summary.md", notification_summary_md(notification, trigger))

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": trigger.get("status"),
        "generated_at_utc": utc_now_iso(),
        "event": event,
        "run_id": run_id,
        "outputs": {
            "chat_context_index": "latest/chat_context/combined_context_index.json",
            "trigger_decision": "latest/consumer_trigger_governor/trigger_decision.json",
            "notification_decision": "latest/notification_routing/notification_decision.json",
            "notification_summary": "latest/notification_routing/notification_summary.md",
        },
        "should_notify": trigger.get("should_notify"),
        "notification_recommended": notification.get("notification_recommended"),
        "consumer_actions": {name: d.get("action") for name, d in first_dict(trigger.get("consumer_decisions")).items()},
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }
    write_json(latest_governor / "consumer_context_publisher_report.json", report)
    return report


def run(repo_root: Path, mode: str = "run_now") -> Dict[str, Any]:
    inputs = load_inputs(repo_root)
    return write_outputs(repo_root, inputs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", default="run_now", choices=["run_now", "safe_test"])
    args = parser.parse_args()
    report = run(Path(args.repo_root).resolve(), mode=args.mode)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
