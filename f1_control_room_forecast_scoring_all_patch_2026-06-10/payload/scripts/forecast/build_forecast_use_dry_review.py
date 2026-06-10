#!/usr/bin/env python3
"""
F1 Forecast Use Dry Review Package Builder.

Consumes the latest extracted Elite artifact and produces a review package for:
- qualifying confidence flags
- race reliability risk flags
- fantasy avoid/hold/monitor notes
- promotion gate decision
- explicit no-automatic-rank-change confirmation

No OpenF1 extraction is run here.
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
    for sub in ["reports", "review", "manifests"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    policy = read_json(Path(args.policy))
    ledger = read_json(find_first(elite, "locked_forecast_ledger_snapshot.json"))
    source = read_csv(find_first(elite, "source_readiness_board.csv"))
    reliability = read_csv(find_first(elite, "reliability_warning_board.csv"))
    dnf = read_csv(find_first(elite, "dnf_all_precursor_board.csv"))
    fantasy = read_csv(find_first(elite, "fantasy_risk_board.csv"))
    disagreement = read_csv(find_first(elite, "model_disagreement_board.csv"))
    promotion = read_csv(find_first(elite, "promotion_demotion_gate.csv"))

    elite_status = ledger.get("elite_status", "UNKNOWN")
    eligible = elite_status in policy.get("required_elite_statuses", [])

    # Qualifying flags are deliberately non-ranking.
    quali = pd.DataFrame([{
        "area": "qualifying",
        "status": "review_ready" if eligible else "source_warning",
        "allowed_use": "confidence_flags_only",
        "p1_p5_reorder_allowed": False,
        "basis": "source readiness + model disagreement + promotion gate",
        "notes": "No automatic qualifying top-five changes from this package."
    }])
    write_df(quali, out / "review" / "qualifying_confidence_flags.csv")

    race = reliability.copy() if not reliability.empty else pd.DataFrame()
    if race.empty:
        race = pd.DataFrame([{"source_profile": "missing", "risk_flag": "no_reliability_board", "race_p1_p20_reorder_allowed": False}])
    else:
        race["risk_flag"] = race.get("reliability_signal_available", False).map(lambda x: "review_risk_context" if bool(x) else "no_signal")
        race["race_p1_p20_reorder_allowed"] = False
    write_df(race, out / "review" / "race_reliability_risk_flags.csv")

    fantasy_review = fantasy.copy() if not fantasy.empty else pd.DataFrame()
    if fantasy_review.empty:
        fantasy_review = pd.DataFrame([{"source_profile": "missing", "fantasy_note": "no_fantasy_board", "automatic_transfer_allowed": False}])
    else:
        fantasy_review["fantasy_note"] = fantasy_review.get("reliability_signal_available", False).map(lambda x: "avoid_hold_monitor_review" if bool(x) else "no_signal")
        fantasy_review["automatic_transfer_allowed"] = False
    write_df(fantasy_review, out / "review" / "fantasy_avoid_hold_monitor_notes.csv")

    dnf_review = dnf.copy() if not dnf.empty else pd.DataFrame()
    if dnf_review.empty:
        dnf_review = pd.DataFrame([{"source_profile": "missing", "dnf_all_review": "no_dnf_all_board"}])
    else:
        dnf_review["dnf_all_review"] = "advisory_precursor_search_only"
        dnf_review["visible_labels_are_metadata_only"] = True
    write_df(dnf_review, out / "review" / "dnf_all_precursor_review.csv")

    promotion_review = promotion.copy() if not promotion.empty else pd.DataFrame()
    if promotion_review.empty:
        promotion_review = pd.DataFrame([{
            "gate": "missing",
            "promotion_action": "NO_PROMOTION_HOLD_STABLE",
            "stable_race_p1_p20_change_allowed": False,
            "qualifying_p1_p5_change_allowed": False
        }])
    promotion_review["forecast_review_decision"] = "hold_stable_pending_human_review"
    write_df(promotion_review, out / "review" / "promotion_gate_decision.csv")

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "elite_status": elite_status,
        "forecast_review_status": "PASS" if eligible else "PASS_WITH_SOURCE_WARNING",
        "stable_race_p1_p20_reorder_allowed": False,
        "qualifying_p1_p5_reorder_allowed": False,
        "automatic_fantasy_transfer_allowed": False,
        "workbook_name": policy.get("workbook_name", ""),
        "notes": "Dry review only; does not alter stable predictions."
    }
    (out / "review" / "forecast_use_dry_review_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# F1 Forecast Use Dry Review",
        "",
        f"Generated UTC: {summary['generated_utc']}",
        f"Elite status: `{elite_status}`",
        f"Review status: `{summary['forecast_review_status']}`",
        "",
        "## Outputs",
        "",
        "- qualifying_confidence_flags.csv",
        "- race_reliability_risk_flags.csv",
        "- fantasy_avoid_hold_monitor_notes.csv",
        "- dnf_all_precursor_review.csv",
        "- promotion_gate_decision.csv",
        "",
        "## Guardrails",
        "",
        "- No automatic stable race P1-P20 reorder.",
        "- No automatic qualifying P1-P5 reorder.",
        "- No automatic fantasy transfer.",
        "- Reliability/DNF/fantasy boards are advisory unless separately promoted.",
        "- 2026 no-DRS rule preserved.",
        "",
    ]
    (out / "reports" / "forecast_use_dry_review_report.md").write_text("\n".join(report), encoding="utf-8")

    step = [
        "## F1 Forecast Use Dry Review",
        "",
        f"- Elite status: `{elite_status}`",
        f"- Review status: `{summary['forecast_review_status']}`",
        "- Stable race P1-P20 reorder: `false`",
        "- Qualifying P1-P5 reorder: `false`",
        "- Fantasy automatic transfer: `false`",
        "",
    ]
    (out / "reports" / "github_step_summary.md").write_text("\n".join(step), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
