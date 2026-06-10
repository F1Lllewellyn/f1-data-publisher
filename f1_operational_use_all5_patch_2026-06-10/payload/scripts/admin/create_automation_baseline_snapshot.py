#!/usr/bin/env python3
"""
Create a lightweight operational baseline snapshot manifest.

This does not run OpenF1 extraction. It records repo state, workflow files,
policy/config files, and operational docs for audit/release baselining.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import zipfile


INCLUDE_PREFIXES = [
    ".github/workflows/",
    "scripts/openf1/",
    "scripts/elite/",
    "scripts/workbook/",
    "scripts/forecast/",
    "scripts/admin/",
    "configs/forecast/",
    "docs/",
]

INCLUDE_FILES = [
    "CURRENT_CANONICAL_FILES_AUTOMATION_OPERATIONAL_BASELINE_2026-06-10.md",
    "ALL5_OPERATIONAL_PATCH_MANIFEST.csv",
    "ELITE_V2_NODE24_PAYLOAD_MANIFEST.csv",
    "ELITE_V2_ARTIFACT_DOWNLOAD_401_HOTFIX_MANIFEST.csv",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def included(rel: str) -> bool:
    rel_norm = rel.replace("\\", "/")
    return any(rel_norm.startswith(p) for p in INCLUDE_PREFIXES) or rel_norm in INCLUDE_FILES


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--baseline-name", default="F1_Automation_Baseline_2026-06-10_READY")
    args = p.parse_args()

    repo = Path(args.repo_root).resolve()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        if ".git/" in rel or rel.startswith("_archive/"):
            continue
        if included(rel):
            rows.append({
                "path": rel,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            })

    rows.sort(key=lambda x: x["path"])

    csv_lines = ["path,size_bytes,sha256"]
    for r in rows:
        csv_lines.append(f'"{r["path"]}",{r["size_bytes"]},"{r["sha256"]}"')

    (out / "baseline_snapshot_manifest.csv").write_text("\n".join(csv_lines), encoding="utf-8")

    summary = {
        "baseline_name": args.baseline_name,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo),
        "file_count": len(rows),
        "status": "BASELINE_SNAPSHOT_CREATED",
        "notes": "Lightweight operational baseline manifest; no OpenF1 extraction was run."
    }
    (out / "baseline_snapshot_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# F1 Automation Baseline Snapshot",
        "",
        f"Baseline: `{args.baseline_name}`",
        f"Generated UTC: {summary['generated_utc']}",
        f"Files recorded: {len(rows)}",
        "",
        "This snapshot records the operational automation/workflow/control files only. It does not include raw OpenF1 data.",
        "",
    ]
    (out / "baseline_snapshot_report.md").write_text("\n".join(report), encoding="utf-8")

    zip_path = out / f"{args.baseline_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for file_name in ["baseline_snapshot_manifest.csv", "baseline_snapshot_summary.json", "baseline_snapshot_report.md"]:
            z.write(out / file_name, file_name)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
