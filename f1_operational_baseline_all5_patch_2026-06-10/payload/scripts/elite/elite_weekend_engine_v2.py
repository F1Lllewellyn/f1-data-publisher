#!/usr/bin/env python3
"""
Elite Weekend Engine v2 artifact consumer.

Consumes latest OpenF1 autopilot artifacts and produces control-room outputs,
workbook bridge exports, GitHub run summary, and locked ledger snapshot.

Guardrails:
- Public/proxy OpenF1 data only.
- Risk/fantasy/reporting only.
- No automatic qualifying P1-P5 reorder.
- No automatic stable race P1-P20 reorder.
- DNF_ALL broad precursor policy preserved.
- 2026 no-DRS rule preserved.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


def find_first(root: Path, pattern: str):
    hits = list(root.rglob(pattern))
    if not hits:
        return None
    hits.sort(key=lambda p: len(str(p)))
    return hits[0]


def read_json(path: Path) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def read_csv(path: Path) -> pd.DataFrame:
    if path and path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def profile_summary(profile: str, profile_dir: Path, artifact_row: dict) -> dict:
    checkpoint = read_json(find_first(profile_dir, "extraction_checkpoint_summary.json") or Path(""))
    manifest = read_csv(find_first(profile_dir, "high_frequency_extraction_manifest.csv") or Path(""))
    feature_manifest = read_csv(find_first(profile_dir, "feature_manifest.csv") or Path(""))
    sessions = read_csv(find_first(profile_dir, "completed_sessions_selected.csv") or Path(""))

    high_freq_rows = 0
    if not manifest.empty and "rows" in manifest.columns:
        high_freq_rows = int(pd.to_numeric(manifest["rows"], errors="coerce").fillna(0).sum())

    feature_rows = checkpoint.get("feature_rows", 0)
    if not feature_rows and not feature_manifest.empty and "rows_30s" in feature_manifest.columns:
        feature_rows = int(pd.to_numeric(feature_manifest["rows_30s"], errors="coerce").fillna(0).sum())

    found = bool(artifact_row.get("found", False))
    status = "MISSING"
    if found and high_freq_rows > 0 and feature_rows > 0:
        status = "PASS"
    elif found and high_freq_rows > 0 and feature_rows == 0:
        status = "PASS_WITH_WARNINGS"
    elif found:
        status = "FOUND_BUT_UNUSABLE"

    return {
        "profile": profile,
        "artifact_found": found,
        "artifact_name": artifact_row.get("artifact_name", ""),
        "artifact_id": artifact_row.get("artifact_id", ""),
        "updated_at": artifact_row.get("updated_at", ""),
        "checkpoint_status": checkpoint.get("status", ""),
        "selected_sessions": int(checkpoint.get("selected_session_count", len(sessions) if not sessions.empty else 0) or 0),
        "high_frequency_rows": high_freq_rows,
        "normal_feature_rows": int(checkpoint.get("normal_feature_rows", feature_rows) or 0),
        "fallback_feature_builder_used": bool(checkpoint.get("fallback_feature_builder_used", False)),
        "feature_rows": int(feature_rows or 0),
        "status": status,
    }


def write_df(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def copy_for_workbook(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        dst.write_bytes(src.read_bytes())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()

    input_root = Path(args.input_dir)
    out = Path(args.output_dir)
    for sub in ["reports", "metrics", "ledgers", "manifests", "validation", "workbook_exports"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    manifest_json = read_json(input_root / "manifests" / "elite_artifact_source_manifest.json")
    profile_rows = manifest_json.get("profiles", [])
    profile_by_name = {r.get("profile"): r for r in profile_rows}

    profiles = ["pre_race", "full_historical", "post_race"]
    summaries = [
        profile_summary(profile, input_root / "inputs" / profile, profile_by_name.get(profile, {}))
        for profile in profiles
    ]

    readiness = pd.DataFrame(summaries)
    source_readiness_path = out / "metrics" / "source_readiness_board.csv"
    write_df(readiness, source_readiness_path)

    pre = next((s for s in summaries if s["profile"] == "pre_race"), {})
    full = next((s for s in summaries if s["profile"] == "full_historical"), {})
    post = next((s for s in summaries if s["profile"] == "post_race"), {})

    if pre.get("status") == "PASS" and full.get("status") == "PASS":
        if post.get("status") == "PASS_WITH_WARNINGS":
            elite_status = "READY_WITH_POSTRACE_SIGNAL_WARNING"
        elif post.get("status") == "PASS":
            elite_status = "READY"
        else:
            elite_status = "READY_WITH_POSTRACE_ARTIFACT_MISSING"
    elif full.get("status") == "PASS":
        elite_status = "PARTIAL_READY_FULL_HISTORICAL_ONLY"
    elif pre.get("status") == "PASS":
        elite_status = "PARTIAL_READY_PRERACE_ONLY"
    else:
        elite_status = "NOT_READY"

    reliability_rows = []
    for s in summaries:
        reliability_rows.append({
            "source_profile": s["profile"],
            "artifact_status": s["status"],
            "selected_sessions": s["selected_sessions"],
            "high_frequency_rows": s["high_frequency_rows"],
            "normal_feature_rows": s["normal_feature_rows"],
            "fallback_feature_builder_used": s["fallback_feature_builder_used"],
            "feature_rows": s["feature_rows"],
            "reliability_signal_available": s["feature_rows"] > 0,
            "usage": "risk/fantasy/reporting only",
            "stable_rank_change_allowed": False,
        })
    reliability_board = pd.DataFrame(reliability_rows)
    reliability_path = out / "metrics" / "reliability_warning_board.csv"
    write_df(reliability_board, reliability_path)

    dnf_board = reliability_board.copy()
    dnf_board["target_policy"] = "DNF_ALL"
    dnf_board["visible_outcome_labels_are_metadata_only"] = True
    dnf_board["do_not_exclude_crash_contact_damage_without_searching_precursors"] = True
    dnf_path = out / "metrics" / "dnf_all_precursor_board.csv"
    write_df(dnf_board, dnf_path)

    fantasy_board = reliability_board[[
        "source_profile", "artifact_status", "feature_rows",
        "fallback_feature_builder_used", "reliability_signal_available"
    ]].copy()
    fantasy_board["fantasy_usage"] = fantasy_board["reliability_signal_available"].map(
        lambda x: "eligible_for_risk_flag_review" if x else "no_signal_available"
    )
    fantasy_board["automatic_transfer_recommendation_allowed"] = False
    fantasy_path = out / "metrics" / "fantasy_risk_board.csv"
    write_df(fantasy_board, fantasy_path)

    disagreement = pd.DataFrame([{
        "model_family": "OpenF1 public/proxy reliability layer",
        "pre_race_status": pre.get("status", "MISSING"),
        "full_historical_status": full.get("status", "MISSING"),
        "post_race_status": post.get("status", "MISSING"),
        "post_race_fallback_used": post.get("fallback_feature_builder_used", False),
        "disagreement_state": "postrace_zero_feature_warning" if post.get("status") == "PASS_WITH_WARNINGS" else "normal",
        "action": "review_before_consumption" if post.get("status") == "PASS_WITH_WARNINGS" else "available_for_control_room",
    }])
    disagreement_path = out / "metrics" / "model_disagreement_board.csv"
    write_df(disagreement, disagreement_path)

    if elite_status == "READY":
        promotion_action = "NO_PROMOTION_AUTOMATIC__AVAILABLE_FOR_REVIEW"
    elif elite_status == "READY_WITH_POSTRACE_SIGNAL_WARNING":
        promotion_action = "NO_PROMOTION__POSTRACE_SIGNAL_WARNING"
    else:
        promotion_action = "NO_PROMOTION_HOLD_STABLE"

    promotion = pd.DataFrame([{
        "gate": "automatic_promotion_demotion_controller",
        "elite_status": elite_status,
        "promotion_action": promotion_action,
        "stable_race_p1_p20_change_allowed": False,
        "qualifying_p1_p5_change_allowed": False,
        "requires_human_review_for_forecast_consumption": True,
    }])
    promotion_path = out / "metrics" / "promotion_demotion_gate.csv"
    write_df(promotion, promotion_path)

    ledger = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "engine_layer": "Elite Weekend Engine v2 Artifact Consumer",
        "elite_status": elite_status,
        "artifact_profiles": summaries,
        "guardrails": {
            "public_proxy_only": True,
            "stable_race_p1_p20_change_allowed": False,
            "qualifying_p1_p5_change_allowed": False,
            "dnf_all_broad_precursor_policy": True,
            "no_drs_2026_rule_preserved": True,
        },
        "next_forecast_cycle_state": {
            "pre_race_auto_ingest": pre.get("status", "MISSING"),
            "full_historical_auto_ingest": full.get("status", "MISSING"),
            "post_race_auto_reliability": post.get("status", "MISSING"),
            "recommended_action": "use_elite_outputs_for_control_room_review" if elite_status.startswith("READY") else "repair_sources_before_forecast_use",
        },
    }
    ledger_path = out / "ledgers" / "locked_forecast_ledger_snapshot.json"
    ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    write_df(pd.DataFrame(summaries), out / "manifests" / "elite_artifact_source_manifest.csv")

    # Workbook/control-room bridge exports
    workbook_dir = out / "workbook_exports"
    workbook_map = [
        (source_readiness_path, "F1_Source_Readiness_Board.csv", "Workbook source readiness import"),
        (reliability_path, "F1_Reliability_Warnings.csv", "Workbook reliability warnings import"),
        (dnf_path, "F1_DNF_ALL_Precursor_Board.csv", "Workbook DNF_ALL precursor import"),
        (fantasy_path, "F1_Fantasy_Risk_Board.csv", "Workbook fantasy risk import"),
        (disagreement_path, "F1_Model_Disagreement_Board.csv", "Workbook model disagreement import"),
        (promotion_path, "F1_Promotion_Gate.csv", "Workbook promotion/demotion gate import"),
        (ledger_path, "F1_Locked_Forecast_Ledger_Snapshot.json", "Workbook locked ledger sidecar"),
    ]
    bridge_rows = []
    for src, name, purpose in workbook_map:
        dst = workbook_dir / name
        copy_for_workbook(src, dst)
        bridge_rows.append({
            "workbook_export": name,
            "source_path": str(src.relative_to(out)),
            "export_path": str(dst.relative_to(out)),
            "purpose": purpose,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
        })
    write_df(pd.DataFrame(bridge_rows), workbook_dir / "workbook_bridge_manifest.csv")

    report_lines = [
        "# Elite Weekend Engine v2 Report",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Elite status: **{elite_status}**",
        "",
        "## Artifact source readiness",
        "",
        "| Profile | Artifact | Status | Sessions | High-frequency rows | Feature rows | Fallback used |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for s in summaries:
        report_lines.append(
            f"| {s['profile']} | {s['artifact_name']} | {s['status']} | {s['selected_sessions']} | {s['high_frequency_rows']} | {s['feature_rows']} | {s['fallback_feature_builder_used']} |"
        )
    report_lines += [
        "",
        "## Output boards generated",
        "",
        "- source_readiness_board.csv",
        "- reliability_warning_board.csv",
        "- dnf_all_precursor_board.csv",
        "- fantasy_risk_board.csv",
        "- model_disagreement_board.csv",
        "- promotion_demotion_gate.csv",
        "- locked_forecast_ledger_snapshot.json",
        "- workbook_exports/workbook_bridge_manifest.csv",
        "",
        "## Next forecast cycle",
        "",
        "Use Elite outputs for control-room review once the latest scheduled pre-race run completes. Do not manually rerun large OpenF1 extraction unless a workflow fails or a fresh full-history rebuild is explicitly needed.",
        "",
        "## Guardrails",
        "",
        "- This run consumes public/proxy OpenF1 artifacts only.",
        "- It does not automatically reorder stable race P1-P20 predictions.",
        "- It does not automatically reorder qualifying P1-P5 predictions.",
        "- Reliability outputs are risk/fantasy/reporting inputs only unless separately promoted.",
        "- DNF_ALL remains broad precursor search; visible DNF labels are metadata only.",
        "- 2026 no-DRS rule preserved.",
        "",
    ]
    report_path = out / "reports" / "elite_weekend_engine_v2_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    validation = {
        "validation_status": "PASS" if elite_status != "NOT_READY" else "FAIL",
        "elite_status": elite_status,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "required_profiles": profiles,
        "profiles": summaries,
        "workbook_bridge_exports": bridge_rows,
    }
    (out / "validation" / "elite_validation_summary.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    summary_lines = [
        "## Elite Weekend Engine v2 summary",
        "",
        f"**Elite status:** `{elite_status}`",
        "",
        "| Source | Status | Sessions | Rows | Features | Fallback |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in summaries:
        summary_lines.append(
            f"| {s['profile']} | {s['status']} | {s['selected_sessions']} | {s['high_frequency_rows']} | {s['feature_rows']} | {s['fallback_feature_builder_used']} |"
        )
    summary_lines += [
        "",
        f"**Promotion gate:** `{promotion_action}`",
        "",
        "- Stable race P1-P20 changes: disabled",
        "- Qualifying P1-P5 changes: disabled",
        "- Workbook bridge exports: generated",
        "",
        "### Next action",
        "",
        "Use the workbook bridge outputs for control-room review. Do not rerun the large OpenF1 full historical workflow unless explicitly needed.",
        "",
    ]
    (out / "reports" / "github_step_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(json.dumps(validation, indent=2))
    if elite_status == "NOT_READY":
        raise SystemExit("Elite Weekend Engine v2 could not find enough validated OpenF1 artifacts.")


if __name__ == "__main__":
    main()
