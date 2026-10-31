import importlib.util
import io
import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/elite/download_latest_openf1_artifacts.py"
SPEC = importlib.util.spec_from_file_location("elite_artifact_ingest", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REPO = "owner/repository"
TOKEN = "test-token"


def zip_bytes(name="evidence/data.csv", payload=b"a,b\n1,2\n"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, payload)
    return stream.getvalue()


def artifact(profile="pre_race", artifact_id=101, size=None, **changes):
    prefixes = MODULE.PROFILES[profile]
    data = {
        "id": artifact_id,
        "name": prefixes[0] + "-2026-77",
        "expired": False,
        "size_in_bytes": size if size is not None else len(zip_bytes()),
        "created_at": "2026-10-30T01:00:00Z",
        "updated_at": "2026-10-30T01:01:00Z",
        "archive_download_url": f"https://api.github.com/repos/{REPO}/actions/artifacts/{artifact_id}/zip",
        "workflow_run": {"id": 5001, "head_sha": "a" * 40},
    }
    data.update(changes)
    return data


def workflow_run_response(profile="pre_race", run_id=5001, head_sha=None, **changes):
    data = {
        "id": run_id,
        "head_sha": head_sha or "a" * 40,
        "path": next(iter(MODULE.APPROVED_WORKFLOWS[profile].values())),
        "head_branch": "main",
        "event": "schedule",
        "status": "completed",
        "conclusion": "success",
        "run_attempt": 1,
        "repository": {"full_name": REPO},
        "head_repository": {"full_name": REPO},
        "artifacts_url": f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/artifacts",
        "created_at": "2026-10-30T00:50:00Z",
        "run_started_at": "2026-10-30T00:51:00Z",
        "updated_at": "2026-10-30T01:05:00Z",
    }
    data.update(changes)
    return data


def verified_run_identity(profile="pre_race"):
    return {
        "id": 5001,
        "head_sha": "a" * 40,
        "path": next(iter(MODULE.APPROVED_WORKFLOWS[profile].values())),
        "head_branch": "main",
        "event": "schedule",
        "run_attempt": 1,
        "repository": REPO,
        "status": "completed",
        "conclusion": "success",
    }


def signed_url(expiry=None):
    expiry = expiry or datetime.now(timezone.utc) + timedelta(hours=1)
    return "https://results.blob.core.windows.net/actions/archive.zip?se=" + expiry.isoformat()


class FakeResponse:
    def __init__(self, body, headers=None, final_url=None):
        self.body = io.BytesIO(body)
        self.headers = headers or {}
        self.final_url = final_url

    def read(self, size=-1):
        return self.body.read(size)

    def __enter__(self):
        return self

    def geturl(self):
        return self.final_url

    def __exit__(self, *args):
        return False


class RedirectOpener:
    def __init__(self, location, requests):
        self.location = location
        self.requests = requests

    def open(self, request, timeout):
        self.requests.append(request)
        headers = Message()
        headers["Location"] = self.location
        raise HTTPError(request.full_url, 302, "Found", headers, None)


class EliteArtifactIngestEgressTests(unittest.TestCase):
    def test_profile_selection_requires_exact_separator_and_latest_identity(self):
        older = artifact(artifact_id=100, updated_at="2026-10-30T00:30:00Z")
        newer = artifact(artifact_id=101)
        lookalike = artifact(artifact_id=102, name="openf1-prerace-auto-finality")
        selected = MODULE.pick_latest([older, lookalike, newer], MODULE.PROFILES["pre_race"], REPO)
        self.assertEqual(selected["id"], 101)

    def test_wrong_archive_repository_or_artifact_identity_is_rejected(self):
        for bad_url in (
            "https://api.github.com/repos/other/repo/actions/artifacts/101/zip",
            f"https://api.github.com/repos/{REPO}/actions/artifacts/999/zip",
            f"http://api.github.com/repos/{REPO}/actions/artifacts/101/zip",
        ):
            with self.subTest(bad_url=bad_url):
                with self.assertRaisesRegex(MODULE.ArtifactHold, "identity mismatch"):
                    MODULE.validate_artifact(
                        artifact(archive_download_url=bad_url), REPO, MODULE.PROFILES["pre_race"]
                    )

    def test_oversize_and_invalid_chronology_are_rejected(self):
        with self.assertRaisesRegex(MODULE.ArtifactHold, "exceeds limit"):
            MODULE.validate_artifact(
                artifact(size_in_bytes=MODULE.MAX_ARTIFACT_BYTES + 1), REPO, MODULE.PROFILES["pre_race"]
            )
        with self.assertRaisesRegex(MODULE.ArtifactHold, "chronology"):
            MODULE.validate_artifact(
                artifact(updated_at="2026-10-29T23:59:00Z"), REPO, MODULE.PROFILES["pre_race"]
            )

    def test_normal_redirect_separates_auth_and_records_exact_integrity(self):
        body = zip_bytes()
        target = artifact(size=len(body))
        api_requests = []
        storage_requests = []
        opener = RedirectOpener(signed_url(), api_requests)

        def storage_open(request, timeout):
            storage_requests.append(request)
            return FakeResponse(body, {"Content-Length": str(len(body))}, request.full_url)

        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "artifact.zip"
            with patch.object(MODULE, "gh_get_json", return_value=workflow_run_response()), patch(
                "urllib.request.build_opener", return_value=opener
            ), patch.object(
                MODULE, "urlopen", side_effect=storage_open
            ):
                result = MODULE.gh_download_artifact(target, "pre_race", REPO, TOKEN, dest)
            self.assertEqual(dest.read_bytes(), body)
            self.assertEqual(result["downloaded_bytes"], len(body))
            self.assertEqual(len(result["archive_sha256"]), 64)
            self.assertEqual(result["verified_workflow_run"], verified_run_identity())
        self.assertEqual(api_requests[0].get_header("Authorization"), "Bearer " + TOKEN)
        self.assertIsNone(storage_requests[0].get_header("Authorization"))

    def test_http_503_reproduction_holds_after_exact_two_calls_and_leaves_no_partial(self):
        body = zip_bytes()
        target = artifact(size=len(body))
        api_requests = []
        storage_requests = []
        opener = RedirectOpener(signed_url(), api_requests)

        def storage_503(request, timeout):
            storage_requests.append(request)
            raise HTTPError(request.full_url, 503, "Egress is over the account limit", {}, None)

        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "artifact.zip"
            with patch.object(MODULE, "gh_get_json", return_value=workflow_run_response()), patch(
                "urllib.request.build_opener", return_value=opener
            ), patch.object(
                MODULE, "urlopen", side_effect=storage_503
            ):
                with self.assertRaisesRegex(MODULE.ArtifactHold, "HTTP 503; HOLD"):
                    MODULE.gh_download_artifact(target, "pre_race", REPO, TOKEN, dest)
            self.assertFalse(dest.exists())
            self.assertFalse(Path(str(dest) + ".part").exists())
        self.assertEqual(len(api_requests), 1)
        self.assertEqual(len(storage_requests), 1)
        self.assertIsNone(storage_requests[0].get_header("Authorization"))

    def test_storage_404_holds_without_retry(self):
        requests = []

        def storage_404(request, timeout):
            requests.append(request)
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)

        with tempfile.TemporaryDirectory() as temp, patch.object(MODULE, "urlopen", side_effect=storage_404):
            with self.assertRaisesRegex(MODULE.ArtifactHold, "HTTP 404; HOLD"):
                MODULE.download_signed_url(signed_url(), Path(temp) / "a.zip", 5)
        self.assertEqual(len(requests), 1)

    def test_expired_redirect_rejected_before_storage_request(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(MODULE, "urlopen") as mocked:
            with self.assertRaisesRegex(MODULE.ArtifactHold, "redirect is expired"):
                MODULE.download_signed_url(
                    signed_url(datetime.now(timezone.utc) - timedelta(seconds=1)), Path(temp) / "a.zip", 1
                )
        mocked.assert_not_called()

    def test_untrusted_or_unsigned_redirect_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(MODULE, "urlopen") as mocked:
            for url in (
                "https://example.com/archive.zip?se=2099-01-01T00:00:00Z",
                "https://results.blob.core.windows.net/actions/archive.zip",
            ):
                with self.subTest(url=url), self.assertRaises(MODULE.ArtifactHold):
                    MODULE.download_signed_url(url, Path(temp) / "a.zip", 1)
        mocked.assert_not_called()

    def test_unexpected_storage_redirect_holds_without_writing(self):
        url = signed_url()
        with tempfile.TemporaryDirectory() as temp, patch.object(
            MODULE, "urlopen", return_value=FakeResponse(b"x", final_url="https://evil.example/archive.zip")
        ):
            dest = Path(temp) / "a.zip"
            with self.assertRaisesRegex(MODULE.ArtifactHold, "redirected unexpectedly"):
                MODULE.download_signed_url(url, dest, 1)
            self.assertFalse(dest.exists())

    def test_incomplete_or_overlong_transfer_is_rejected_and_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            for body, expected in ((b"12", 3), (b"1234", 3)):
                dest = Path(temp) / "a.zip"
                with self.subTest(body=body), self.assertRaises(MODULE.ArtifactHold):
                    MODULE._stream_response(FakeResponse(body), dest, expected)
                self.assertFalse(dest.exists())
                self.assertFalse(Path(str(dest) + ".part").exists())

    def test_content_length_identity_mismatch_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "a.zip"
            with self.assertRaisesRegex(MODULE.ArtifactHold, "Content-Length identity"):
                MODULE._stream_response(FakeResponse(b"123", {"Content-Length": "4"}), dest, 3)
            self.assertFalse(dest.exists())

    def test_exact_hash_bound_cache_avoids_all_network_requests(self):
        body = zip_bytes()
        target = artifact(size=len(body))
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "artifact.zip"
            dest.write_bytes(body)
            transfer = {
                "downloaded_bytes": len(body),
                "archive_sha256": MODULE._file_sha256(dest),
            }
            MODULE.write_cache_identity(
                target, REPO, verified_run_identity(), dest, transfer
            )
            with patch.object(MODULE, "gh_get_json", return_value=workflow_run_response()), patch(
                "urllib.request.build_opener"
            ) as opener, patch.object(MODULE, "urlopen") as urlopen:
                reused = MODULE.gh_download_artifact(target, "pre_race", REPO, TOKEN, dest)
            self.assertTrue(reused["cache_reused"])
            self.assertEqual(reused["archive_sha256"], transfer["archive_sha256"])
            opener.assert_not_called()
            urlopen.assert_not_called()

    def test_stale_or_altered_cache_holds_before_network_request(self):
        body = zip_bytes()
        target = artifact(size=len(body))
        cases = ("missing_receipt", "wrong_identity", "altered_bytes")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                dest = Path(temp) / "artifact.zip"
                dest.write_bytes(body)
                transfer = {
                    "downloaded_bytes": len(body),
                    "archive_sha256": MODULE._file_sha256(dest),
                }
                if case != "missing_receipt":
                    MODULE.write_cache_identity(
                        target, REPO, verified_run_identity(), dest, transfer
                    )
                if case == "wrong_identity":
                    receipt = MODULE._cache_identity_path(dest)
                    data = json.loads(receipt.read_text())
                    data["artifact_id"] = 999
                    receipt.write_text(json.dumps(data))
                elif case == "altered_bytes":
                    dest.write_bytes(body[:-1] + bytes([body[-1] ^ 1]))
                with patch.object(MODULE, "gh_get_json", return_value=workflow_run_response()), patch(
                    "urllib.request.build_opener"
                ) as opener, patch.object(MODULE, "urlopen") as urlopen:
                    with self.assertRaisesRegex(MODULE.ArtifactHold, "cache"):
                        MODULE.gh_download_artifact(target, "pre_race", REPO, TOKEN, dest)
                opener.assert_not_called()
                urlopen.assert_not_called()

    def test_missing_null_or_malformed_listing_run_holds_before_download_or_inputs(self):
        missing = artifact()
        missing.pop("workflow_run")
        cases = (
            missing,
            artifact(workflow_run=None),
            artifact(workflow_run={}),
            artifact(workflow_run={"id": True, "head_sha": "a" * 40}),
            artifact(workflow_run={"id": 5001, "head_sha": "not-a-sha"}),
        )
        for target in cases:
            with self.subTest(workflow_run=target.get("workflow_run", "missing")), tempfile.TemporaryDirectory() as temp:
                with patch.object(MODULE, "list_artifacts", return_value=[target]), patch.object(
                    MODULE, "gh_get_json"
                ) as run_lookup, patch("urllib.request.build_opener") as archive_api, patch.object(
                    MODULE, "urlopen"
                ) as storage, patch.dict(
                    os.environ, {"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": TOKEN}, clear=False
                ), patch("sys.argv", [str(MODULE_PATH), "--output-dir", temp]):
                    with self.assertRaisesRegex(MODULE.ArtifactHold, "workflow-run identity"):
                        MODULE.main()
                run_lookup.assert_not_called()
                archive_api.assert_not_called()
                storage.assert_not_called()
                self.assertFalse((Path(temp) / "inputs").exists())
                manifest = json.loads(
                    (Path(temp) / "manifests/elite_artifact_source_manifest.json").read_text()
                )
                self.assertTrue(manifest["hold"])
                self.assertFalse(manifest["source_ready"])
                self.assertFalse(manifest["forecast_eligible"])

    def test_mismatched_run_head_workflow_and_repository_hold_before_archive(self):
        cases = (
            workflow_run_response(id=9001),
            workflow_run_response(head_sha="b" * 40),
            workflow_run_response(path=".github/workflows/unapproved.yml"),
            workflow_run_response(repository={"full_name": "other/repository"}),
            workflow_run_response(conclusion="failure"),
        )
        for run in cases:
            with self.subTest(run=run), tempfile.TemporaryDirectory() as temp:
                dest = Path(temp) / "artifact.zip"
                with patch.object(MODULE, "gh_get_json", return_value=run) as run_lookup, patch(
                    "urllib.request.build_opener"
                ) as archive_api, patch.object(MODULE, "urlopen") as storage:
                    with self.assertRaisesRegex(MODULE.ArtifactHold, "workflow-run identity mismatch"):
                        MODULE.gh_download_artifact(
                            artifact(), "pre_race", REPO, TOKEN, dest
                        )
                run_lookup.assert_called_once()
                archive_api.assert_not_called()
                storage.assert_not_called()
                self.assertFalse(dest.exists())
                self.assertFalse((Path(temp) / "inputs").exists())

    def test_cache_is_not_reused_when_independent_run_identity_mismatches(self):
        body = zip_bytes()
        target = artifact(size=len(body))
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "artifact.zip"
            dest.write_bytes(body)
            transfer = {
                "downloaded_bytes": len(body),
                "archive_sha256": MODULE._file_sha256(dest),
            }
            MODULE.write_cache_identity(
                target, REPO, verified_run_identity(), dest, transfer
            )
            wrong_run = workflow_run_response(head_sha="b" * 40)
            with patch.object(MODULE, "gh_get_json", return_value=wrong_run), patch(
                "urllib.request.build_opener"
            ) as archive_api, patch.object(MODULE, "urlopen") as storage:
                with self.assertRaisesRegex(MODULE.ArtifactHold, "workflow-run identity mismatch"):
                    MODULE.gh_download_artifact(
                        target, "pre_race", REPO, TOKEN, dest
                    )
            archive_api.assert_not_called()
            storage.assert_not_called()
            self.assertFalse((Path(temp) / "inputs").exists())

    def test_legacy_prefix_without_approved_workflow_holds_architecture_scope(self):
        target = artifact(name="openf1-high-frequency-2026-prerace-77")
        with tempfile.TemporaryDirectory() as temp, patch.object(
            MODULE, "gh_get_json"
        ) as run_lookup, patch("urllib.request.build_opener") as archive_api, patch.object(
            MODULE, "urlopen"
        ) as storage:
            with self.assertRaisesRegex(MODULE.ArtifactHold, "HOLD_ARCHITECTURE_SCOPE"):
                MODULE.gh_download_artifact(
                    target, "pre_race", REPO, TOKEN, Path(temp) / "artifact.zip"
                )
        run_lookup.assert_not_called()
        archive_api.assert_not_called()
        storage.assert_not_called()

    def test_corrupt_zip_rejected_without_visible_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "bad.zip"
            archive.write_bytes(b"not a zip")
            destination = Path(temp) / "inputs" / "pre_race"
            with self.assertRaises(zipfile.BadZipFile):
                MODULE.extract_validated_zip(archive, destination)
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_name(".pre_race.extracting").exists())

    def test_traversal_symlink_and_duplicate_members_are_rejected(self):
        builders = []
        builders.append(lambda z: z.writestr("../escape", "x"))
        def symlink(z):
            info = zipfile.ZipInfo("link")
            info.external_attr = (stat_mode := 0o120777) << 16
            self.assertTrue(stat_mode)
            z.writestr(info, "target")
        builders.append(symlink)
        def duplicate(z):
            z.writestr("same", "a")
            z.writestr("same", "b")
        builders.append(duplicate)
        for index, builder in enumerate(builders):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp:
                archive = Path(temp) / "unsafe.zip"
                with zipfile.ZipFile(archive, "w") as z:
                    builder(z)
                with self.assertRaisesRegex(MODULE.ArtifactHold, "unsafe member"):
                    MODULE.extract_validated_zip(archive, Path(temp) / "profile")

    def test_valid_zip_extracts_only_after_integrity_check(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "valid.zip"
            archive.write_bytes(zip_bytes())
            destination = Path(temp) / "pre_race"
            MODULE.extract_validated_zip(archive, destination)
            self.assertEqual((destination / "evidence/data.csv").read_bytes(), b"a,b\n1,2\n")

    def test_missing_all_artifacts_writes_hold_and_false_trust_ceilings(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(MODULE, "list_artifacts", return_value=[]), patch.dict(
            os.environ, {"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": TOKEN}, clear=False
        ), patch("sys.argv", [str(MODULE_PATH), "--output-dir", temp]):
            with self.assertRaisesRegex(SystemExit, "No OpenF1 artifacts"):
                MODULE.main()
            manifest = json.loads(
                (Path(temp) / "manifests/elite_artifact_source_manifest.json").read_text()
            )
        self.assertTrue(manifest["hold"])
        self.assertFalse(manifest["source_ready"])
        self.assertFalse(manifest["forecast_eligible"])
        self.assertFalse(manifest["event_session_provenance_verified"])
        self.assertEqual(
            manifest["event_session_provenance_status"], "HOLD_ARCHITECTURE_SCOPE"
        )
        self.assertTrue(all(row["status"] == "MISSING" for row in manifest["profiles"]))

    def test_failed_profile_manifest_holds_and_never_upgrades_trust(self):
        target = artifact()
        with tempfile.TemporaryDirectory() as temp, patch.object(
            MODULE, "list_artifacts", return_value=[target]
        ), patch.object(MODULE, "gh_download_artifact", side_effect=MODULE.ArtifactHold("HTTP 503; HOLD")), patch.dict(
            os.environ, {"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": TOKEN}, clear=False
        ), patch("sys.argv", [str(MODULE_PATH), "--output-dir", temp]):
            with self.assertRaisesRegex(MODULE.ArtifactHold, "HTTP 503"):
                MODULE.main()
            manifest = json.loads(
                (Path(temp) / "manifests/elite_artifact_source_manifest.json").read_text()
            )
        self.assertTrue(manifest["hold"])
        self.assertFalse(manifest["source_ready"])
        self.assertFalse(manifest["forecast_eligible"])
        self.assertFalse(manifest["profiles"][0]["verified"])


if __name__ == "__main__":
    unittest.main()
