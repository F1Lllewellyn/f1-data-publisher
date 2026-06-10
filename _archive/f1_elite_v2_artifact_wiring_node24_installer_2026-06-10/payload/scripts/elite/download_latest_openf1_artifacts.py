#!/usr/bin/env python3
"""
Download latest successful OpenF1 autopilot artifacts for Elite Weekend Engine v2.

Uses GitHub REST API via GITHUB_TOKEN. This avoids manual uploads and lets the
Elite workflow consume the most recent validated OpenF1 artifacts automatically.
"""

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen


PROFILES = {
    "pre_race": [
        "openf1-prerace-auto-final",
        "openf1-high-frequency-2026-prerace",
    ],
    "full_historical": [
        "openf1-full-historical-auto-final",
        "openf1-high-frequency-2026-all",
    ],
    "post_race": [
        "openf1-post-race-auto-final",
    ],
}


def gh_get_json(url: str, token: str):
    req = Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "f1-elite-weekend-engine-v2",
    })
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def gh_download(url: str, token: str, dest: Path):
    req = Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "f1-elite-weekend-engine-v2",
    })
    with urlopen(req, timeout=300) as r:
        dest.write_bytes(r.read())


def list_artifacts(repo: str, token: str):
    artifacts = []
    page = 1
    while page <= 5:
        url = f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100&page={page}"
        data = gh_get_json(url, token)
        batch = data.get("artifacts", [])
        artifacts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return artifacts


def pick_latest(artifacts, prefixes):
    candidates = []
    for a in artifacts:
        name = a.get("name", "")
        expired = bool(a.get("expired", False))
        if expired:
            continue
        if any(name.startswith(prefix) for prefix in prefixes):
            candidates.append(a)
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return candidates[0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--include-post-race-warning", action="store_true")
    args = p.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    if not repo:
        raise SystemExit("GITHUB_REPOSITORY is not set.")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set.")

    out = Path(args.output_dir)
    inputs = out / "inputs"
    downloads = out / "downloads"
    manifests = out / "manifests"
    for d in [inputs, downloads, manifests]:
        d.mkdir(parents=True, exist_ok=True)

    artifacts = list_artifacts(repo, token)
    rows = []

    for profile, prefixes in PROFILES.items():
        target = pick_latest(artifacts, prefixes)
        profile_dir = inputs / profile
        profile_dir.mkdir(parents=True, exist_ok=True)

        row = {
            "profile": profile,
            "prefixes": ";".join(prefixes),
            "found": False,
            "artifact_id": "",
            "artifact_name": "",
            "created_at": "",
            "updated_at": "",
            "size_in_bytes": "",
            "downloaded_to": "",
            "extracted_to": str(profile_dir),
            "status": "MISSING",
        }

        if target is None:
            rows.append(row)
            continue

        zip_path = downloads / f"{profile}_{target['id']}.zip"
        gh_download(target["archive_download_url"], token, zip_path)

        with zipfile.ZipFile(zip_path) as z:
            z.extractall(profile_dir)

        row.update({
            "found": True,
            "artifact_id": str(target.get("id", "")),
            "artifact_name": target.get("name", ""),
            "created_at": target.get("created_at", ""),
            "updated_at": target.get("updated_at", ""),
            "size_in_bytes": str(target.get("size_in_bytes", "")),
            "downloaded_to": str(zip_path),
            "status": "DOWNLOADED",
        })
        rows.append(row)

    manifest_path = manifests / "elite_artifact_source_manifest.json"
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repository": repo,
        "profiles": rows,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # CSV-lite without pandas dependency for this stage
    csv_path = manifests / "elite_artifact_source_manifest.csv"
    headers = ["profile", "found", "artifact_id", "artifact_name", "created_at", "updated_at", "size_in_bytes", "status", "extracted_to"]
    lines = [",".join(headers)]
    for row in rows:
        def clean(v):
            s = str(v).replace('"', '""')
            return f'"{s}"'
        lines.append(",".join(clean(row.get(h, "")) for h in headers))
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    found_count = sum(1 for r in rows if r["found"])
    print(f"Downloaded {found_count}/{len(rows)} OpenF1 artifact profiles.")
    print(manifest_path)

    # Do not fail if one optional artifact is missing; Elite v2 will grade readiness.
    if found_count == 0:
        raise SystemExit("No OpenF1 artifacts found; cannot run Elite Weekend Engine v2.")


if __name__ == "__main__":
    main()
