#!/usr/bin/env python3
"""Safely download the latest OpenF1 artifacts for Elite Weekend Engine v2.

GitHub's authenticated artifact endpoint redirects to short-lived object storage.
The GitHub token is used only at the API endpoint; the signed storage request is
separately validated and never receives GitHub credentials. Downloads and ZIP
extraction are bounded and become visible only after complete validation.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


PROFILES = {
    "pre_race": ["openf1-prerace-auto-final", "openf1-high-frequency-2026-prerace"],
    "full_historical": ["openf1-full-historical-auto-final", "openf1-high-frequency-2026-all"],
    "post_race": ["openf1-post-race-auto-final"],
}
APPROVED_WORKFLOWS = {
    "pre_race": {
        "openf1-prerace-auto-final": ".github/workflows/openf1-prerace-auto-ingest.yml",
    },
    "full_historical": {
        "openf1-full-historical-auto-final": ".github/workflows/openf1-full-historical-auto-ingest.yml",
    },
    "post_race": {
        "openf1-post-race-auto-final": ".github/workflows/openf1-post-race-auto-reliability.yml",
    },
}
EVENT_SESSION_PROVENANCE_STATUS = "HOLD_ARCHITECTURE_SCOPE"
EVENT_SESSION_PROVENANCE_HOLD = (
    "HOLD_ARCHITECTURE_SCOPE: exact event/session provenance is not independently verified"
)
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024
MAX_EXTRACTED_BYTES = 8 * 1024 * 1024 * 1024
MAX_ZIP_MEMBERS = 100_000
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ArtifactHold(RuntimeError):
    """A deterministic, fail-closed artifact intake HOLD."""


def gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "f1-elite-weekend-engine-v2",
    }


def gh_get_json(url: str, token: str):
    req = Request(url, headers=gh_headers(token))
    with urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ArtifactHold(f"invalid artifact {field}; HOLD")
    try:
        # Query parsing decodes a literal '+' in an ISO offset as a space.
        parsed = datetime.fromisoformat(value.replace(" ", "+").replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactHold(f"invalid artifact {field}; HOLD") from exc
    if parsed.tzinfo is None:
        raise ArtifactHold(f"invalid artifact {field}; HOLD")
    return parsed.astimezone(timezone.utc)


def _artifact_name_matches(name: str, prefixes: list[str]) -> bool:
    return any(name == prefix or name.startswith(prefix + "-") for prefix in prefixes)


def validate_artifact(artifact: dict, repo: str, prefixes: list[str]) -> dict:
    if not isinstance(artifact, dict):
        raise ArtifactHold("invalid artifact metadata; HOLD")
    name = artifact.get("name")
    if not isinstance(name, str) or not _artifact_name_matches(name, prefixes):
        raise ArtifactHold("artifact profile identity mismatch; HOLD")
    artifact_id = artifact.get("id")
    if isinstance(artifact_id, bool) or not isinstance(artifact_id, int) or artifact_id <= 0:
        raise ArtifactHold("invalid artifact id; HOLD")
    size = artifact.get("size_in_bytes")
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_ARTIFACT_BYTES:
        raise ArtifactHold("artifact transfer size is invalid or exceeds limit; HOLD")
    if artifact.get("expired") is not False:
        raise ArtifactHold("artifact is expired or expiry is unresolved; HOLD")
    created = _parse_utc(artifact.get("created_at"), "created_at")
    updated = _parse_utc(artifact.get("updated_at"), "updated_at")
    if updated < created:
        raise ArtifactHold("artifact chronology is invalid; HOLD")
    archive_url = artifact.get("archive_download_url")
    parsed = urlparse(archive_url if isinstance(archive_url, str) else "")
    expected_path = f"/repos/{repo}/actions/artifacts/{artifact_id}/zip"
    if (
        parsed.scheme != "https" or parsed.hostname != "api.github.com"
        or parsed.path != expected_path or parsed.username or parsed.password
        or parsed.query or parsed.fragment
    ):
        raise ArtifactHold("artifact archive identity mismatch; HOLD")
    workflow_run = artifact.get("workflow_run")
    if not isinstance(workflow_run, dict):
        raise ArtifactHold("missing or invalid originating workflow-run identity; HOLD")
    run_id = workflow_run.get("id")
    head_sha = workflow_run.get("head_sha")
    if (
        isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0
        or not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha)
    ):
        raise ArtifactHold("missing or invalid originating workflow-run identity; HOLD")
    return artifact


def _expected_workflow_path(artifact: dict, profile: str) -> str:
    profile_workflows = APPROVED_WORKFLOWS.get(profile)
    if profile_workflows is None:
        raise ArtifactHold("unknown artifact profile; HOLD")
    name = artifact["name"]
    for prefix, workflow_path in profile_workflows.items():
        if name == prefix or name.startswith(prefix + "-"):
            return workflow_path
    raise ArtifactHold(
        "HOLD_ARCHITECTURE_SCOPE: artifact prefix has no approved originating workflow identity"
    )


def verify_originating_workflow_run(artifact: dict, profile: str, repo: str, token: str) -> dict:
    """Independently bind listing identity to one completed approved workflow run."""
    validate_artifact(artifact, repo, PROFILES.get(profile, []))
    expected_path = _expected_workflow_path(artifact, profile)
    listed = artifact["workflow_run"]
    run_url = f"https://api.github.com/repos/{repo}/actions/runs/{listed['id']}"
    try:
        run = gh_get_json(run_url, token)
    except HTTPError as exc:
        raise ArtifactHold(f"originating workflow-run lookup returned HTTP {exc.code}; HOLD") from exc
    except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactHold("originating workflow-run lookup failed; HOLD") from exc
    if not isinstance(run, dict):
        raise ArtifactHold("originating workflow-run response is malformed; HOLD")

    repository = run.get("repository")
    head_repository = run.get("head_repository")
    run_id = run.get("id")
    run_attempt = run.get("run_attempt")
    if (
        isinstance(run_id, bool) or run_id != listed["id"]
        or run.get("head_sha") != listed["head_sha"]
        or run.get("path") != expected_path
        or run.get("head_branch") != "main"
        or run.get("event") not in {"schedule", "workflow_dispatch"}
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or not isinstance(repository, dict) or repository.get("full_name") != repo
        or not isinstance(head_repository, dict) or head_repository.get("full_name") != repo
        or isinstance(run_attempt, bool) or not isinstance(run_attempt, int) or run_attempt <= 0
        or run.get("artifacts_url") != f"https://api.github.com/repos/{repo}/actions/runs/{listed['id']}/artifacts"
    ):
        raise ArtifactHold("originating workflow-run identity mismatch; HOLD")

    run_created = _parse_utc(run.get("created_at"), "workflow-run created_at")
    run_started = _parse_utc(run.get("run_started_at"), "workflow-run run_started_at")
    run_updated = _parse_utc(run.get("updated_at"), "workflow-run updated_at")
    artifact_created = _parse_utc(artifact["created_at"], "created_at")
    artifact_updated = _parse_utc(artifact["updated_at"], "updated_at")
    if not run_created <= run_started <= artifact_created <= artifact_updated <= run_updated:
        raise ArtifactHold("originating workflow-run chronology mismatch; HOLD")
    return {
        "id": run_id,
        "head_sha": run["head_sha"],
        "path": run["path"],
        "head_branch": run["head_branch"],
        "event": run["event"],
        "run_attempt": run_attempt,
        "repository": repo,
        "status": run["status"],
        "conclusion": run["conclusion"],
    }


def get_artifact_redirect_url(url: str, token: str) -> str:
    """Return the signed Location without forwarding authentication."""
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    req = Request(url, headers=gh_headers(token))
    try:
        with opener.open(req, timeout=60):
            raise ArtifactHold("GitHub artifact endpoint did not return a signed redirect; HOLD")
    except HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise ArtifactHold(f"GitHub artifact endpoint returned HTTP {exc.code}; HOLD") from exc
        location = exc.headers.get("Location")
        if not location:
            raise ArtifactHold("GitHub artifact redirect has no Location; HOLD") from exc
        return location


def _signed_url_expiry(url: str) -> datetime:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed_host = (
        host.endswith(".blob.core.windows.net")
        or host.endswith(".actions.githubusercontent.com")
        or host.endswith(".amazonaws.com")
    )
    if (
        parsed.scheme != "https" or not allowed_host or parsed.username
        or parsed.password or parsed.fragment
    ):
        raise ArtifactHold("artifact redirect host or scheme is not trusted; HOLD")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if "se" in query and len(query["se"]) == 1:
        return _parse_utc(query["se"][0], "redirect expiry")
    if all(key in query and len(query[key]) == 1 for key in ("X-Amz-Date", "X-Amz-Expires")):
        try:
            issued = datetime.strptime(query["X-Amz-Date"][0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            seconds = int(query["X-Amz-Expires"][0])
        except (ValueError, TypeError) as exc:
            raise ArtifactHold("artifact redirect expiry is invalid; HOLD") from exc
        if not 0 < seconds <= 7 * 24 * 60 * 60:
            raise ArtifactHold("artifact redirect expiry is invalid; HOLD")
        return issued + timedelta(seconds=seconds)
    raise ArtifactHold("artifact redirect expiry is missing; HOLD")


def validate_signed_url(url: str, now: datetime | None = None) -> None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expiry = _signed_url_expiry(url)
    if expiry <= now:
        raise ArtifactHold("artifact redirect is expired; HOLD")
    if expiry > now + timedelta(days=1):
        raise ArtifactHold("artifact redirect lifetime is unbounded; HOLD")


def _stream_response(response, dest: Path, expected_size: int) -> dict:
    declared = response.headers.get("Content-Length")
    if declared is not None:
        try:
            declared_size = int(declared)
        except ValueError as exc:
            raise ArtifactHold("invalid artifact Content-Length; HOLD") from exc
        if declared_size != expected_size:
            raise ArtifactHold("artifact Content-Length identity mismatch; HOLD")
    temp = dest.with_name(dest.name + ".part")
    temp.unlink(missing_ok=True)
    digest = hashlib.sha256()
    received = 0
    try:
        with temp.open("xb") as output:
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                received += len(chunk)
                if received > expected_size or received > MAX_ARTIFACT_BYTES:
                    raise ArtifactHold("artifact transfer exceeded its verified size; HOLD")
                digest.update(chunk)
                output.write(chunk)
        if received != expected_size:
            raise ArtifactHold("artifact transfer is incomplete or has wrong identity; HOLD")
        os.replace(temp, dest)
    except Exception:
        temp.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise
    return {"downloaded_bytes": received, "archive_sha256": digest.hexdigest()}


def download_signed_url(url: str, dest: Path, expected_size: int) -> dict:
    validate_signed_url(url)
    req = Request(url, headers={"User-Agent": "f1-elite-weekend-engine-v2"})
    try:
        with urlopen(req, timeout=600) as response:
            final_url = response.geturl() if hasattr(response, "geturl") else url
            if final_url != url:
                raise ArtifactHold("artifact storage redirected unexpectedly; HOLD")
            return _stream_response(response, dest, expected_size)
    except HTTPError as exc:
        dest.with_name(dest.name + ".part").unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise ArtifactHold(f"artifact storage returned HTTP {exc.code}; HOLD") from exc


def _cache_identity_path(dest: Path) -> Path:
    return dest.with_name(dest.name + ".identity.json")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reuse_verified_cache(
    artifact: dict, repo: str, verified_workflow_run: dict, dest: Path
) -> dict | None:
    identity_path = _cache_identity_path(dest)
    if not dest.exists() and not identity_path.exists():
        return None
    if not dest.is_file() or not identity_path.is_file():
        raise ArtifactHold("artifact cache is incomplete; HOLD")
    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactHold("artifact cache identity is invalid; HOLD") from exc
    expected = {
        "repository": repo,
        "artifact_id": artifact["id"],
        "artifact_name": artifact["name"],
        "archive_download_url": artifact["archive_download_url"],
        "size_in_bytes": artifact["size_in_bytes"],
        "created_at": artifact["created_at"],
        "updated_at": artifact["updated_at"],
        "workflow_run": artifact.get("workflow_run"),
        "verified_workflow_run": verified_workflow_run,
    }
    if not isinstance(identity, dict) or any(identity.get(key) != value for key, value in expected.items()):
        raise ArtifactHold("artifact cache identity mismatch; HOLD")
    if dest.stat().st_size != artifact["size_in_bytes"]:
        raise ArtifactHold("artifact cache size mismatch; HOLD")
    actual_sha = _file_sha256(dest)
    if identity.get("archive_sha256") != actual_sha:
        raise ArtifactHold("artifact cache digest mismatch; HOLD")
    return {
        "downloaded_bytes": artifact["size_in_bytes"],
        "archive_sha256": actual_sha,
        "cache_reused": True,
    }


def write_cache_identity(
    artifact: dict, repo: str, verified_workflow_run: dict, dest: Path, transfer: dict
) -> None:
    identity = {
        "repository": repo,
        "artifact_id": artifact["id"],
        "artifact_name": artifact["name"],
        "archive_download_url": artifact["archive_download_url"],
        "size_in_bytes": artifact["size_in_bytes"],
        "created_at": artifact["created_at"],
        "updated_at": artifact["updated_at"],
        "workflow_run": artifact.get("workflow_run"),
        "verified_workflow_run": verified_workflow_run,
        "archive_sha256": transfer["archive_sha256"],
    }
    path = _cache_identity_path(dest)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(identity, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def gh_download_artifact(
    artifact: dict, profile: str, repo: str, token: str, dest: Path
) -> dict:
    verified_workflow_run = verify_originating_workflow_run(artifact, profile, repo, token)
    cached = reuse_verified_cache(artifact, repo, verified_workflow_run, dest)
    if cached is not None:
        cached["verified_workflow_run"] = verified_workflow_run
        return cached
    archive_url = artifact["archive_download_url"]
    signed_url = get_artifact_redirect_url(archive_url, token)
    transfer = download_signed_url(signed_url, dest, artifact["size_in_bytes"])
    transfer["verified_workflow_run"] = verified_workflow_run
    return transfer


def list_artifacts(repo: str, token: str):
    artifacts = []
    for page in range(1, 11):
        url = f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100&page={page}"
        data = gh_get_json(url, token)
        if not isinstance(data, dict) or not isinstance(data.get("artifacts"), list):
            raise ArtifactHold("GitHub artifact listing is invalid; HOLD")
        batch = data["artifacts"]
        artifacts.extend(batch)
        if len(batch) < 100:
            break
    return artifacts


def pick_latest(artifacts, prefixes, repo=None):
    matches = [
        artifact for artifact in artifacts
        if isinstance(artifact, dict) and isinstance(artifact.get("name"), str)
        and _artifact_name_matches(artifact["name"], prefixes)
        and artifact.get("expired") is not True
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
    target = matches[0]
    return validate_artifact(target, repo, prefixes) if repo else target


def extract_validated_zip(zip_path: Path, profile_dir: Path) -> None:
    staging = profile_dir.with_name("." + profile_dir.name + ".extracting")
    previous = profile_dir.with_name("." + profile_dir.name + ".previous")
    if staging.exists() or previous.exists():
        raise ArtifactHold("artifact extraction destination is not clean; HOLD")
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            if not members or len(members) > MAX_ZIP_MEMBERS:
                raise ArtifactHold("artifact ZIP member count is invalid; HOLD")
            names = set()
            total = 0
            for info in members:
                path = PurePosixPath(info.filename)
                mode = info.external_attr >> 16
                if (
                    not info.filename or "\\" in info.filename or path.is_absolute()
                    or ".." in path.parts or info.filename in names or stat.S_ISLNK(mode)
                    or info.flag_bits & 0x1
                ):
                    raise ArtifactHold("artifact ZIP contains an unsafe member; HOLD")
                names.add(info.filename)
                total += info.file_size
                if total > MAX_EXTRACTED_BYTES:
                    raise ArtifactHold("artifact ZIP exceeds extraction limit; HOLD")
            corrupt = archive.testzip()
            if corrupt is not None:
                raise ArtifactHold("artifact ZIP integrity check failed; HOLD")
            for info in members:
                destination = staging.joinpath(*PurePosixPath(info.filename).parts)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output, DOWNLOAD_CHUNK_BYTES)
        if profile_dir.exists():
            os.replace(profile_dir, previous)
        try:
            os.replace(staging, profile_dir)
        except Exception:
            if previous.exists() and not profile_dir.exists():
                os.replace(previous, profile_dir)
            raise
        shutil.rmtree(previous, ignore_errors=True)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def write_manifest(manifest_path: Path, rows: list[dict], repo: str, error: str = ""):
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "repository": repo,
        "error": error, "hold": bool(error), "source_ready": False,
        "forecast_eligible": False,
        "event_session_provenance_verified": False,
        "event_session_provenance_status": EVENT_SESSION_PROVENANCE_STATUS,
        "profiles": rows,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    csv_path = manifest_path.with_suffix(".csv")
    headers = [
        "profile", "found", "artifact_id", "artifact_name", "created_at", "updated_at",
        "size_in_bytes", "workflow_run_id", "workflow_run_head_sha", "workflow_path",
        "workflow_run_attempt", "originating_workflow_run_verified",
        "event_session_provenance_status", "downloaded_bytes", "archive_sha256",
        "status", "extracted_to", "quarantined_to",
    ]
    lines = [",".join(headers)]
    for row in rows:
        def clean(value):
            return f'"{str(value).replace(chr(34), chr(34) * 2)}"'
        lines.append(",".join(clean(row.get(header, "")) for header in headers))
    csv_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--include-post-race-warning", action="store_true")
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise SystemExit("GITHUB_REPOSITORY is not set to owner/repository.")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set.")
    out = Path(args.output_dir)
    downloads = out / "downloads"
    manifests = out / "manifests"
    downloads.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    rows = []
    manifest_path = manifests / "elite_artifact_source_manifest.json"
    artifacts = list_artifacts(repo, token)
    for profile, prefixes in PROFILES.items():
        row = {
            "profile": profile, "prefixes": ";".join(prefixes), "found": False,
            "artifact_id": "", "artifact_name": "", "created_at": "", "updated_at": "",
            "size_in_bytes": "", "downloaded_bytes": "", "archive_sha256": "",
            "workflow_run_id": "", "workflow_run_head_sha": "", "workflow_path": "",
            "workflow_run_attempt": "",
            "downloaded_to": "", "extracted_to": "", "quarantined_to": "",
            "status": "MISSING", "verified": False, "source_ready": False,
            "forecast_eligible": False, "originating_workflow_run_verified": False,
            "event_session_provenance_verified": False,
            "event_session_provenance_status": EVENT_SESSION_PROVENANCE_STATUS,
        }
        try:
            target = pick_latest(artifacts, prefixes, repo=repo)
            if target is None:
                rows.append(row)
                continue
            row.update({
                "found": True, "artifact_id": str(target["id"]), "artifact_name": target["name"],
                "created_at": target["created_at"], "updated_at": target["updated_at"],
                "size_in_bytes": str(target["size_in_bytes"]),
            })
            zip_path = downloads / f"{profile}_{target['id']}.zip"
            transfer = gh_download_artifact(target, profile, repo, token, zip_path)
            quarantine_path = out / "quarantine" / profile
            extract_validated_zip(zip_path, quarantine_path)
            if not transfer.get("cache_reused"):
                write_cache_identity(
                    target, repo, transfer["verified_workflow_run"], zip_path, transfer
                )
            row.update(transfer)
            verified_run = transfer["verified_workflow_run"]
            row.update({
                "found": False,
                "downloaded_to": str(zip_path),
                "quarantined_to": str(quarantine_path),
                "status": EVENT_SESSION_PROVENANCE_STATUS,
                "verified": False,
                "originating_workflow_run_verified": True,
                "workflow_run_id": str(verified_run["id"]),
                "workflow_run_head_sha": verified_run["head_sha"],
                "workflow_path": verified_run["path"],
                "workflow_run_attempt": str(verified_run["run_attempt"]),
            })
            raise ArtifactHold(EVENT_SESSION_PROVENANCE_HOLD)
        except Exception as exc:
            row["status"] = f"HOLD: {type(exc).__name__}: {exc}"
            rows.append(row)
            write_manifest(manifest_path, rows, repo, error=str(exc))
            raise
        rows.append(row)
    write_manifest(manifest_path, rows, repo)
    found_count = sum(row["status"] == "DOWNLOADED" for row in rows)
    print(f"Downloaded {found_count}/{len(rows)} OpenF1 artifact profiles.")
    print(manifest_path)
    if found_count == 0:
        write_manifest(manifest_path, rows, repo, error="No OpenF1 artifacts downloaded; HOLD")
        raise SystemExit("No OpenF1 artifacts downloaded; cannot run Elite Weekend Engine v2.")


if __name__ == "__main__":
    main()
