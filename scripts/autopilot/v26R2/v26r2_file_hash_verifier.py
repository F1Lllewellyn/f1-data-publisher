
#!/usr/bin/env python3
"""Dormant v26R2 helper for read-only file hash verification.

This module performs no network calls and no repository mutation. It compares local
file bytes against an expected SHA-256 manifest and is intended as the reference
logic for a future read-only bridge lane.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class FileHashResult:
    path: str
    present: bool
    byte_length: int | None
    sha256: str | None
    expected_sha256: str
    match: bool


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_hashes(root: Path, expected_sha256: Mapping[str, str]) -> List[FileHashResult]:
    results: List[FileHashResult] = []
    for rel_path, expected in expected_sha256.items():
        candidate = root / rel_path
        if not candidate.exists() or not candidate.is_file():
            results.append(FileHashResult(rel_path, False, None, None, expected, False))
            continue
        data = candidate.read_bytes()
        actual = sha256_bytes(data)
        results.append(FileHashResult(rel_path, True, len(data), actual, expected, actual == expected))
    return results


def summarize(results: Iterable[FileHashResult]) -> dict:
    rows = list(results)
    return {
        "file_count": len(rows),
        "all_present": all(r.present for r in rows),
        "all_hashes_match": all(r.match for r in rows),
        "missing_paths": [r.path for r in rows if not r.present],
        "mismatched_paths": [r.path for r in rows if r.present and not r.match],
        "results": [asdict(r) for r in rows],
    }


def load_expected_manifest(path: Path) -> Dict[str, str]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "expected_file_sha256" in data:
            data = data["expected_file_sha256"]
        if not isinstance(data, dict):
            raise ValueError("JSON manifest must be an object or contain expected_file_sha256 object")
        return {str(k): str(v) for k, v in data.items()}

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "path" not in reader.fieldnames or "sha256" not in reader.fieldnames:
            raise ValueError("CSV manifest must include path and sha256 columns")
        return {row["path"]: row["sha256"] for row in reader}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local file SHA-256 values against a manifest.")
    parser.add_argument("--root", required=True, help="Repository/worktree root")
    parser.add_argument("--manifest", required=True, help="CSV or JSON manifest with path/sha256 entries")
    parser.add_argument("--output-json", default="", help="Optional JSON output path")
    args = parser.parse_args()

    expected = load_expected_manifest(Path(args.manifest))
    results = verify_hashes(Path(args.root), expected)
    summary = summarize(results)

    output = json.dumps(summary, indent=2, sort_keys=True)
    if args.output_json:
        Path(args.output_json).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if summary["all_present"] and summary["all_hashes_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
