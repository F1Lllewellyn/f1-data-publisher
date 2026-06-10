#!/usr/bin/env python3
"""
OpenF1 high-frequency report-only runner.

Runs after a checkpoint artifact is downloaded. Writes reports without
re-extracting OpenF1 data and without relying on pandas.to_markdown.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


def fmt_value(v):
    if pd.isna(v):
        return ""
    if isinstance(v, float):
        if abs(v) < 1 and v != 0:
            return f"{v:.4f}"
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.4f}"
    return str(v).replace("\n", " ").replace("|", "\\|")


def markdown_table(df: pd.DataFrame, max_rows: int = 20) -> list[str]:
    if df is None or df.empty:
        return ["_No rows._"]
    d = df.head(max_rows).copy()
    cols = list(d.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in d.iterrows():
        lines.append("| " + " | ".join(fmt_value(row[c]) for c in cols) + " |")
    if len(df) > max_rows:
        lines += ["", f"_Showing first {max_rows} of {len(df)} rows._"]
    return lines


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--mode", required=True)
    p.add_argument("--workflow-label", default="OpenF1 automated ingest")
    args = p.parse_args()

    root = Path(args.output_dir)
    report_dir = root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_csv_if_exists(root / "manifests" / "high_frequency_extraction_manifest.csv")
    feature_manifest = read_csv_if_exists(root / "manifests" / "feature_manifest.csv")
    sessions = read_csv_if_exists(root / "manifests" / "completed_sessions_selected.csv")
    metrics = read_csv_if_exists(root / "metrics" / "pre_race_first_warning_to_dnf_aggregate.csv")
    phase = read_csv_if_exists(root / "metrics" / "pre_race_first_warning_phase_breakdown.csv")

    checkpoint_summary = {}
    checkpoint_summary_path = root / "manifests" / "extraction_checkpoint_summary.json"
    if checkpoint_summary_path.exists():
        try:
            checkpoint_summary = json.loads(checkpoint_summary_path.read_text(encoding="utf-8"))
        except Exception:
            checkpoint_summary = {}

    total_rows = 0
    if not manifest.empty and "rows" in manifest.columns:
        total_rows = int(pd.to_numeric(manifest["rows"], errors="coerce").fillna(0).sum())

    feature_rows_30s = 0
    if not feature_manifest.empty and "rows_30s" in feature_manifest.columns:
        feature_rows_30s = int(pd.to_numeric(feature_manifest["rows_30s"], errors="coerce").fillna(0).sum())

    lines = [
        "# OpenF1 Automated Ingest Report",
        "",
        f"Workflow: {args.workflow_label}",
        f"Year: {args.year}",
        f"Mode: {args.mode}",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Status",
        "",
        f"- Checkpoint status: {checkpoint_summary.get('status', 'unknown')}",
        f"- Selected sessions: {len(sessions)}",
        f"- Manifest rows: {len(manifest)}",
        f"- Total high-frequency rows: {total_rows}",
        f"- Feature manifest rows: {len(feature_manifest)}",
        f"- 30-second feature rows: {feature_rows_30s}",
        "",
        "## Selected sessions",
        "",
    ]
    lines += markdown_table(sessions[[c for c in ["country_name", "meeting_name", "session_name", "session_type", "session_key", "date_start"] if c in sessions.columns]], max_rows=30)
    lines += ["", "## Extraction status by endpoint", ""]
    if not manifest.empty and "endpoint" in manifest.columns:
        endpoint_summary = (
            manifest.assign(rows_num=pd.to_numeric(manifest.get("rows", 0), errors="coerce").fillna(0))
            .groupby(["endpoint", "status"], dropna=False)
            .agg(files=("endpoint", "size"), rows=("rows_num", "sum"))
            .reset_index()
        )
        lines += markdown_table(endpoint_summary, max_rows=30)
    else:
        lines += ["_No extraction manifest found._"]

    lines += ["", "## Pre-race / DNF warning metric", ""]
    lines += markdown_table(metrics, max_rows=20) if not metrics.empty else ["_No pre-race aggregate metric produced for this mode._"]

    if not phase.empty:
        lines += ["", "## First warning phase breakdown", ""]
        lines += markdown_table(phase, max_rows=20)

    lines += [
        "",
        "## Authority / guardrails",
        "",
        "- Public/proxy OpenF1 data only.",
        "- Risk/fantasy/reporting only.",
        "- No automatic qualifying P1-P5 reorder.",
        "- No automatic stable race P1-P20 reorder.",
        "- DNF_ALL remains a broad precursor-search target; visible DNF labels are metadata, not exclusion gates.",
        "- 2026 no-DRS rule preserved; do not infer DRS-assisted passing from any source field.",
        "",
    ]

    report_path = report_dir / "openf1_high_frequency_auto_ingest_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    summary_lines = [
        "## OpenF1 automated ingest summary",
        "",
        f"- Workflow: {args.workflow_label}",
        f"- Mode: {args.mode}",
        f"- Selected sessions: {len(sessions)}",
        f"- Total high-frequency rows: {total_rows}",
        f"- 30-second feature rows: {feature_rows_30s}",
        f"- Report: `{report_path}`",
        "",
    ]
    (report_dir / "github_step_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Report written: {report_path}")


if __name__ == "__main__":
    main()
