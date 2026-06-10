#!/usr/bin/env python3
"""
Build a dry forecast cycle package from Elite Weekend Engine v2 outputs.

This is a forecast-consumption dry run only. It does not reorder race P1-P20,
qualifying P1-P5, or make automatic fantasy transfers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd


def find_first(root: Path, pattern: str) -> Path | None:
    hits = list(root.rglob(pattern))
    if not hits:
        return None
    hits.sort(key=lambda p: len(str(p)))
    return hits[0]


def read_csv(path: Path | None) -> pd.DataFrame:
    if path and path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def read_json(path: Path | None) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def write_df(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--elite-artifact-dir", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()

    elite = Path(args.elite_artifact_dir)
    out = Path(args.output_dir)
    for sub in ["reports", "metrics", "forecast_package"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    policy = read_json(Path(args.policy))
    readiness = read_csv(find_first(elite, "source_readiness_board.csv"))
    reliability = read_csv(find_first(elite, "reliability_warning_board.csv"))
    dnf = read_csv(find_first(elite, "dnf_all_precursor_board.csv"))
    fantasy = read_csv(find_first(elite, "fantasy_risk_board.csv"))
    disagreement = read_csv(find_first(elite, "model_disagreement_board.csv"))
    promotion = read_csv(find_first(elite, "promotion_demotion_gate.csv"))
    ledger = read_json(find_first(elite, "locked_forecast_ledger_snapshot.json"))

    elite_status = ledger.get("elite_status", "UNKNOWN")
    allowed_statuses = policy.get("source_requirements", {}).get("elite_status_required_for_forecast_use", [])

    forecast_eligible = elite_status in allowed_statuses

    decisions = []
    decisions.append({
        "area": "source_readiness",
        "decision": "eligible_input" if forecast_eligible else "do_not_consume",
        "reason": f"elite_status={elite_status}",
        "automatic_rank_change_allowed": False
    })
    decisions.append({
        "area": "reliability",
        "decision": "confidence_and_risk_flags_only",
        "reason": "reliability board may inform risk flags; no stable rank reorder",
        "automatic_rank_change_allowed": False
    })
    decisions.append({
        "area": "dnf_all_precursor",
        "decision": "advisory_precursor_search_only",
        "reason": "DNF_ALL labels are metadata; precursor search remains broad",
        "automatic_rank_change_allowed": False
    })
    decisions.append({
        "area": "fantasy",
        "decision": "avoid_hold_monitor_flags_only",
        "reason": "no automatic transfer recommendation from signal alone",
        "automatic_rank_change_allowed": False
    })
    decisions.append({
        "area": "promotion_gate",
        "decision": "hold_stable_pending_review",
        "reason": "promotion requires audit/backtest/locked future proof",
        "automatic_rank_change_allowed": False
    })

    decision_df = pd.DataFrame(decisions)
    write_df(decision_df, out / "metrics" / "forecast_consumption_decision_board.csv")

    q_df = pd.DataFrame([{
        "forecast_area": "qualifying",
        "output": "confidence_adjustment_only",
        "p1_p5_reorder_allowed": False,
        "reason": "Elite v2 boards do not automatically alter qualifying top five."
    }])
    write_df(q_df, out / "forecast_package" / "qualifying_confidence_adjustments.csv")

    race_df = reliability.copy() if not reliability.empty else pd.DataFrame()
    if not race_df.empty:
        race_df["forecast_usage"] = race_df["reliability_signal_available"].map(lambda x: "risk_flag_review" if bool(x) else "no_signal")
        race_df["race_p1_p20_reorder_allowed"] = False
    else:
        race_df = pd.DataFrame([{
            "forecast_usage": "no_reliability_board_found",
            "race_p1_p20_reorder_allowed": False
        }])
    write_df(race_df, out / "forecast_package" / "race_reliability_risk_flags.csv")

    fantasy_df = fantasy.copy() if not fantasy.empty else pd.DataFrame()
    if not fantasy_df.empty:
        fantasy_df["dry_forecast_action"] = fantasy_df["reliability_signal_available"].map(lambda x: "monitor_risk" if bool(x) else "no_signal")
        fantasy_df["automatic_transfer_allowed"] = False
    else:
        fantasy_df = pd.DataFrame([{
            "dry_forecast_action": "no_fantasy_board_found",
            "automatic_transfer_allowed": False
        }])
    write_df(fantasy_df, out / "forecast_package" / "fantasy_risk_value_notes.csv")

    promotion_review = promotion.copy() if not promotion.empty else pd.DataFrame([{
        "gate": "promotion_gate_missing",
        "promotion_action": "NO_PROMOTION_HOLD_STABLE"
    }])
    promotion_review["dry_forecast_decision"] = "hold_stable"
    write_df(promotion_review, out / "forecast_package" / "promotion_gate_review.csv")

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "elite_status": elite_status,
        "forecast_eligible": forecast_eligible,
        "stable_race_p1_p20_reorder_allowed": False,
        "qualifying_p1_p5_reorder_allowed": False,
        "automatic_fantasy_transfer_allowed": False,
        "dry_run_status": "PASS" if forecast_eligible else "PASS_WITH_SOURCE_WARNING",
    }
    (out / "forecast_package" / "forecast_dry_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# F1 Dry Forecast Cycle Report",
        "",
        f"Generated UTC: {summary['generated_utc']}",
        f"Elite status: `{elite_status}`",
        f"Dry run status: `{summary['dry_run_status']}`",
        "",
        "## Decisions",
        "",
        "| Area | Decision | Automatic rank change allowed |",
        "|---|---|---:|",
    ]
    for row in decisions:
        report.append(f"| {row['area']} | {row['decision']} | {row['automatic_rank_change_allowed']} |")
    report += [
        "",
        "## Guardrails",
        "",
        "- No automatic stable race P1-P20 reorder.",
        "- No automatic qualifying P1-P5 reorder.",
        "- No automatic fantasy transfer.",
        "- Reliability/DNF/fantasy boards are advisory until separately promoted.",
        "- 2026 no-DRS rule preserved.",
        "",
    ]
    (out / "reports" / "dry_forecast_cycle_report.md").write_text("\n".join(report), encoding="utf-8")

    step_summary = [
        "## F1 Dry Forecast Cycle",
        "",
        f"- Elite status: `{elite_status}`",
        f"- Dry run status: `{summary['dry_run_status']}`",
        "- Race rank changes: disabled",
        "- Qualifying top-five changes: disabled",
        "- Fantasy automatic transfers: disabled",
        "",
    ]
    (out / "reports" / "github_step_summary.md").write_text("\n".join(step_summary), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
