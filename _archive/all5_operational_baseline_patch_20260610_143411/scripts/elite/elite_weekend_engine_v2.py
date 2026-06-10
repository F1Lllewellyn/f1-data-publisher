#!/usr/bin/env python3
"""
Elite Weekend Engine v2 artifact consumer.

This is not a stub. It consumes the latest OpenF1 autopilot artifacts downloaded
by download_latest_openf1_artifacts.py and produces control-room outputs:
source readiness, reliability board, DNF_ALL precursor board, fantasy risk board,
model disagreement board, promotion gate, and locked ledger snapshot.

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
        "feature_rows": int(feature_rows or 0),
        "status": status,
    }


def write_df(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()

    input_root = Path(args.input_dir)
    out = Path(args.output_dir)
    for sub in ["reports", "metrics", "ledgers", "manifests", "validation"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    manifest_json = read_json(input_root / "manifests" / "elite_artifact_source_manifest.json")
    profile_rows = manifest_json.get("profiles", [])
    profile_by_name = {r.get("profile"): r for r in profile_rows}

    profiles = ["pre_race", "full_historical", "post_race"]
    summaries = []
    for profile in profiles:
        summaries.append(profile_summary(profile, input_root / "inputs" / profile, profile_by_name.get(profile, {})))

    readiness = pd.DataFrame(summaries)
    write_df(readiness, out / "metrics" / "source_readiness_board.csv")

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

    # Reliability board
    reliability_rows = []
    for s in summaries:
        reliability_rows.append({
            "source_profile": s["profile"],
            "artifact_status": s["status"],
            "selected_sessions": s["selected_sessions"],
            "high_frequency_rows": s["high_frequency_rows"],
            "feature_rows": s["feature_rows"],
            "reliability_signal_available": s["feature_rows"] > 0,
            "usage": "risk/fantasy/reporting only",
            "stable_rank_change_allowed": False,
        })
    reliability_board = pd.DataFrame(reliability_rows)
    write_df(reliability_board, out / "metrics" / "reliability_warning_board.csv")

    # DNF_ALL precursor board
    dnf_board = reliability_board.copy()
    dnf_board["target_policy"] = "DNF_ALL"
    dnf_board["visible_outcome_labels_are_metadata_only"] = True
    dnf_board["do_not_exclude_crash_contact_damage_without_searching_precursors"] = True
    write_df(dnf_board, out / "metrics" / "dnf_all_precursor_board.csv")

    # Fantasy risk board
    fantasy_board = reliability_board[["source_profile", "artifact_status", "feature_rows", "reliability_signal_available"]].copy()
    fantasy_board["fantasy_usage"] = fantasy_board["reliability_signal_available"].map(lambda x: "eligible_for_risk_flag_review" if x else "no_signal_available")
    fantasy_board["automatic_transfer_recommendation_allowed"] = False
    write_df(fantasy_board, out / "metrics" / "fantasy_risk_board.csv")

    # Model disagreement board
    disagreement = pd.DataFrame([{
        "model_family": "OpenF1 public/proxy reliability layer",
        "pre_race_status": pre.get("status", "MISSING"),
        "full_historical_status": full.get("status", "MISSING"),
        "post_race_status": post.get("status", "MISSING"),
        "disagreement_state": "postrace_zero_feature_warning" if post.get("status") == "PASS_WITH_WARNINGS" else "normal",
        "action": "review_before_consumption" if post.get("status") == "PASS_WITH_WARNINGS" else "available_for_control_room",
    }])
    write_df(disagreement, out / "metrics" / "model_disagreement_board.csv")

    # Promotion/demotion gate
    promotion_action = "NO_PROMOTION_HOLD_STABLE"
    if elite_status == "READY":
        promotion_action = "NO_PROMOTION_AUTOMATIC__AVAILABLE_FOR_REVIEW"
    elif elite_status == "READY_WITH_POSTRACE_SIGNAL_WARNING":
        promotion_action = "NO_PROMOTION__POSTRACE_SIGNAL_WARNING"

    promotion = pd.DataFrame([{
        "gate": "automatic_promotion_demotion_controller",
        "elite_status": elite_status,
        "promotion_action": promotion_action,
        "stable_race_p1_p20_change_allowed": False,
        "qualifying_p1_p5_change_allowed": False,
        "requires_human_review_for_forecast_consumption": True,
    }])
    write_df(promotion, out / "metrics" / "promotion_demotion_gate.csv")

    # Ledger snapshot
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
    }
    (out / "ledgers" / "locked_forecast_ledger_snapshot.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    write_df(pd.DataFrame(summaries), out / "manifests" / "elite_artifact_source_manifest.csv")

    # Report
    report_lines = [
        "# Elite Weekend Engine v2 Report",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Elite status: **{elite_status}**",
        "",
        "## Artifact source readiness",
        "",
        "| Profile | Artifact | Status | Sessions | High-frequency rows | Feature rows |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for s in summaries:
        report_lines.append(
            f"| {s['profile']} | {s['artifact_name']} | {s['status']} | {s['selected_sessions']} | {s['high_frequency_rows']} | {s['feature_rows']} |"
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
    (out / "reports" / "elite_weekend_engine_v2_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    validation = {
        "validation_status": "PASS" if elite_status != "NOT_READY" else "FAIL",
        "elite_status": elite_status,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "required_profiles": profiles,
        "profiles": summaries,
    }
    (out / "validation" / "elite_validation_summary.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    summary_lines = [
        "## Elite Weekend Engine v2 summary",
        "",
        f"- Elite status: {elite_status}",
        f"- Pre-race artifact: {pre.get('status', 'MISSING')}",
        f"- Full historical artifact: {full.get('status', 'MISSING')}",
        f"- Post-race artifact: {post.get('status', 'MISSING')}",
        "- Stable rank changes: disabled",
        "- Qualifying top-five changes: disabled",
        "",
    ]
    (out / "reports" / "github_step_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(json.dumps(validation, indent=2))

    if elite_status == "NOT_READY":
        raise SystemExit("Elite Weekend Engine v2 could not find enough validated OpenF1 artifacts.")


if __name__ == "__main__":
    main()
