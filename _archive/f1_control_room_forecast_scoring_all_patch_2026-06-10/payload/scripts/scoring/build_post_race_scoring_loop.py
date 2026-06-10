#!/usr/bin/env python3
"""
F1 Post-Race Scoring Loop Package Builder.

Builds a post-race scoring template and summary from latest Elite outputs.
Actual finishing order/results can be added later; this workflow seeds the
review surface and scorecard structure.
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
    for sub in ["reports", "scoring", "templates"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    policy = read_json(Path(args.policy))
    ledger = read_json(find_first(elite, "locked_forecast_ledger_snapshot.json"))
    reliability = read_csv(find_first(elite, "reliability_warning_board.csv"))
    dnf = read_csv(find_first(elite, "dnf_all_precursor_board.csv"))
    fantasy = read_csv(find_first(elite, "fantasy_risk_board.csv"))
    disagreement = read_csv(find_first(elite, "model_disagreement_board.csv"))
    promotion = read_csv(find_first(elite, "promotion_demotion_gate.csv"))

    elite_status = ledger.get("elite_status", "UNKNOWN")

    rows = []
    source_tables = [
        ("reliability", reliability),
        ("dnf_all", dnf),
        ("fantasy", fantasy),
        ("model_disagreement", disagreement),
        ("promotion_gate", promotion),
    ]
    for family, df in source_tables:
        if df is None or df.empty:
            rows.append({
                "race": "TBD",
                "date": "YYYY-MM-DD",
                "signal_family": family,
                "source_profile": "missing",
                "flagged_entity": "TBD",
                "actual_outcome": "TBD",
                "helped_decision": "",
                "false_positive": "",
                "missed_signal": "",
                "score": "",
                "promotion_candidate": False,
                "notes": "No source table found"
            })
            continue
        profiles = df["source_profile"].tolist() if "source_profile" in df.columns else ["aggregate"]
        for profile in profiles[:20]:
            rows.append({
                "race": "TBD",
                "date": "YYYY-MM-DD",
                "signal_family": family,
                "source_profile": profile,
                "flagged_entity": "TBD",
                "actual_outcome": "TBD",
                "helped_decision": "",
                "false_positive": "",
                "missed_signal": "",
                "score": "",
                "promotion_candidate": False,
                "notes": "Fill after race"
            })

    scorecard = pd.DataFrame(rows)
    write_df(scorecard, out / "scoring" / "post_race_signal_scorecard_template.csv")

    scoring_rules = pd.DataFrame([
        {"metric": "helped_decision", "score": policy.get("score_scale", {}).get("helped_decision", 1), "meaning": "Signal helped avoid risk or improve forecast context"},
        {"metric": "neutral", "score": policy.get("score_scale", {}).get("neutral", 0), "meaning": "Signal did not materially help or hurt"},
        {"metric": "false_positive", "score": policy.get("score_scale", {}).get("false_positive", -1), "meaning": "Signal created avoidable noise"},
        {"metric": "missed_signal", "score": policy.get("score_scale", {}).get("missed_signal", -1), "meaning": "Signal failed to flag relevant risk"},
    ])
    write_df(scoring_rules, out / "scoring" / "post_race_scoring_rules.csv")

    promotion_audit = pd.DataFrame([{
        "gate": "post_race_promotion_audit",
        "elite_status": elite_status,
        "automatic_promotion_allowed": False,
        "requires_review": True,
        "requires_locked_future_or_backtest_proof": True,
        "decision": "hold_stable_until_scored"
    }])
    write_df(promotion_audit, out / "scoring" / "post_race_promotion_audit.csv")

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "elite_status": elite_status,
        "rows_in_scorecard_template": len(scorecard),
        "automatic_promotion_allowed": False,
        "status": "PASS",
        "notes": "Template seeded. Fill actual outcomes after race and score signal value."
    }
    (out / "scoring" / "post_race_scoring_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# F1 Post-Race Scoring Loop",
        "",
        f"Generated UTC: {summary['generated_utc']}",
        f"Elite status: `{elite_status}`",
        "",
        "## Outputs",
        "",
        "- post_race_signal_scorecard_template.csv",
        "- post_race_scoring_rules.csv",
        "- post_race_promotion_audit.csv",
        "- post_race_scoring_summary.json",
        "",
        "## Rule",
        "",
        "No signal is promoted automatically. Promotion requires scored value plus locked future or backtest proof.",
        "",
    ]
    (out / "reports" / "post_race_scoring_loop_report.md").write_text("\n".join(report), encoding="utf-8")

    step = [
        "## F1 Post-Race Scoring Loop",
        "",
        f"- Elite status: `{elite_status}`",
        f"- Scorecard rows: `{len(scorecard)}`",
        "- Automatic promotion: `false`",
        "",
    ]
    (out / "reports" / "github_step_summary.md").write_text("\n".join(step), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
