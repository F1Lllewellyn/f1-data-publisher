#!/usr/bin/env python3
"""F1 1B downstream consumer handoff wiring v24.

Consumes the output-contract ledger/handoff layer and writes explicit,
machine-readable input contracts for Race Predictions, Fantasy Predictions,
and Race Reports.

Safety:
- Writes only latest/downstream_consumers and history/downstream_consumers.
- Reads latest/last_good_state, latest/forecast_bundle_ledger,
  latest/readiness_handoff, latest/material_change, and latest/1b_output_contract.
- Does not touch stable engine files, canonical workbooks, model promotion state,
  forecast gates, .git, or generated forecast/race-report outputs.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = "f1_1b_downstream_consumer_wiring_v24"
PROTECTED_MARKERS = ("Engine_2026-06-07_STABLE", "F1_2026_Prediction_Model_Data_Workbook")
CONSUMERS = ("race_predictions", "fantasy_predictions", "race_reports")


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(value: Any) -> str:
    if value is None:
        return "unknown"
    return str(value).strip().lower()


def safe_write_path(path: Path) -> None:
    parts = set(path.parts)
    if ".git" in parts:
        raise RuntimeError(f"Refusing to write inside .git: {path}")
    norm = path.as_posix()
    for marker in PROTECTED_MARKERS:
        if marker in norm:
            raise RuntimeError(f"Refusing to write protected path containing {marker}: {path}")


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_load_error": str(exc), "_path": path.as_posix()}
    return data if isinstance(data, dict) else {"value": data}


def write_json(path: Path, data: Dict[str, Any]) -> None:
    safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: List[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def sha256_json(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def get_nested(data: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def load_contract_inputs(root: Path) -> Dict[str, Any]:
    paths = {
        "bundle": root / "latest" / "forecast_bundle_ledger" / "latest_bundle_snapshot.json",
        "last_good": root / "latest" / "last_good_state.json",
        "material_change": root / "latest" / "material_change" / "material_change_report.json",
        "combined_handoff": root / "latest" / "readiness_handoff" / "combined_readiness_handoff.json",
        "output_contract": root / "latest" / "1b_output_contract" / "output_contract_report.json",
    }
    loaded = {name: load_json(path) for name, path in paths.items()}
    loaded["paths"] = {name: relpath(path, root) for name, path in paths.items()}
    return loaded


def clean_or_usable(status: Any) -> bool:
    return normalize(status) in {"clean", "usable", "usable_with_optional_context_gaps", "source_backed", "refresh_applied"}


def source_workbook_ok(bundle: Dict[str, Any], output_contract: Dict[str, Any]) -> Dict[str, Any]:
    source_status = get_nested(bundle, ["source", "status"], output_contract.get("source_status", "unknown"))
    workbook_status = get_nested(bundle, ["workbook", "status"], output_contract.get("workbook_source_status", "unknown"))
    readiness_quality = get_nested(bundle, ["source", "readiness_quality"], output_contract.get("readiness_quality", "unknown"))
    source_backed = boolish(bundle.get("source_backed")) or clean_or_usable(source_status)
    workbook_ready = boolish(bundle.get("workbook_ready")) or clean_or_usable(workbook_status)
    usable_quality = normalize(readiness_quality) == "usable_with_optional_context_gaps"
    return {
        "source_status": source_status,
        "workbook_source_status": workbook_status,
        "readiness_quality": readiness_quality,
        "source_backed": source_backed,
        "workbook_ready": workbook_ready,
        "usable_quality": usable_quality,
        "base_ready": bool(source_backed and workbook_ready and (clean_or_usable(source_status) or usable_quality)),
    }


def consumer_base_payload(root: Path, inputs: Dict[str, Any], consumer: str) -> Dict[str, Any]:
    bundle = inputs.get("bundle", {})
    handoff = inputs.get("combined_handoff", {})
    output_contract = inputs.get("output_contract", {})
    material = inputs.get("material_change", {})
    last_good = inputs.get("last_good", {})
    status = source_workbook_ok(bundle, output_contract)
    consumer_handoffs = handoff.get("handoffs") if isinstance(handoff.get("handoffs"), dict) else {}
    consumer_contract = consumer_handoffs.get(consumer, {}) if isinstance(consumer_handoffs.get(consumer, {}), dict) else {}
    event = bundle.get("event") or handoff.get("event") or last_good.get("event") or {}
    run_id = bundle.get("run_id") or last_good.get("run_id") or output_contract.get("run_id") or "unknown_run"
    signature = bundle.get("signature") or last_good.get("signature") or sha256_json({"event": event, "run_id": run_id})
    material_change_detected = boolish(material.get("material_change_detected"))
    notification_recommended = boolish(material.get("notification_recommended"))
    allowed_inputs = {
        "last_good_state": inputs.get("paths", {}).get("last_good"),
        "latest_bundle_snapshot": inputs.get("paths", {}).get("bundle"),
        "combined_readiness_handoff": inputs.get("paths", {}).get("combined_handoff"),
        "material_change_report": inputs.get("paths", {}).get("material_change"),
        "output_contract_report": inputs.get("paths", {}).get("output_contract"),
    }
    common = {
        "schema_version": SCHEMA_VERSION,
        "consumer": consumer,
        "generated_at_utc": utc_now_iso(),
        "event": event,
        "run_id": run_id,
        "source_status": status["source_status"],
        "workbook_source_status": status["workbook_source_status"],
        "readiness_quality": status["readiness_quality"],
        "source_backed": status["source_backed"],
        "workbook_ready": status["workbook_ready"],
        "material_change_detected": material_change_detected,
        "notification_recommended": notification_recommended,
        "bundle_signature": signature,
        "allowed_input_paths": allowed_inputs,
        "consumer_contract_from_output_layer": consumer_contract,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }
    return common


def build_consumer_payload(root: Path, inputs: Dict[str, Any], consumer: str) -> Dict[str, Any]:
    payload = consumer_base_payload(root, inputs, consumer)
    contract = payload.get("consumer_contract_from_output_layer", {})
    base_ready = bool(payload["source_backed"] and payload["workbook_ready"] and clean_or_usable(payload["source_status"]))
    if normalize(payload["readiness_quality"]) == "usable_with_optional_context_gaps" and payload["workbook_ready"]:
        base_ready = True

    if consumer == "race_predictions":
        ready = bool(base_ready and boolish(contract.get("ready_for_use", True)))
        payload.update({
            "consumer_readiness": "ready" if ready else "blocked",
            "ready_for_use": ready,
            "blocked": not ready,
            "default_output_rule": "exact P1-P20 prediction output may use this as readiness/confidence/risk context only; stable engine logic is not overwritten",
            "allowed_effect": "readiness, confidence, risk flags, and source-backed context",
            "disallowed_effect": "automatic promotion, stable logic change, or hidden model overwrite",
        })
    elif consumer == "fantasy_predictions":
        ready = bool(base_ready and boolish(contract.get("ready_for_use", True)))
        payload.update({
            "consumer_readiness": "ready" if ready else "blocked",
            "ready_for_use": ready,
            "blocked": not ready,
            "default_output_rule": "fantasy picks may use this as source-backed value/risk/readiness context only",
            "allowed_effect": "constructor/driver value, risk, chip, and transfer recommendation context",
            "disallowed_effect": "automatic transfer execution, chip activation, or budget assumption without current fantasy data",
        })
    elif consumer == "race_reports":
        context_ready = bool(base_ready and boolish(contract.get("ready_for_readiness_context", True)))
        full_report_ready = bool(context_ready and boolish(contract.get("ready_for_full_report", False)))
        payload.update({
            "consumer_readiness": "full_report_ready" if full_report_ready else ("context_ready" if context_ready else "blocked"),
            "ready_for_readiness_context": context_ready,
            "ready_for_full_report": full_report_ready,
            "blocked": not context_ready,
            "default_output_rule": "report layer may use this for source/readiness context; Full Report PDF only when session type supports it and user requests report output",
            "allowed_effect": "Race Reports source context and placemat/full-report readiness checks",
            "disallowed_effect": "automatic PDF generation or report publication",
        })
    else:
        raise ValueError(f"Unknown consumer: {consumer}")
    return payload


def write_outputs(root: Path, consumer_payloads: Dict[str, Dict[str, Any]], inputs: Dict[str, Any]) -> Dict[str, Any]:
    latest_root = root / "latest" / "downstream_consumers"
    bundle = inputs.get("bundle", {})
    event = bundle.get("event") or inputs.get("last_good", {}).get("event") or {}
    event_id = str(event.get("event_id") or "unknown_event").replace("/", "_").replace(" ", "_")
    run_id = str(bundle.get("run_id") or inputs.get("last_good", {}).get("run_id") or "unknown_run")
    history_root = root / "history" / "downstream_consumers" / event_id / run_id
    rows: List[Dict[str, Any]] = []
    for name, payload in consumer_payloads.items():
        write_json(latest_root / name / "consumer_input.json", payload)
        rows.append({
            "consumer": name,
            "consumer_readiness": payload.get("consumer_readiness"),
            "source_status": payload.get("source_status"),
            "workbook_source_status": payload.get("workbook_source_status"),
            "readiness_quality": payload.get("readiness_quality"),
            "material_change_detected": payload.get("material_change_detected"),
            "notification_recommended": payload.get("notification_recommended"),
            "promotion_allowed": payload.get("promotion_allowed"),
            "forecast_gate_activated": payload.get("forecast_gate_activated"),
        })
    combined = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "status": "pass" if any(p.get("consumer_readiness") != "blocked" for p in consumer_payloads.values()) else "blocked",
        "event": event,
        "run_id": run_id,
        "consumers": consumer_payloads,
        "source_paths": inputs.get("paths", {}),
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }
    write_json(latest_root / "combined_downstream_consumer_manifest.json", combined)
    write_csv(latest_root / "combined_downstream_consumer_manifest.csv", rows)
    write_json(history_root / "combined_downstream_consumer_manifest.json", combined)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": combined["status"],
        "generated_at_utc": combined["generated_at_utc"],
        "event": event,
        "run_id": run_id,
        "consumers_ready": {name: payload.get("consumer_readiness") for name, payload in consumer_payloads.items()},
        "outputs": {
            "combined_manifest": "latest/downstream_consumers/combined_downstream_consumer_manifest.json",
            "combined_csv": "latest/downstream_consumers/combined_downstream_consumer_manifest.csv",
            "race_predictions_input": "latest/downstream_consumers/race_predictions/consumer_input.json",
            "fantasy_predictions_input": "latest/downstream_consumers/fantasy_predictions/consumer_input.json",
            "race_reports_input": "latest/downstream_consumers/race_reports/consumer_input.json",
            "history_manifest": relpath(history_root / "combined_downstream_consumer_manifest.json", root),
        },
        "material_change_detected": boolish(inputs.get("material_change", {}).get("material_change_detected")),
        "notification_recommended": boolish(inputs.get("material_change", {}).get("notification_recommended")),
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
        "forecast_gate_activated": False,
    }
    write_json(latest_root / "downstream_consumer_wiring_report.json", report)
    return report


def run(repo_root: Path, mode: str = "run_now") -> Dict[str, Any]:
    inputs = load_contract_inputs(repo_root)
    payloads = {consumer: build_consumer_payload(repo_root, inputs, consumer) for consumer in CONSUMERS}
    return write_outputs(repo_root, payloads, inputs)


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
