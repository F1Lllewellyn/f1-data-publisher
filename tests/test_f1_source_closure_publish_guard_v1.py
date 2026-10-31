"""Adversarial offline tests for the source-closure publication guard."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "scripts/ops/f1_source_closure_publish_guard_v1.py"
WORKFLOW_PATH = ROOT / ".github/workflows/f1-openf1-lightweight-source-closure.yml"
spec = importlib.util.spec_from_file_location("source_publish_guard", GUARD_PATH)
guard = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)


BASELINE_WORKFLOW_BLOB = "6768b09449905cd61281386d6fc147f0fa18d01c"
COLLECTOR_PATH = "scripts/openf1/publish_openf1_lightweight_source_closure.py"
APPROVED_COLLECTOR_BLOBS = (
    "dbbc36dc01737084f2b1ff332e26c6c270be0049",
    "851625a5c333afc65f330e823d943c80b7b77121",
    "e23f016ef4d40e69a39d33cc0efe43572fdd16f8",
)
OLD_PUBLICATION = '''        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add latest/openf1_lightweight_source_closure history/openf1_lightweight_source_closure || true
          if git diff --cached --quiet; then
            echo "No source-closure changes to commit."
          else
            git commit -m "Update OpenF1 lightweight source closure artifacts"
            bash scripts/ops/safe_git_push_rebase_retry.sh


          fi
'''
NEW_PUBLICATION = '''        run: |
          set -euo pipefail
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          python scripts/ops/f1_source_closure_publish_guard_v1.py \\
            --repo-root "$GITHUB_WORKSPACE" \\
            --remote origin \\
            --branch "$GITHUB_REF_NAME" \\
            --expected-season "${{ github.event.inputs.season || '2026' }}" \\
            --expected-completed-only "${{ github.event.inputs.completed_only || 'true' }}" \\
            --github-run-id "$GITHUB_RUN_ID" \\
            --artifact-uploaded-for-run "$GITHUB_RUN_ID"
'''


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and completed.returncode:
        raise AssertionError(f"git failed ({completed.returncode}): {args}\n{completed.stdout}")
    return completed


def git_blob_sha(payload: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    ).hexdigest()


def immutable_git_blob(root: Path, blob_sha: str) -> bytes:
    completed = subprocess.run(
        ["git", "cat-file", "blob", blob_sha],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise AssertionError(
            "HOLD_MISSING_HISTORICAL_OBJECT: "
            f"required collector blob {blob_sha} is unavailable"
        )
    actual = git_blob_sha(completed.stdout)
    if actual != blob_sha:
        raise AssertionError(
            f"immutable collector object identity mismatch: {actual} != {blob_sha}"
        )
    return completed.stdout


def require_approved_collector(payload: bytes) -> str:
    actual = git_blob_sha(payload)
    if actual not in APPROVED_COLLECTOR_BLOBS:
        raise AssertionError(f"unrecognized collector blob: {actual}")
    return actual


def configure(root: Path) -> None:
    git(root, "config", "user.name", "Issue 327 Offline Test")
    git(root, "config", "user.email", "issue327@example.invalid")


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        return list(reader.fieldnames), list(reader)


def zip_tree(root: Path) -> None:
    archive = root / guard.ZIP_NAME
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path != archive:
                bundle.write(path, path.relative_to(root).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (root / guard.ZIP_SHA_NAME).write_text(
        f"{digest}  {guard.ZIP_NAME}\n", encoding="utf-8"
    )


def refresh_history_from_latest(repo: Path) -> None:
    latest = repo.joinpath(*guard.LATEST_REL.parts)
    manifest = json.loads((latest / "latest_manifest.json").read_text(encoding="utf-8"))
    history = repo / manifest["history_path"]
    for name in (guard.ZIP_NAME, guard.ZIP_SHA_NAME):
        path = latest / name
        if path.exists():
            path.unlink()
    zip_tree(latest)
    shutil.rmtree(history)
    history.mkdir(parents=True)
    for name in guard.TRACKED_FILES - {guard.ZIP_SHA_NAME}:
        target = history / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(latest / name, target)
    zip_tree(history)


def write_snapshot(
    repo: Path,
    *,
    generated: dt.datetime,
    history_stamp: str,
    marker: str,
    previous: dt.datetime | None,
    session_count: int = 1,
) -> Path:
    if session_count < 1:
        raise AssertionError("fixture requires at least one completed session")
    latest = repo.joinpath(*guard.LATEST_REL.parts)
    history = repo / "history/openf1_lightweight_source_closure" / history_stamp
    latest.mkdir(parents=True, exist_ok=True)
    history.mkdir(parents=True, exist_ok=False)
    observed = generated - dt.timedelta(minutes=1)
    sessions = []
    for index in range(session_count):
        session_start = dt.datetime(2026, 10, 24, 6, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=index)
        sessions.append(
            {
                "session_key": str(11392 + index),
                "session_type": "Qualifying" if index == 0 else "Practice",
                "session_name": "Qualifying" if index == 0 else f"Practice {index}",
                "date_start": iso(session_start),
                "date_end": iso(session_start + dt.timedelta(minutes=1)),
                "meeting_key": str(1297 + index),
                "circuit_key": "9",
                "circuit_short_name": "Austin",
                "country_key": "19",
                "country_code": "USA",
                "country_name": "United States",
                "location": "Austin",
                "gmt_offset": "-05:00:00",
                "year": "2026",
                "is_cancelled": "False",
                "_completed_session": "True",
            }
        )
    target_fields = list(sessions[0])
    readiness = []
    source_manifest = []
    for lane in guard.LANES:
        relative = f"data/openf1_{lane}.csv"
        rows = [
            {
                "session_key": session["session_key"],
                "meeting_key": session["meeting_key"],
                "source_closure_retrieved_utc": iso(observed),
                "fixture_value": f"{marker}-{lane}-{index}",
            }
            for index, session in enumerate(sessions)
        ]
        write_csv(latest / relative, list(rows[0]), rows)
        result = {
            "lane": lane,
            "rows": session_count,
            "result": "pass",
            "reason": "evidence_bearing",
            "required_status": "opportunistic" if lane == "team_radio" else "required_lightweight",
            "heavy_endpoint": False,
        }
        readiness.append(result)
        source_manifest.append(
            {
                "path": relative,
                "lane": lane,
                "rows": session_count,
                "sha256": hashlib.sha256((latest / relative).read_bytes()).hexdigest(),
                "result": "pass",
                "reason": "evidence_bearing",
            }
        )
    write_csv(latest / "data/target_sessions.csv", target_fields, sessions)
    write_csv(
        latest / "combined_source_manifest.csv",
        ["path", "lane", "rows", "sha256", "result", "reason"],
        source_manifest,
    )
    write_csv(
        latest / "source_readiness_summary.csv",
        ["lane", "rows", "result", "reason", "required_status", "heavy_endpoint"],
        readiness,
    )
    write_csv(
        latest / "request_log.csv",
        ["timestamp_utc", "endpoint", "status"],
        [{"timestamp_utc": iso(observed), "endpoint": "sessions", "status": "pass"}],
    )
    write_csv(
        latest / "zero_lane_diagnostics.csv",
        ["lane", "session_key", "meeting_key", "rows"],
        [
            {
                "lane": lane,
                "session_key": session["session_key"],
                "meeting_key": session["meeting_key"],
                "rows": session_count,
            }
            for lane in guard.LANES
            for session in sessions
        ],
    )
    manifest = {
        "artifact_profile": guard.PROFILE,
        "generated_utc": iso(generated),
        "season": 2026,
        "completed_only": True,
        "target_session_count": session_count,
        "lanes": readiness,
        "pass_count": len(guard.LANES),
        "pass_with_warnings_count": 0,
        "fail_count": 0,
        "heavy_endpoints_excluded_by_default": ["car_data", "location"],
        "timestamp_policy": "dt.datetime.now(dt.UTC)",
        "no_drs_2026_assumption": True,
        "previous_manifest_generated_utc": iso(previous) if previous else None,
        "latest_zip": guard.ZIP_NAME,
        "history_path": f"history/openf1_lightweight_source_closure/{history_stamp}",
    }
    (latest / "latest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    readiness_payload = {"generated_utc": iso(generated + dt.timedelta(seconds=1)), "lanes": readiness}
    (latest / "data_readiness.json").write_text(json.dumps(readiness_payload, indent=2), encoding="utf-8")
    (latest / "source_closure_report.md").write_text(f"# Fixture\n\n{marker}\n", encoding="utf-8")
    (latest / "F1_OpenF1_Lightweight_Source_Closure_Summary.xlsx").write_bytes(
        b"PK\x03\x04" + marker.encode("ascii")
    )
    for name in guard.TRACKED_FILES - {guard.ZIP_SHA_NAME}:
        target = history / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(latest / name, target)
    zip_tree(latest)
    zip_tree(history)
    return history


def write_zero_session_401_snapshot(
    repo: Path,
    *,
    generated: dt.datetime,
    history_stamp: str,
    previous: dt.datetime,
    preserve_csv_headers: bool,
) -> Path:
    """Model the audited Austin HTTP-401 / 105-to-zero publisher output."""
    latest = repo.joinpath(*guard.LATEST_REL.parts)
    history = repo / "history/openf1_lightweight_source_closure" / history_stamp
    latest.mkdir(parents=True, exist_ok=True)
    history.mkdir(parents=True, exist_ok=False)
    target_fields = [
        "session_key",
        "session_type",
        "session_name",
        "date_start",
        "date_end",
        "meeting_key",
        "circuit_key",
        "circuit_short_name",
        "country_key",
        "country_code",
        "country_name",
        "location",
        "gmt_offset",
        "year",
        "is_cancelled",
        "_completed_session",
    ]
    if preserve_csv_headers:
        write_csv(latest / "data/target_sessions.csv", target_fields, [])
    else:
        (latest / "data/target_sessions.csv").write_bytes(b"\n")

    readiness = []
    source_manifest = []
    lane_fields = [
        "session_key",
        "meeting_key",
        "source_closure_retrieved_utc",
        "fixture_value",
    ]
    for lane in guard.LANES:
        relative = f"data/openf1_{lane}.csv"
        if preserve_csv_headers:
            write_csv(latest / relative, lane_fields, [])
        else:
            (latest / relative).parent.mkdir(parents=True, exist_ok=True)
            (latest / relative).write_bytes(b"\n")
        reason = (
            "opportunistic_source_limited_zero_rows"
            if lane == "team_radio"
            else "not_applicable_for_current_completed_sessions"
        )
        lane_state = {
            "lane": lane,
            "rows": 0,
            "result": "pass_with_warnings",
            "reason": reason,
            "required_status": "opportunistic" if lane == "team_radio" else "required_lightweight",
            "heavy_endpoint": False,
        }
        readiness.append(lane_state)
        source_manifest.append(
            {
                "path": relative,
                "lane": lane,
                "rows": 0,
                "sha256": hashlib.sha256((latest / relative).read_bytes()).hexdigest(),
                "result": "pass_with_warnings",
                "reason": reason,
            }
        )
    write_csv(
        latest / "combined_source_manifest.csv",
        ["path", "lane", "rows", "sha256", "result", "reason"],
        source_manifest,
    )
    write_csv(
        latest / "source_readiness_summary.csv",
        ["lane", "rows", "result", "reason", "required_status", "heavy_endpoint"],
        readiness,
    )
    write_csv(
        latest / "request_log.csv",
        [
            "timestamp_utc",
            "endpoint",
            "strategy",
            "params_json",
            "rows",
            "status",
            "error",
            "elapsed_seconds",
        ],
        [
            {
                "timestamp_utc": "2026-10-25T21:07:29.706628Z",
                "endpoint": "sessions",
                "strategy": "sessions_by_year",
                "params_json": '{"year": 2026}',
                "rows": 0,
                "status": "http_401",
                "error": "Live F1 session in progress; global API access restricted",
                "elapsed_seconds": "0.34",
            }
        ],
    )
    write_csv(
        latest / "zero_lane_diagnostics.csv",
        ["lane", "session_key", "meeting_key", "rows"],
        [
            {"lane": lane, "session_key": "", "meeting_key": "", "rows": 0}
            for lane in guard.LANES
        ],
    )
    manifest = {
        "artifact_profile": guard.PROFILE,
        "generated_utc": iso(generated),
        "season": 2026,
        "completed_only": True,
        "target_session_count": 0,
        "lanes": readiness,
        "pass_count": 0,
        "pass_with_warnings_count": len(guard.LANES),
        "fail_count": 0,
        "heavy_endpoints_excluded_by_default": ["car_data", "location"],
        "timestamp_policy": "dt.datetime.now(dt.UTC)",
        "no_drs_2026_assumption": True,
        "previous_manifest_generated_utc": iso(previous),
        "latest_zip": guard.ZIP_NAME,
        "history_path": f"history/openf1_lightweight_source_closure/{history_stamp}",
    }
    (latest / "latest_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (latest / "data_readiness.json").write_text(
        json.dumps(
            {
                "generated_utc": iso(generated + dt.timedelta(seconds=1)),
                "lanes": readiness,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (latest / "source_closure_report.md").write_text(
        "# Fixture\n\nAustin audited HTTP 401; zero target sessions.\n",
        encoding="utf-8",
    )
    (latest / "F1_OpenF1_Lightweight_Source_Closure_Summary.xlsx").write_bytes(
        b"PK\x03\x04austin-http-401-zero-session"
    )
    for name in (guard.ZIP_NAME, guard.ZIP_SHA_NAME):
        path = latest / name
        if path.exists():
            path.unlink()
    zip_tree(latest)
    for name in guard.TRACKED_FILES - {guard.ZIP_SHA_NAME}:
        target = history / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(latest / name, target)
    zip_tree(history)
    return history


class GitFixture:
    def __init__(self, directory: str):
        self.root = Path(directory)
        self.remote = self.root / "remote.git"
        self.seed = self.root / "seed"
        git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        git(self.root, "init", "--initial-branch=main", str(self.seed))
        configure(self.seed)
        (self.seed / ".gitignore").write_text("*.zip\n", encoding="utf-8")
        (self.seed / "unrelated.txt").write_text("baseline\n", encoding="utf-8")
        baseline = dt.datetime(2026, 10, 24, 10, tzinfo=dt.timezone.utc)
        write_snapshot(
            self.seed,
            generated=baseline,
            history_stamp="20261024_095000",
            marker="baseline",
            previous=None,
        )
        git(self.seed, "add", ".")
        git(self.seed, "commit", "-m", "baseline")
        git(self.seed, "remote", "add", "origin", str(self.remote))
        git(self.seed, "push", "-u", "origin", "main")
        self.baseline = baseline

    def clone(self, name: str) -> Path:
        target = self.root / name
        git(self.root, "clone", str(self.remote), str(target))
        configure(target)
        return target

    def remote_text(self, path: str) -> str:
        return git(self.root, "--git-dir", str(self.remote), "show", f"main:{path}").stdout

    def remote_bytes(self, path: str) -> bytes:
        return subprocess.run(
            ["git", "--git-dir", str(self.remote), "show", f"main:{path}"],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout


class PublicationGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = GitFixture(self.temp.name)
        self.now = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)

    def candidate(
        self,
        name: str,
        hour: int,
        stamp: str,
        marker: str,
        *,
        session_count: int = 1,
    ) -> Path:
        repo = self.fixture.clone(name)
        write_snapshot(
            repo,
            generated=dt.datetime(2026, 10, 24, hour, tzinfo=dt.timezone.utc),
            history_stamp=stamp,
            marker=marker,
            previous=self.fixture.baseline,
            session_count=session_count,
        )
        return repo

    def run_guard(self, repo: Path, **kwargs):
        return guard.run_guard(
            repo_root=repo,
            remote="origin",
            branch="main",
            expected_season=2026,
            expected_completed_only=True,
            github_run_id="40125611266",
            artifact_uploaded_for_run="40125611266",
            clock=lambda: self.now,
            **kwargs,
        )

    def push_competing_snapshot(
        self,
        hour: int,
        stamp: str,
        marker: str,
        *,
        session_count: int = 1,
    ) -> Path:
        competing = self.fixture.clone(f"competing-{marker}")
        write_snapshot(
            competing,
            generated=dt.datetime(2026, 10, 24, hour, tzinfo=dt.timezone.utc),
            history_stamp=stamp,
            marker=marker,
            previous=self.fixture.baseline,
            session_count=session_count,
        )
        git(competing, "add", ".")
        git(competing, "commit", "-m", f"competing {marker}")
        git(competing, "push", "origin", "main")
        return competing

    def remote_head(self) -> str:
        return git(
            self.fixture.root,
            "--git-dir",
            str(self.fixture.remote),
            "rev-parse",
            "main",
        ).stdout.strip()

    def push_remote_mutation(self, repo: Path, message: str, *paths: Path) -> None:
        git(repo, "add", *(path.relative_to(repo).as_posix() for path in paths))
        git(repo, "commit", "-m", message)
        git(repo, "push", "origin", "main")

    def candidate_evidence(self, candidate: Path) -> tuple[bytes, bytes]:
        latest = candidate.joinpath(*guard.LATEST_REL.parts)
        manifest = json.loads((latest / "latest_manifest.json").read_text(encoding="utf-8"))
        history = candidate / manifest["history_path"]
        return (
            (latest / guard.ZIP_NAME).read_bytes(),
            (history / "latest_manifest.json").read_bytes(),
        )

    def test_unrelated_remote_movement_is_retained(self):
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        other = self.fixture.clone("other")
        (other / "unrelated.txt").write_text("advanced\n", encoding="utf-8")
        git(other, "add", "unrelated.txt")
        git(other, "commit", "-m", "unrelated movement")
        git(other, "push", "origin", "main")
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "PUBLISHED_LATEST_AND_HISTORY", result)
        self.assertEqual(self.fixture.remote_text("unrelated.txt"), "advanced\n")
        self.assertEqual(result["publication"]["push_attempts"], 1)

    def test_same_path_remote_older_is_replaced_whole_without_merge(self):
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        self.push_competing_snapshot(11, "20261024_105000", "competing")
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "PUBLISHED_LATEST_AND_HISTORY", result)
        workbook = self.fixture.remote_bytes(
            "latest/openf1_lightweight_source_closure/F1_OpenF1_Lightweight_Source_Closure_Summary.xlsx"
        )
        self.assertEqual(workbook, b"PK\x03\x04candidate")
        self.assertIn("2026-10-24T12:00:00Z", self.fixture.remote_text(
            "latest/openf1_lightweight_source_closure/latest_manifest.json"
        ))

    def test_newer_remote_blocks_stale_latest_but_preserves_candidate_history(self):
        candidate = self.candidate("candidate", 11, "20261024_105000", "candidate")
        self.push_competing_snapshot(12, "20261024_115000", "newer")
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "PUBLISHED_HISTORY_ONLY", result)
        self.assertEqual(result["publication"]["latest_decision"], "PRESERVE_NEWER_REMOTE_LATEST")
        self.assertTrue(result["remote"]["tracked_data_integrity_validated"])
        self.assertFalse(result["remote"]["zip_integrity_validated"])
        latest = self.fixture.remote_text("latest/openf1_lightweight_source_closure/latest_manifest.json")
        self.assertIn("2026-10-24T12:00:00Z", latest)
        history = self.fixture.remote_text(
            "history/openf1_lightweight_source_closure/20261024_105000/latest_manifest.json"
        )
        self.assertIn("2026-10-24T11:00:00Z", history)

    def test_newer_remote_with_invalid_source_hash_holds_without_push(self):
        candidate = self.candidate("candidate", 11, "20261024_105000", "candidate")
        evidence_before = self.candidate_evidence(candidate)
        remote = self.push_competing_snapshot(12, "20261024_115000", "remote")
        source_manifest = remote.joinpath(*guard.LATEST_REL.parts) / "combined_source_manifest.csv"
        fields, rows = read_csv(source_manifest)
        next(row for row in rows if row["lane"] == "weather")["sha256"] = "0" * 64
        write_csv(source_manifest, fields, rows)
        self.push_remote_mutation(remote, "invalidate remote source hash", source_manifest)
        remote_before = self.remote_head()
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "remote_latest_invalid:source_manifest_sha_mismatch")
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(self.remote_head(), remote_before)
        self.assertEqual(self.candidate_evidence(candidate), evidence_before)

    def test_newer_remote_with_truncated_lane_holds_without_push(self):
        candidate = self.candidate("candidate", 11, "20261024_105000", "candidate")
        remote = self.push_competing_snapshot(12, "20261024_115000", "remote")
        latest = remote.joinpath(*guard.LATEST_REL.parts)
        weather = latest / "data/openf1_weather.csv"
        fields, _rows = read_csv(weather)
        write_csv(weather, fields, [])
        source_manifest = latest / "combined_source_manifest.csv"
        manifest_fields, manifest_rows = read_csv(source_manifest)
        next(row for row in manifest_rows if row["lane"] == "weather")["sha256"] = hashlib.sha256(
            weather.read_bytes()
        ).hexdigest()
        write_csv(source_manifest, manifest_fields, manifest_rows)
        self.push_remote_mutation(remote, "truncate remote lane with matching hash", weather, source_manifest)
        remote_before = self.remote_head()
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "remote_latest_invalid:lane_csv_row_count_mismatch")
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(self.remote_head(), remote_before)

    def test_newer_remote_with_cross_session_lane_holds_without_push(self):
        candidate = self.candidate("candidate", 11, "20261024_105000", "candidate")
        remote = self.push_competing_snapshot(12, "20261024_115000", "remote")
        latest = remote.joinpath(*guard.LATEST_REL.parts)
        weather = latest / "data/openf1_weather.csv"
        fields, rows = read_csv(weather)
        rows[0]["session_key"] = "99999"
        write_csv(weather, fields, rows)
        source_manifest = latest / "combined_source_manifest.csv"
        manifest_fields, manifest_rows = read_csv(source_manifest)
        next(row for row in manifest_rows if row["lane"] == "weather")["sha256"] = hashlib.sha256(
            weather.read_bytes()
        ).hexdigest()
        write_csv(source_manifest, manifest_fields, manifest_rows)
        self.push_remote_mutation(remote, "cross-bind remote lane session", weather, source_manifest)
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "remote_latest_invalid:lane_session_identity_mismatch")
        self.assertEqual(result["publication"]["push_attempts"], 0)

    def test_newer_remote_with_missing_target_identity_holds_without_push(self):
        candidate = self.candidate("candidate", 11, "20261024_105000", "candidate")
        remote = self.push_competing_snapshot(12, "20261024_115000", "remote")
        targets = remote.joinpath(*guard.LATEST_REL.parts) / "data/target_sessions.csv"
        fields, rows = read_csv(targets)
        rows[0]["session_name"] = ""
        write_csv(targets, fields, rows)
        self.push_remote_mutation(remote, "remove remote session identity", targets)
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "remote_latest_invalid:target_session_identity_missing")
        self.assertEqual(result["publication"]["push_attempts"], 0)

    def test_newer_candidate_cannot_remove_completed_session_coverage(self):
        self.push_competing_snapshot(11, "20261024_105000", "remote-105", session_count=105)
        candidate = self.candidate(
            "candidate", 12, "20261024_115000", "candidate-104", session_count=104
        )
        evidence_before = self.candidate_evidence(candidate)
        remote_before = self.remote_head()
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "candidate_completed_session_coverage_regression:11496")
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(self.remote_head(), remote_before)
        self.assertEqual(self.candidate_evidence(candidate), evidence_before)
        remote_manifest = json.loads(self.fixture.remote_text(
            "latest/openf1_lightweight_source_closure/latest_manifest.json"
        ))
        self.assertEqual(remote_manifest["target_session_count"], 105)

    def test_exact_austin_http401_blank_csv_snapshot_holds_before_publication(self):
        remote_generated = dt.datetime(2026, 10, 25, 19, 13, 4, tzinfo=dt.timezone.utc)
        remote = self.fixture.clone("remote-austin-105")
        write_snapshot(
            remote,
            generated=remote_generated,
            history_stamp="20261025_185347",
            marker="austin-authoritative-105",
            previous=self.fixture.baseline,
            session_count=105,
        )
        git(remote, "add", ".")
        git(remote, "commit", "-m", "authoritative Austin 105-session snapshot")
        git(remote, "push", "origin", "main")

        candidate = self.fixture.clone("candidate-austin-http401-exact")
        write_zero_session_401_snapshot(
            candidate,
            generated=dt.datetime(2026, 10, 25, 21, 7, 29, 967737, tzinfo=dt.timezone.utc),
            history_stamp="20261025_210729",
            previous=remote_generated,
            preserve_csv_headers=False,
        )
        self.now = dt.datetime(2026, 10, 25, 22, tzinfo=dt.timezone.utc)
        evidence_before = self.candidate_evidence(candidate)
        remote_before = self.remote_head()
        result = self.run_guard(candidate)

        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "target_sessions_identity_columns_missing")
        self.assertIsNone(result["candidate"])
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(self.remote_head(), remote_before)
        self.assertEqual(self.candidate_evidence(candidate), evidence_before)
        request_log = (candidate.joinpath(*guard.LATEST_REL.parts) / "request_log.csv").read_text()
        self.assertIn("2026-10-25T21:07:29.706628Z", request_log)
        self.assertIn("http_401", request_log)
        remote_manifest = json.loads(self.fixture.remote_text(
            "latest/openf1_lightweight_source_closure/latest_manifest.json"
        ))
        self.assertEqual(remote_manifest["target_session_count"], 105)

    def test_structurally_complete_http401_zero_candidate_still_cannot_replace_105_sessions(self):
        remote_generated = dt.datetime(2026, 10, 25, 19, 13, 4, tzinfo=dt.timezone.utc)
        remote = self.fixture.clone("remote-austin-105")
        write_snapshot(
            remote,
            generated=remote_generated,
            history_stamp="20261025_185347",
            marker="austin-authoritative-105",
            previous=self.fixture.baseline,
            session_count=105,
        )
        git(remote, "add", ".")
        git(remote, "commit", "-m", "authoritative Austin 105-session snapshot")
        git(remote, "push", "origin", "main")

        candidate = self.fixture.clone("candidate-austin-http401-zero")
        write_zero_session_401_snapshot(
            candidate,
            generated=dt.datetime(2026, 10, 25, 21, 7, 29, 967737, tzinfo=dt.timezone.utc),
            history_stamp="20261025_210729",
            previous=remote_generated,
            preserve_csv_headers=True,
        )
        self.now = dt.datetime(2026, 10, 25, 22, tzinfo=dt.timezone.utc)
        evidence_before = self.candidate_evidence(candidate)
        remote_before = self.remote_head()
        result = self.run_guard(candidate)

        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "candidate_completed_session_coverage_regression:11392")
        self.assertEqual(result["candidate"]["target_session_count"], 0)
        self.assertEqual(result["remote"]["target_session_count"], 105)
        self.assertIsNone(result["publication"]["latest_decision"])
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(self.remote_head(), remote_before)
        self.assertEqual(self.candidate_evidence(candidate), evidence_before)
        request_log = (candidate.joinpath(*guard.LATEST_REL.parts) / "request_log.csv").read_text()
        self.assertIn("sessions_by_year", request_log)
        self.assertIn("http_401", request_log)
        remote_manifest = json.loads(self.fixture.remote_text(
            "latest/openf1_lightweight_source_closure/latest_manifest.json"
        ))
        self.assertEqual(remote_manifest["target_session_count"], 105)

    def test_newer_candidate_cannot_change_existing_meeting_identity(self):
        self.push_competing_snapshot(11, "20261024_105000", "remote")
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        latest = candidate.joinpath(*guard.LATEST_REL.parts)
        targets = latest / "data/target_sessions.csv"
        target_fields, target_rows = read_csv(targets)
        target_rows[0]["meeting_key"] = "7777"
        write_csv(targets, target_fields, target_rows)
        source_manifest = latest / "combined_source_manifest.csv"
        manifest_fields, manifest_rows = read_csv(source_manifest)
        for lane in guard.LANES:
            lane_path = latest / f"data/openf1_{lane}.csv"
            lane_fields, lane_rows = read_csv(lane_path)
            lane_rows[0]["meeting_key"] = "7777"
            write_csv(lane_path, lane_fields, lane_rows)
            next(row for row in manifest_rows if row["lane"] == lane)["sha256"] = hashlib.sha256(
                lane_path.read_bytes()
            ).hexdigest()
        write_csv(source_manifest, manifest_fields, manifest_rows)
        refresh_history_from_latest(candidate)
        remote_before = self.remote_head()
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "candidate_existing_session_identity_changed:11392")
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(self.remote_head(), remote_before)

    def test_newer_candidate_with_additional_completed_session_publishes(self):
        self.push_competing_snapshot(11, "20261024_105000", "remote-104", session_count=104)
        candidate = self.candidate(
            "candidate", 12, "20261024_115000", "candidate-105", session_count=105
        )
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "PUBLISHED_LATEST_AND_HISTORY", result)
        self.assertEqual(result["publication"]["latest_decision"], "PUBLISH_CANDIDATE_LATEST")
        self.assertEqual(result["publication"]["push_attempts"], 1)
        remote_manifest = json.loads(self.fixture.remote_text(
            "latest/openf1_lightweight_source_closure/latest_manifest.json"
        ))
        self.assertEqual(remote_manifest["target_session_count"], 105)

    def test_newer_candidate_can_legitimately_reduce_lane_rows_without_losing_sessions(self):
        remote = self.candidate("remote", 11, "20261024_105000", "remote")
        latest = remote.joinpath(*guard.LATEST_REL.parts)
        weather = latest / "data/openf1_weather.csv"
        weather_fields, weather_rows = read_csv(weather)
        second = dict(weather_rows[0])
        second["fixture_value"] = "remote-correctable-second-row"
        write_csv(weather, weather_fields, [*weather_rows, second])
        source_manifest = latest / "combined_source_manifest.csv"
        source_fields, source_rows = read_csv(source_manifest)
        weather_source = next(row for row in source_rows if row["lane"] == "weather")
        weather_source["rows"] = "2"
        weather_source["sha256"] = hashlib.sha256(weather.read_bytes()).hexdigest()
        write_csv(source_manifest, source_fields, source_rows)
        manifest_path = latest / "latest_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        next(row for row in manifest["lanes"] if row["lane"] == "weather")["rows"] = 2
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        readiness_path = latest / "data_readiness.json"
        readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        next(row for row in readiness["lanes"] if row["lane"] == "weather")["rows"] = 2
        readiness_path.write_text(json.dumps(readiness, indent=2), encoding="utf-8")
        summary_path = latest / "source_readiness_summary.csv"
        summary_fields, summary_rows = read_csv(summary_path)
        next(row for row in summary_rows if row["lane"] == "weather")["rows"] = "2"
        write_csv(summary_path, summary_fields, summary_rows)
        refresh_history_from_latest(remote)
        git(remote, "add", ".")
        git(remote, "commit", "-m", "valid remote with two weather rows")
        git(remote, "push", "origin", "main")
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "PUBLISHED_LATEST_AND_HISTORY", result)
        self.assertEqual(result["publication"]["push_attempts"], 1)
        weather_after = self.fixture.remote_text(
            "latest/openf1_lightweight_source_closure/data/openf1_weather.csv"
        )
        self.assertNotIn("remote-correctable-second-row", weather_after)

    def test_equal_clock_different_bytes_holds_without_push(self):
        candidate = self.candidate("candidate", 12, "20261024_115001", "candidate")
        self.push_competing_snapshot(12, "20261024_115000", "different")
        before = git(self.fixture.root, "--git-dir", str(self.fixture.remote), "rev-parse", "main").stdout.strip()
        result = self.run_guard(candidate)
        after = git(self.fixture.root, "--git-dir", str(self.fixture.remote), "rev-parse", "main").stdout.strip()
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "equal_generation_clock_with_different_latest_bytes")
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(after, before)

    def test_final_push_race_holds_once_and_preserves_candidate(self):
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        racer = self.fixture.clone("racer")

        def race() -> None:
            (racer / "unrelated.txt").write_text("raced\n", encoding="utf-8")
            git(racer, "add", "unrelated.txt")
            git(racer, "commit", "-m", "racer")
            git(racer, "push", "origin", "main")

        candidate_manifest = candidate / guard.LATEST_REL.as_posix() / "latest_manifest.json"
        original = candidate_manifest.read_bytes()
        result = self.run_guard(candidate, before_push=race)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "push_rejected_after_freshness_decision")
        self.assertEqual(result["publication"]["push_attempts"], 1)
        self.assertFalse(result["publication"]["push_succeeded"])
        self.assertFalse(result["publication"]["force_push_used"])
        self.assertFalse(result["publication"]["retry_used"])
        self.assertEqual(candidate_manifest.read_bytes(), original)
        self.assertEqual(self.fixture.remote_text("unrelated.txt"), "raced\n")
        with self.assertRaises(AssertionError):
            self.fixture.remote_text(
                "history/openf1_lightweight_source_closure/20261024_115000/latest_manifest.json"
            )

    def test_prior_tracked_dirt_holds_before_fetch_or_push(self):
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        (candidate / "unrelated.txt").write_text("unexpected dirt\n", encoding="utf-8")
        before = git(self.fixture.root, "--git-dir", str(self.fixture.remote), "rev-parse", "main").stdout.strip()
        result = self.run_guard(candidate)
        after = git(self.fixture.root, "--git-dir", str(self.fixture.remote), "rev-parse", "main").stdout.strip()
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "unexpected_worktree_change:unrelated.txt")
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(after, before)

    def test_immutable_history_collision_holds(self):
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        collision = self.fixture.clone("collision")
        source = write_snapshot(
            collision,
            generated=dt.datetime(2026, 10, 24, 11, tzinfo=dt.timezone.utc),
            history_stamp="20261024_115000",
            marker="collision",
            previous=self.fixture.baseline,
        )
        latest = collision.joinpath(*guard.LATEST_REL.parts)
        shutil.rmtree(latest)
        git(collision, "restore", guard.LATEST_REL.as_posix())
        git(collision, "add", source.relative_to(collision).as_posix())
        git(collision, "commit", "-m", "history collision")
        git(collision, "push", "origin", "main")
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "immutable_history_path_collision")

    def test_unexpected_remote_latest_member_holds_before_replacement(self):
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        other = self.fixture.clone("other")
        extra = other.joinpath(*guard.LATEST_REL.parts) / "unexpected.txt"
        extra.write_text("must not be deleted\n", encoding="utf-8")
        git(other, "add", extra.relative_to(other).as_posix())
        git(other, "commit", "-m", "unexpected remote latest member")
        git(other, "push", "origin", "main")
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "remote_latest_invalid:remote_latest_file_set_invalid")
        self.assertEqual(result["publication"]["push_attempts"], 0)
        self.assertEqual(self.fixture.remote_text(extra.relative_to(other).as_posix()), "must not be deleted\n")

    def test_remote_latest_symlink_holds_before_replacement(self):
        candidate = self.candidate("candidate", 12, "20261024_115000", "candidate")
        other = self.fixture.clone("other")
        report = other.joinpath(*guard.LATEST_REL.parts) / "source_closure_report.md"
        report.unlink()
        report.symlink_to("latest_manifest.json")
        git(other, "add", report.relative_to(other).as_posix())
        git(other, "commit", "-m", "unsafe remote symlink")
        git(other, "push", "origin", "main")
        result = self.run_guard(candidate)
        self.assertEqual(result["status"], "HOLD", result)
        self.assertEqual(result["reason"], "remote_latest_invalid:remote_tree_mode_invalid")
        self.assertEqual(result["publication"]["push_attempts"], 0)


class CandidateValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = GitFixture(self.temp.name)
        self.repo = self.fixture.clone("candidate")
        self.generated = dt.datetime(2026, 10, 24, 12, tzinfo=dt.timezone.utc)
        self.history = write_snapshot(
            self.repo,
            generated=self.generated,
            history_stamp="20261024_115000",
            marker="candidate",
            previous=self.fixture.baseline,
        )
        self.latest = self.repo.joinpath(*guard.LATEST_REL.parts)
        self.now = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)

    def validate(self):
        return guard.validate_candidate(
            self.repo,
            expected_season=2026,
            expected_completed_only=True,
            now=self.now,
        )

    def test_valid_candidate_proves_session_identity_and_clocks(self):
        candidate = self.validate()
        self.assertEqual(candidate.history_rel.as_posix(), "history/openf1_lightweight_source_closure/20261024_115000")
        self.assertRegex(candidate.tree_sha256, r"^[0-9a-f]{64}$")

    def test_missing_session_name_fails_closed(self):
        fields, rows = read_csv(self.latest / "data/target_sessions.csv")
        rows[0]["session_name"] = ""
        write_csv(self.latest / "data/target_sessions.csv", fields, rows)
        with self.assertRaisesRegex(guard.PublicationHold, "target_session_identity_missing"):
            self.validate()

    def test_lane_cross_session_identity_fails_closed(self):
        path = self.latest / "data/openf1_weather.csv"
        fields, rows = read_csv(path)
        rows[0]["session_key"] = "99999"
        write_csv(path, fields, rows)
        manifest_fields, manifest_rows = read_csv(self.latest / "combined_source_manifest.csv")
        for row in manifest_rows:
            if row["lane"] == "weather":
                row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        write_csv(self.latest / "combined_source_manifest.csv", manifest_fields, manifest_rows)
        with self.assertRaisesRegex(guard.PublicationHold, "lane_session_identity_mismatch"):
            self.validate()

    def test_source_clock_after_generation_fails_closed(self):
        path = self.latest / "data/openf1_weather.csv"
        fields, rows = read_csv(path)
        rows[0]["source_closure_retrieved_utc"] = iso(self.generated + dt.timedelta(minutes=1))
        write_csv(path, fields, rows)
        manifest_fields, manifest_rows = read_csv(self.latest / "combined_source_manifest.csv")
        for row in manifest_rows:
            if row["lane"] == "weather":
                row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        write_csv(self.latest / "combined_source_manifest.csv", manifest_fields, manifest_rows)
        with self.assertRaisesRegex(guard.PublicationHold, "lane_source_clock_after_generation"):
            self.validate()

    def test_manifest_history_traversal_fails_closed(self):
        for root in (self.latest, self.history):
            manifest = json.loads((root / "latest_manifest.json").read_text())
            manifest["history_path"] = "history/openf1_lightweight_source_closure/../../outside"
            (root / "latest_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(guard.PublicationHold, "candidate_history_path_invalid"):
            self.validate()

    def test_dangling_symlink_fails_closed(self):
        path = self.latest / "request_log.csv"
        path.unlink()
        path.symlink_to(self.repo / "does-not-exist")
        with self.assertRaisesRegex(guard.PublicationHold, "candidate_latest_tree_unsafe"):
            self.validate()

    def test_zip_checksum_corruption_fails_closed(self):
        (self.latest / guard.ZIP_SHA_NAME).write_text("0" * 64 + f"  {guard.ZIP_NAME}\n", encoding="utf-8")
        with self.assertRaisesRegex(guard.PublicationHold, "zip_checksum_mismatch"):
            self.validate()

    def test_artifact_run_assertion_mismatch_holds_without_push(self):
        result = guard.run_guard(
            repo_root=self.repo,
            remote="origin",
            branch="main",
            expected_season=2026,
            expected_completed_only=True,
            github_run_id="40125611266",
            artifact_uploaded_for_run="999",
            clock=lambda: self.now,
        )
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "artifact_upload_precondition_invalid")
        self.assertEqual(result["publication"]["push_attempts"], 0)


class StaticScopeTests(unittest.TestCase):
    def test_workflow_reconstructs_exact_protected_baseline(self):
        current = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertEqual(current.count(NEW_PUBLICATION), 1)
        reconstructed = current.replace(NEW_PUBLICATION, OLD_PUBLICATION, 1).encode("utf-8")
        blob = hashlib.sha1(
            b"blob " + str(len(reconstructed)).encode("ascii") + b"\0" + reconstructed
        ).hexdigest()
        self.assertEqual(blob, BASELINE_WORKFLOW_BLOB)

    def test_dispatch_schema_and_manual_shadow_jobs_remain_protected(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        dispatch = text.split("  workflow_dispatch:\n", 1)[1].split("  schedule:\n", 1)[0]
        for name in (
            "season:",
            "completed_only:",
            "provenance_shadow_session_key:",
            "provenance_shadow_endpoint:",
        ):
            self.assertEqual(dispatch.count(f"      {name}"), 1)
        self.assertEqual(text.count("openf1-manual-shadow-custody-attestation:"), 1)
        self.assertEqual(text.count("dr002-pre2b7k4r28-openf1-manual-shadow-custody"), 1)
        self.assertIn("if: ${{ success() && (github.event_name != 'workflow_dispatch' || github.event.inputs.provenance_shadow_session_key == '') }}", text)
        self.assertLess(text.index("Upload legacy source closure artifact"), text.index("f1_source_closure_publish_guard_v1.py"))

    def test_guard_has_one_plain_push_and_no_provider_or_retry_path(self):
        source = GUARD_PATH.read_text(encoding="utf-8")
        self.assertEqual(source.count('"push",\n            remote,'), 1)
        self.assertNotIn("--force", source)
        self.assertNotIn("git rebase", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("openf1.org", source)
        self.assertIn('"retry_used": False', source)
        self.assertIn('"provider_requests": 0', source)

    def test_protected_dependency_blobs_unchanged(self):
        expected = {
            "docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md": "85ce44807ef159b5ba5d3bfd543ea1f945097f77",
            "scripts/ops/safe_git_push_rebase_retry.sh": "85f85bb540cf8442827a1586d5ccf0c5602d7a75",
            ".github/workflows/f1-session-data-processor-loop-v1.yml": "cfbed6cbedac9c7e601802c38c6eb5770d09004d",
            ".github/workflows/f1-automated-forecast-gate-orchestrator-v1.yml": "32a1210a2f43065e9d65a9bd858c059b6166700f",
            ".github/workflows/f1-peak-elite-control-room-one-click-v1.yml": "c2f8ddc46c52a2be06fcf7f53d03edc2df40f787",
        }
        for path, expected_blob in expected.items():
            with self.subTest(path=path):
                raw = (ROOT / path).read_bytes()
                actual = hashlib.sha1(
                    b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
                ).hexdigest()
                self.assertEqual(actual, expected_blob)

        immutable_collectors = {
            blob_sha: immutable_git_blob(ROOT, blob_sha)
            for blob_sha in APPROVED_COLLECTOR_BLOBS
        }
        self.assertEqual(len(set(APPROVED_COLLECTOR_BLOBS)), 3)
        for index, left in enumerate(APPROVED_COLLECTOR_BLOBS):
            for right in APPROVED_COLLECTOR_BLOBS[index + 1:]:
                self.assertNotEqual(
                    immutable_collectors[left], immutable_collectors[right]
                )

        active = (ROOT / COLLECTOR_PATH).read_bytes()
        active_blob = require_approved_collector(active)
        self.assertEqual(active, immutable_collectors[active_blob])

        tampered = active + b"\n# unauthorized collector change\n"
        with self.assertRaisesRegex(AssertionError, "unrecognized collector blob"):
            require_approved_collector(tampered)


if __name__ == "__main__":
    unittest.main()
