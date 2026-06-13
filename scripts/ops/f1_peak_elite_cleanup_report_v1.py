#!/usr/bin/env python3
"""F1 peak-elite cleanup inventory v1.

Generates a cleanup/declutter report without deleting or moving files. The
installer can safely add this to the repo because governance prefers archiving
and explicit review over deletion.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    out = root / "_runtime" / "peak_elite" / "cleanup"
    out.mkdir(parents=True, exist_ok=True)

    files = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
    large = []
    bom = []
    old_installers = []
    manifest_docs = []
    duplicate_hash: Dict[str, List[str]] = {}
    for p in files:
        rel = str(p.relative_to(root)).replace("\\", "/")
        size = p.stat().st_size
        if size > 1024 * 1024:
            large.append({"path": rel, "bytes": size})
        if p.suffix.lower() in {".yml", ".yaml", ".py", ".ps1", ".cmd", ".bat", ".md", ".txt"}:
            try:
                if p.read_bytes().startswith(b"\xef\xbb\xbf"):
                    bom.append(rel)
            except Exception:
                pass
        lname = p.name.lower()
        if "installer" in lname or "oneclick" in lname or "one-click" in lname or rel.startswith("installer/"):
            old_installers.append(rel)
        if p.name.upper().endswith(("MANIFEST.CSV", "MANIFEST.JSON")) or p.name.startswith("CURRENT_CANONICAL_FILES"):
            manifest_docs.append(rel)
        if size < 512 * 1024:
            try:
                duplicate_hash.setdefault(sha256(p), []).append(rel)
            except Exception:
                pass
    duplicates = [v for v in duplicate_hash.values() if len(v) > 1]

    report = {
        "created_utc": iso_now(),
        "status": "report_only",
        "file_count": len(files),
        "large_files_over_1mb": sorted(large, key=lambda x: x["bytes"], reverse=True),
        "utf8_bom_files": bom,
        "installer_or_oneclick_files": old_installers[:500],
        "manifest_or_canonical_docs": manifest_docs[:500],
        "duplicate_small_file_groups": duplicates[:100],
        "delete_performed": False,
        "archive_performed": False,
        "stable_engine_modified": False,
        "canonical_workbook_overwrite": False,
        "promotion_allowed": False,
    }
    write_json(out / "cleanup_inventory.json", report)
    md = [
        "# F1 Peak-Elite Cleanup Inventory",
        "",
        f"Created UTC: `{report['created_utc']}`",
        "Status: **report only**",
        "",
        "No files were deleted or moved by this script.",
        "",
        "## Cleanup pressure points",
        f"- Total tracked/non-.git files scanned: `{report['file_count']}`",
        f"- Large files >1 MB: `{len(large)}`",
        f"- UTF-8 BOM text files: `{len(bom)}`",
        f"- Installer/one-click artifacts: `{len(old_installers)}`",
        f"- Manifest/canonical docs: `{len(manifest_docs)}`",
        f"- Duplicate small-file hash groups: `{len(duplicates)}`",
        "",
        "## Governance",
        "- Deletion performed: `false`",
        "- Archive performed: `false`",
        "- Stable engine modified: `false`",
        "- Canonical workbook overwritten: `false`",
        "- Model promotion: `false`",
    ]
    (out / "CLEANUP_INVENTORY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
