#!/usr/bin/env python3
"""
Download the latest Elite Weekend Engine v2 artifact.

Uses GitHub REST API and handles the GitHub artifact redirect correctly:
- authenticate to the GitHub API endpoint,
- capture signed storage redirect,
- download signed URL without GitHub Authorization header.
"""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError


PREFIXES = [
    "elite-weekend-engine-v2",
]


def gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "f1-operational-downstream",
    }


def gh_get_json(url: str, token: str):
    req = Request(url, headers=gh_headers(token))
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get_redirect_url(url: str, token: str) -> str:
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    req = Request(url, headers=gh_headers(token))
    try:
        with opener.open(req, timeout=60):
            return url
    except HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            loc = e.headers.get("Location")
            if not loc:
                raise RuntimeError("Redirect response missing Location header.")
            return loc
        raise


def download_artifact(archive_download_url: str, token: str, dest: Path):
    signed = get_redirect_url(archive_download_url, token)
    if signed == archive_download_url:
        req = Request(archive_download_url, headers=gh_headers(token))
    else:
        req = Request(signed, headers={"User-Agent": "f1-operational-downstream"})
    with urlopen(req, timeout=600) as r:
        dest.write_bytes(r.read())


def list_artifacts(repo: str, token: str):
    artifacts = []
    page = 1
    while page <= 10:
        data = gh_get_json(f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100&page={page}", token)
        batch = data.get("artifacts", [])
        artifacts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return artifacts


def pick_latest(artifacts):
    candidates = []
    for a in artifacts:
        name = a.get("name", "")
        if a.get("expired", False):
            continue
        if any(name.startswith(prefix) for prefix in PREFIXES):
            candidates.append(a)
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return candidates[0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY is not set.")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set.")

    out = Path(args.output_dir)
    artifact_dir = out / "elite_artifact"
    manifest_dir = out / "manifests"
    download_dir = out / "downloads"
    for d in [artifact_dir, manifest_dir, download_dir]:
        d.mkdir(parents=True, exist_ok=True)

    target = pick_latest(list_artifacts(repo, token))
    if target is None:
        raise SystemExit("No Elite Weekend Engine v2 artifact found.")

    zip_path = download_dir / f"elite_{target['id']}.zip"
    download_artifact(target["archive_download_url"], token, zip_path)

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(artifact_dir)

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repository": repo,
        "artifact_id": target.get("id"),
        "artifact_name": target.get("name"),
        "created_at": target.get("created_at"),
        "updated_at": target.get("updated_at"),
        "size_in_bytes": target.get("size_in_bytes"),
        "zip_path": str(zip_path),
        "extracted_to": str(artifact_dir)
    }
    (manifest_dir / "latest_elite_artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
