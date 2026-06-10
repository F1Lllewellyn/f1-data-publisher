#!/usr/bin/env python3
"""
F1 Season Archive Publisher.

Creates a long-term GitHub Release archive from compact derived outputs.

Expanded operational archive profile:
- Elite Weekend Engine v2 outputs
- Workbook Control Room Bridge outputs
- Dry Forecast Cycle outputs
- Forecast Use Dry Review outputs
- Race Weekend Operating Rhythm outputs
- Post-Race Scoring Loop outputs
- Automation Baseline Snapshot

This intentionally avoids relying on 90-day GitHub Actions artifact retention.
It does not re-run OpenF1 extraction and does not archive raw high-frequency
car_data/location by default.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError


DEFAULT_PREFIXES = {
    "elite_outputs": ["elite-weekend-engine-v2"],
    "workbook_bridge": ["f1-workbook-control-room-bridge"],
    "dry_forecast_cycle": ["f1-dry-forecast-cycle"],
    "forecast_use_dry_review": ["f1-forecast-use-dry-review"],
    "race_weekend_operating_rhythm": ["f1-race-weekend-operating-rhythm"],
    "post_race_scoring_loop": ["f1-post-race-scoring-loop"],
    "baseline_snapshot": ["F1_Automation_Baseline_2026-06-10_READY"],
}


def now_utc():
    return datetime.now(timezone.utc)


def gh_headers(token: str, content_type: str | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "f1-season-archive-publisher",
    }
    if content_type:
        h["Content-Type"] = content_type
    return h


def gh_request_json(method: str, url: str, token: str, body: dict | None = None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=data,
        method=method,
        headers=gh_headers(token, "application/json" if body is not None else None),
    )
    with urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def get_artifact_redirect_url(url: str, token: str) -> str:
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
                raise RuntimeError("Artifact redirect response missing Location header.")
            return loc
        raise


def download_artifact_zip(archive_download_url: str, token: str, dest: Path):
    signed = get_artifact_redirect_url(archive_download_url, token)
    if signed == archive_download_url:
        req = Request(archive_download_url, headers=gh_headers(token))
    else:
        req = Request(signed, headers={"User-Agent": "f1-season-archive-publisher"})
    with urlopen(req, timeout=900) as r:
        dest.write_bytes(r.read())


def list_artifacts(repo: str, token: str):
    artifacts = []
    page = 1
    while page <= 10:
        url = f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100&page={page}"
        data = gh_request_json("GET", url, token)
        batch = data.get("artifacts", [])
        artifacts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return artifacts


def pick_latest_artifact(artifacts, prefixes):
    candidates = []
    for a in artifacts:
        if a.get("expired", False):
            continue
        name = a.get("name", "")
        if any(name.startswith(prefix) for prefix in prefixes):
            candidates.append(a)
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return candidates[0]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def zip_dir(source_dir: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in source_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(source_dir))


def safe_extract(zip_path: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for member in z.infolist():
            member_path = dest / member.filename
            resolved = member_path.resolve()
            if not str(resolved).startswith(str(dest.resolve())):
                raise RuntimeError(f"Unsafe zip path: {member.filename}")
        z.extractall(dest)


def create_or_get_release(repo: str, token: str, tag_name: str, release_name: str, body: str, target_commitish: str):
    get_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag_name}"
    try:
        return gh_request_json("GET", get_url, token)
    except HTTPError as e:
        if e.code != 404:
            raise

    create_url = f"https://api.github.com/repos/{repo}/releases"
    payload = {
        "tag_name": tag_name,
        "target_commitish": target_commitish,
        "name": release_name,
        "body": body,
        "draft": False,
        "prerelease": False,
        "make_latest": "false",
    }
    return gh_request_json("POST", create_url, token, payload)


def upload_release_asset(upload_url_template: str, token: str, asset_path: Path):
    base = upload_url_template.split("{", 1)[0]
    params = urlencode({"name": asset_path.name})
    url = f"{base}?{params}"

    content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
    req = Request(
        url,
        data=asset_path.read_bytes(),
        method="POST",
        headers=gh_headers(token, content_type),
    )
    with urlopen(req, timeout=900) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--season-year", default="2026")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--target-commitish", default="main")
    p.add_argument("--archive-scope", choices=["compact"], default="compact")
    p.add_argument("--release-tag", default="")
    p.add_argument("--release-name", default="")
    args = p.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    run_number = os.environ.get("GITHUB_RUN_NUMBER", "local")
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY is not set.")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set.")

    stamp = now_utc().strftime("%Y%m%d")
    release_tag = args.release_tag or f"F1_{args.season_year}_Season_Archive_{stamp}_run{run_number}"
    release_name = args.release_name or f"F1 {args.season_year} Season Archive — {stamp} run {run_number}"

    out = Path(args.output_dir)
    downloads = out / "downloads"
    archive_root = out / f"F1_{args.season_year}_Season_Archive"
    for d in [downloads, archive_root]:
        d.mkdir(parents=True, exist_ok=True)

    artifacts = list_artifacts(repo, token)
    source_rows = []

    for profile, prefixes in DEFAULT_PREFIXES.items():
        target = pick_latest_artifact(artifacts, prefixes)
        row = {
            "profile": profile,
            "prefixes": ";".join(prefixes),
            "found": False,
            "artifact_id": "",
            "artifact_name": "",
            "created_at": "",
            "updated_at": "",
            "size_in_bytes": "",
            "status": "MISSING",
        }
        if target is None:
            source_rows.append(row)
            continue

        zip_path = downloads / f"{profile}_{target['id']}.zip"
        extract_dir = archive_root / profile
        try:
            download_artifact_zip(target["archive_download_url"], token, zip_path)
            safe_extract(zip_path, extract_dir)
            row.update({
                "found": True,
                "artifact_id": str(target.get("id", "")),
                "artifact_name": target.get("name", ""),
                "created_at": target.get("created_at", ""),
                "updated_at": target.get("updated_at", ""),
                "size_in_bytes": str(target.get("size_in_bytes", "")),
                "status": "ARCHIVED",
            })
        except Exception as e:
            row.update({
                "found": True,
                "artifact_id": str(target.get("id", "")),
                "artifact_name": target.get("name", ""),
                "created_at": target.get("created_at", ""),
                "updated_at": target.get("updated_at", ""),
                "size_in_bytes": str(target.get("size_in_bytes", "")),
                "status": f"FAILED: {type(e).__name__}: {e}",
            })
            source_rows.append(row)
            raise

        source_rows.append(row)

    manifests = archive_root / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)

    source_manifest_csv = manifests / "season_archive_source_artifacts.csv"
    with source_manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(source_rows[0].keys()) if source_rows else ["profile"])
        writer.writeheader()
        writer.writerows(source_rows)

    archived_count = sum(1 for r in source_rows if r["status"] == "ARCHIVED")
    missing_count = sum(1 for r in source_rows if r["status"] == "MISSING")

    policy = {
        "generated_utc": now_utc().isoformat(),
        "season_year": args.season_year,
        "archive_scope": args.archive_scope,
        "repository": repo,
        "release_tag": release_tag,
        "release_name": release_name,
        "retention_strategy": "github_release_assets_long_term_archive",
        "raw_high_frequency_data_included": False,
        "raw_data_policy": "Excluded by default. Archive raw only for explicit forensic/end-of-season snapshots.",
        "artifact_profile_count": len(source_rows),
        "artifact_profiles_archived": archived_count,
        "artifact_profiles_missing": missing_count,
        "guardrails": {
            "public_proxy_only": True,
            "no_private_internal_sensor_dependency": True,
            "no_stable_race_p1_p20_automatic_change": True,
            "no_qualifying_p1_p5_automatic_change": True,
            "dnf_all_broad_precursor_search": True,
            "no_drs_2026_assumption": True,
        },
        "artifact_profiles": source_rows,
    }
    policy_path = manifests / "season_archive_manifest.json"
    policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    report_lines = [
        f"# F1 {args.season_year} Season Archive",
        "",
        f"Generated UTC: {policy['generated_utc']}",
        f"Release tag: `{release_tag}`",
        f"Archive scope: `{args.archive_scope}`",
        f"Artifact profiles archived: `{archived_count}/{len(source_rows)}`",
        "",
        "## Source artifacts",
        "",
        "| Profile | Artifact | Status | Size bytes |",
        "|---|---|---:|---:|",
    ]
    for row in source_rows:
        report_lines.append(f"| {row['profile']} | {row['artifact_name']} | {row['status']} | {row['size_in_bytes']} |")

    report_lines += [
        "",
        "## Long-term retention policy",
        "",
        "This archive is published as a GitHub Release asset so it is not dependent on GitHub Actions artifact retention.",
        "",
        "Raw high-frequency OpenF1 data is not included by default. Compact derived outputs, ledgers, workbook bridge exports, forecast reviews, post-race scoring packages, validation summaries, and manifests are included.",
        "",
        "## Guardrails",
        "",
        "- Public/proxy OpenF1 data only.",
        "- No automatic stable race P1-P20 rank changes.",
        "- No automatic qualifying P1-P5 rank changes.",
        "- DNF_ALL broad precursor-search policy preserved.",
        "- 2026 no-DRS rule preserved.",
        "",
    ]
    report_path = manifests / "season_archive_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    archive_zip = out / f"F1_{args.season_year}_Season_Archive_COMPACT_EXPANDED_{stamp}_run{run_number}.zip"
    zip_dir(archive_root, archive_zip)

    checksum_path = out / f"{archive_zip.name}.sha256.txt"
    checksum_path.write_text(f"{sha256(archive_zip)}  {archive_zip.name}\n", encoding="utf-8")

    release_body = "\n".join(report_lines)
    release = create_or_get_release(repo, token, release_tag, release_name, release_body, args.target_commitish)

    uploaded_assets = []
    for asset in [archive_zip, checksum_path, policy_path, report_path, source_manifest_csv]:
        try:
            uploaded_assets.append(upload_release_asset(release["upload_url"], token, asset))
        except HTTPError as e:
            if e.code == 422:
                print(f"Asset may already exist, skipping: {asset.name}")
            else:
                raise

    publish_summary = {
        "generated_utc": now_utc().isoformat(),
        "release_tag": release_tag,
        "release_name": release_name,
        "release_html_url": release.get("html_url"),
        "archive_zip": str(archive_zip),
        "archive_sha256": sha256(archive_zip),
        "uploaded_assets": [a.get("name") for a in uploaded_assets],
        "source_artifacts": source_rows,
        "status": "PUBLISHED",
    }
    (out / "season_archive_publish_summary.json").write_text(json.dumps(publish_summary, indent=2), encoding="utf-8")

    step_summary = [
        f"## F1 {args.season_year} Season Archive Published",
        "",
        f"- Release tag: `{release_tag}`",
        f"- Archive: `{archive_zip.name}`",
        f"- SHA256: `{publish_summary['archive_sha256']}`",
        f"- Artifact profiles archived: `{archived_count}/{len(source_rows)}`",
        f"- Raw high-frequency data included: `false`",
        "",
        "### Source artifacts",
        "",
        "| Profile | Status | Artifact |",
        "|---|---:|---|",
    ]
    for row in source_rows:
        step_summary.append(f"| {row['profile']} | {row['status']} | {row['artifact_name']} |")
    (out / "github_step_summary.md").write_text("\n".join(step_summary), encoding="utf-8")

    print(json.dumps(publish_summary, indent=2))


if __name__ == "__main__":
    main()
