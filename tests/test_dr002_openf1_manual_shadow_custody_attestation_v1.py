import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "scripts/forecast_bundles"
SCRIPT = BUNDLE_DIR / "dr002_openf1_manual_shadow_custody_attestation_v1.py"
WORKFLOW = ROOT / ".github/workflows/f1-openf1-lightweight-source-closure.yml"
FIXTURE_SCRIPT = (
    ROOT / "tests/test_dr002_openf1_three_source_precutoff_candidate_v1.py"
)
sys.path.insert(0, str(BUNDLE_DIR))

spec = importlib.util.spec_from_file_location("manual_shadow_custody", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

fixture_spec = importlib.util.spec_from_file_location(
    "precutoff_fixture_for_custody", FIXTURE_SCRIPT
)
_fixture_module = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(_fixture_module)


HISTORICAL_WORKFLOW_BLOB = "d277ceaaffbb148dbde4b0c32bfbbcd8664e4329"
PREDECESSOR_WORKFLOW_BLOB = "6768b09449905cd61281386d6fc147f0fa18d01c"
SUCCESSOR_WORKFLOW_BLOB = "bf56b47b3325458384bbb60148e3bb65030c41e6"
HISTORICAL_WORKFLOW_SHA256 = (
    "b7fb291274f5c1f31cceb54cc43bfca5fef88e0d1fd76a6288f219a3be18d35a"
)
PREDECESSOR_PREFIX_SHA256 = (
    "4371e64fda6fad45f123ecd615c79fa372267c982c7c6387ccbd55817c8d3887"
)
SUCCESSOR_PREFIX_SHA256 = (
    "e009a62e6f8df4aab62d84ecb6b4bae6ca959e30b31091470fd710aace48b0ae"
)
CUSTODY_MARKER = (
    b"# K4R28 manual-shadow custody follow-on job; original workflow above is unchanged.\n"
)
PREDECESSOR_PUBLICATION_BLOCK = b'''      - name: Commit source closure outputs
        if: ${{ success() && (github.event_name != 'workflow_dispatch' || github.event.inputs.provenance_shadow_session_key == '') }}
        run: |
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
SUCCESSOR_PUBLICATION_BLOCK = b'''      - name: Commit source closure outputs
        if: ${{ success() && (github.event_name != 'workflow_dispatch' || github.event.inputs.provenance_shadow_session_key == '') }}
        run: |
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


def git_blob_bytes(blob_sha):
    return subprocess.run(
        ["git", "cat-file", "blob", blob_sha], cwd=ROOT, check=True,
        capture_output=True,
    ).stdout


def git_blob_sha(data):
    return subprocess.run(
        ["git", "hash-object", "--stdin"], cwd=ROOT, check=True,
        input=data, capture_output=True,
    ).stdout.decode().strip()


def assert_workflow_compatibility(testcase, workflow):
    historical = git_blob_bytes(HISTORICAL_WORKFLOW_BLOB)
    predecessor = git_blob_bytes(PREDECESSOR_WORKFLOW_BLOB)
    successor = git_blob_bytes(SUCCESSOR_WORKFLOW_BLOB)
    testcase.assertEqual(hashlib.sha256(historical).hexdigest(),
                         HISTORICAL_WORKFLOW_SHA256)
    testcase.assertEqual(git_blob_sha(historical), HISTORICAL_WORKFLOW_BLOB)
    testcase.assertEqual(git_blob_sha(predecessor), PREDECESSOR_WORKFLOW_BLOB)
    testcase.assertEqual(git_blob_sha(successor), SUCCESSOR_WORKFLOW_BLOB)

    testcase.assertEqual(predecessor.count(CUSTODY_MARKER), 1)
    testcase.assertEqual(successor.count(CUSTODY_MARKER), 1)
    predecessor_prefix, predecessor_suffix = predecessor.split(CUSTODY_MARKER)
    successor_prefix, successor_suffix = successor.split(CUSTODY_MARKER)
    testcase.assertEqual(hashlib.sha256(predecessor_prefix).hexdigest(),
                         PREDECESSOR_PREFIX_SHA256)
    testcase.assertEqual(hashlib.sha256(successor_prefix).hexdigest(),
                         SUCCESSOR_PREFIX_SHA256)
    testcase.assertEqual(successor_suffix, predecessor_suffix)
    testcase.assertEqual(
        successor.replace(SUCCESSOR_PUBLICATION_BLOCK,
                          PREDECESSOR_PUBLICATION_BLOCK, 1),
        predecessor,
    )
    testcase.assertEqual(predecessor.count(PREDECESSOR_PUBLICATION_BLOCK), 1)
    testcase.assertEqual(successor.count(SUCCESSOR_PUBLICATION_BLOCK), 1)
    testcase.assertEqual(
        predecessor_prefix.replace(
            b"historical Qualifying session key.",
            b"historical Race session key.", 1,
        ),
        historical,
    )

    active_blob = git_blob_sha(workflow)
    testcase.assertIn(active_blob, {
        PREDECESSOR_WORKFLOW_BLOB, SUCCESSOR_WORKFLOW_BLOB,
    })
    testcase.assertEqual(
        workflow,
        predecessor if active_blob == PREDECESSOR_WORKFLOW_BLOB else successor,
    )
    testcase.assertEqual(workflow.count(CUSTODY_MARKER), 1)
    active_prefix, active_suffix = workflow.split(CUSTODY_MARKER)
    testcase.assertEqual(active_suffix, predecessor_suffix)
    testcase.assertEqual(
        hashlib.sha256(active_prefix).hexdigest(),
        PREDECESSOR_PREFIX_SHA256
        if active_blob == PREDECESSOR_WORKFLOW_BLOB
        else SUCCESSOR_PREFIX_SHA256,
    )

    parsed = yaml.safe_load(workflow.decode("utf-8"))
    triggers = parsed.get("on", parsed.get(True))
    inputs = triggers["workflow_dispatch"]["inputs"]
    testcase.assertEqual(set(inputs), {
        "season", "completed_only", "provenance_shadow_session_key",
        "provenance_shadow_endpoint",
    })
    testcase.assertEqual(inputs["season"], {
        "description": "F1 season year", "required": True, "default": "2026",
    })
    testcase.assertEqual(inputs["completed_only"], {
        "description": "Only retrieve completed sessions", "required": True,
        "default": "true",
    })
    testcase.assertEqual(inputs["provenance_shadow_session_key"], {
        "description": (
            "Optional exact historical session key for manual provenance shadow only"
        ),
        "required": False, "default": "",
    })
    testcase.assertEqual(inputs["provenance_shadow_endpoint"], {
        "description": "Historical provenance shadow endpoint",
        "required": False, "type": "choice",
        "options": ["weather", "drivers", "starting_grid"],
        "default": "weather",
    })
    testcase.assertEqual(parsed["permissions"], {
        "contents": "write", "actions": "read",
    })
    custody = parsed["jobs"]["openf1-manual-shadow-custody-attestation"]
    testcase.assertEqual(custody["permissions"], {
        "contents": "read", "actions": "read", "id-token": "write",
        "attestations": "write",
    })
    for value in (
        "workflow_dispatch", "provenance_shadow_session_key",
        "refs/heads/main", "weather", "drivers", "starting_grid",
        ".result == 'success'",
    ):
        testcase.assertIn(value, custody["if"])
    testcase.assertEqual(predecessor_suffix.count(
        b"actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093"
    ), 1)
    testcase.assertEqual(predecessor_suffix.count(
        b"actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
    ), 1)
    return active_blob


class ManualShadowCustodyAttestationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        fixture_type = _fixture_module.ThreeSourcePrecutoffCandidateTests
        self.fixture = fixture_type(
            "test_valid_synthetic_event_is_only_unauthenticated_candidate"
        )
        self.fixture.setUp()
        self.repository = "F1Lllewellyn/f1-data-publisher"
        self.workflow = m.WORKFLOW_NAME
        self.workflow_ref = self.repository + "/" + m.WORKFLOW_PATH + "@" + m.MAIN_REF
        self.head_sha = "a" * 40
        self.run_id = "123456"
        self.run_attempt = "1"

    @staticmethod
    def json_bytes(value, *, canonical=False):
        if canonical:
            return json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        return (
            json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8")

    def artifact_members(self, endpoint, *, raw=None, receipt_bytes=None,
                         sessions=None, manifest_changes=None,
                         assessment_changes=None):
        f = self.fixture
        if endpoint == "weather":
            raw = f.weather_raw if raw is None else raw
            receipt_bytes = f.weather_receipt if receipt_bytes is None else receipt_bytes
            raw_name = "weather.response.json"
            session_id = f.practice_id
        elif endpoint == "drivers":
            raw = f.drivers_raw if raw is None else raw
            receipt_bytes = f.drivers_receipt if receipt_bytes is None else receipt_bytes
            raw_name = "drivers.response.json"
            session_id = f.practice_id
        else:
            raw = f.grid_raw if raw is None else raw
            receipt_bytes = f.grid_receipt if receipt_bytes is None else receipt_bytes
            raw_name = "starting_grid.response.json"
            session_id = f.qualifying_id
        receipt = json.loads(receipt_bytes)
        payload = receipt["payload"]
        raw_sha = hashlib.sha256(raw).hexdigest()
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        common = {
            "status": m.capture_contract.VALIDATED,
            "reason": None,
            "k4r1_status": m.capture_contract.VALIDATED,
            "repository": self.repository,
            "workflow": self.workflow,
            "workflow_ref": self.workflow_ref,
            "ref": m.MAIN_REF,
            "head_sha": self.head_sha,
            "run_id": self.run_id,
            "run_attempt": self.run_attempt,
            "event_id": f.event_id,
            "meeting_id": f.meeting_id,
            "session_id": session_id,
            "canonical_request_uri": payload["source_uri"],
            "raw_response_sha256": raw_sha,
            "receipt_sha256": receipt_sha,
            "receipt_type": "source_capture",
            "first_observed_utc": payload["first_observed_utc"],
            "ingested_utc": payload["ingested_utc"],
            "receipt_created_utc": receipt["receipt_created_utc"],
            "openf1_documented_historical_window_satisfied": True,
            "verified_receipt_bindings_created": False,
            "latest_or_history_written": False,
            "repository_mutation_performed": False,
            "dr002_activated": False,
            "promotion_allowed": False,
        }
        if endpoint == "drivers":
            common.update({
                "selected_endpoint": "drivers",
                "raw_response_filename": raw_name,
                "k4r6_status": m.drivers_adapter.VALIDATED,
            })
        elif endpoint == "starting_grid":
            sessions = f.sessions_raw if sessions is None else sessions
            manifest = f.valid_manifest(
                grid_receipt=receipt_bytes,
                grid_raw=raw,
                sessions_raw=sessions,
            )
            manifest.update(common)
            manifest.update({
                "raw_response_filename": raw_name,
                "session_discovery_filename": "sessions.response.json",
                "session_discovery_request_uri": (
                    m.API_BASE + "/sessions?year=2026"
                ),
            })
            common = manifest
        if manifest_changes:
            common.update(manifest_changes)
        assessment = {
            "status": m.capture_contract.VALIDATED,
            "reason_codes": [],
            "canonical_request_uri": payload["source_uri"],
            "raw_response_sha256": raw_sha,
            "receipt_sha256": receipt_sha,
        }
        if assessment_changes:
            assessment.update(assessment_changes)
        members = {
            raw_name: raw,
            "source_capture_receipt.json": receipt_bytes,
            "shadow_manifest.json": self.json_bytes(common),
            "shadow_report.md": b"# DR-002 synthetic source shadow\n",
            "historical_rest_capture_assessment.json": self.json_bytes(assessment),
        }
        if endpoint == "starting_grid":
            members["sessions.response.json"] = sessions
        return members

    def write_artifact(self, endpoint, *, members=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "artifact"
        root.mkdir()
        members = self.artifact_members(endpoint) if members is None else members
        for name, data in members.items():
            (root / name).write_bytes(data)
        return root

    def build(self, endpoint="weather", *, root=None, **changes):
        root = self.write_artifact(endpoint) if root is None else root
        args = {
            "artifact_root": root,
            "endpoint": endpoint,
            "session_key": (
                self.fixture.qualifying_id
                if endpoint == "starting_grid" else self.fixture.practice_id
            ),
            "repository": self.repository,
            "workflow": self.workflow,
            "workflow_ref": self.workflow_ref,
            "git_ref": m.MAIN_REF,
            "head_sha": self.head_sha,
            "run_id": self.run_id,
            "run_attempt": self.run_attempt,
        }
        args.update(changes)
        return m.build_custody_manifest_bytes(**args)

    def assert_hold(self, callable_, reason=None):
        with self.assertRaises(m.CustodyHold) as caught:
            callable_()
        if reason is not None:
            self.assertIn(reason, str(caught.exception))

    def fake_bundle(self, manifest_bytes, *, digest=None, signature=b"fake-signature"):
        digest = digest or hashlib.sha256(manifest_bytes).hexdigest()
        statement = {
            "_type": m.STATEMENT_TYPE,
            "predicateType": m.PREDICATE_TYPE,
            "subject": [{
                "name": "custody_manifest.json",
                "digest": {"sha256": digest},
            }],
            "predicate": {},
        }
        bundle = {
            "mediaType": m.BUNDLE_MEDIA_TYPE,
            "dsseEnvelope": {
                "payloadType": m.DSSE_PAYLOAD_TYPE,
                "payload": base64.b64encode(
                    self.json_bytes(statement, canonical=True)
                ).decode("ascii"),
                "signatures": [{
                    "sig": base64.b64encode(signature).decode("ascii")
                }],
            },
        }
        return self.json_bytes(bundle, canonical=True)

    def prepared_output(self, endpoint="weather"):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        artifact = root / "artifact"
        artifact.mkdir()
        for name, data in self.artifact_members(endpoint).items():
            (artifact / name).write_bytes(data)
        output = root / "custody"
        manifest_bytes = m.prepare_custody_manifest(
            artifact_root=artifact,
            output_dir=output,
            endpoint=endpoint,
            session_key=(
                self.fixture.qualifying_id
                if endpoint == "starting_grid" else self.fixture.practice_id
            ),
            repository=self.repository,
            workflow=self.workflow,
            workflow_ref=self.workflow_ref,
            git_ref=m.MAIN_REF,
            head_sha=self.head_sha,
            run_id=self.run_id,
            run_attempt=self.run_attempt,
        )
        bundle_path = root / "action-output.bundle.json"
        bundle_path.write_bytes(self.fake_bundle(manifest_bytes))
        return root, output, manifest_bytes, bundle_path

    def preserve(self, output, bundle_path, **changes):
        args = {
            "custody_manifest_path": output / "custody_manifest.json",
            "attestation_bundle_path": bundle_path,
            "output_dir": output,
            "attestation_id": "98765",
            "attestation_url": (
                "https://github.com/" + self.repository + "/attestations/98765"
            ),
            "repository": self.repository,
            "workflow": self.workflow,
            "workflow_ref": self.workflow_ref,
            "git_ref": m.MAIN_REF,
            "head_sha": self.head_sha,
            "run_id": self.run_id,
            "run_attempt": self.run_attempt,
        }
        args.update(changes)
        return m.preserve_attestation_outputs(**args)

    # 1-3
    def test_valid_weather_drivers_and_grid_artifacts_prepare(self):
        for endpoint, count in (("weather", 5), ("drivers", 5), ("starting_grid", 6)):
            with self.subTest(endpoint=endpoint):
                result = json.loads(self.build(endpoint))
                self.assertEqual(result["status"], m.STATUS)
                self.assertEqual(result["source_endpoint"], endpoint)
                self.assertEqual(result["original_artifact_member_count"], count)

    # 4
    def test_inventory_is_exact_sorted_and_deterministic(self):
        first = self.build("starting_grid")
        second = self.build("starting_grid")
        self.assertEqual(first, second)
        inventory = json.loads(first)["original_artifact_members"]
        self.assertEqual(
            [row["member_name"] for row in inventory],
            sorted(m.EXPECTED_MEMBERS["starting_grid"]),
        )
        members = self.artifact_members("starting_grid")
        for row in inventory:
            data = members[row["member_name"]]
            self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(row["byte_length"], len(data))

    # 5
    def test_manifest_preserves_source_and_race_relationship_without_authority(self):
        result = json.loads(self.build("starting_grid"))
        relation = result["source_to_target_relationship"]
        self.assertEqual(relation["source_session_id"], self.fixture.qualifying_id)
        self.assertEqual(relation["target_race_session_id"], self.fixture.race_id)
        self.assertFalse(relation["cross_session_producer_authorization"])
        self.assertFalse(result["source_session_classification_authenticated"])

    # 6
    def test_all_required_trust_and_production_flags_are_false(self):
        result = json.loads(self.build("weather"))
        self.assertTrue(all(result[field] is False for field in m.FALSE_FLAGS))

    def test_parse_utc_accepts_equivalent_z_and_zero_offset_only(self):
        zulu = m._parse_utc("2026-09-26T11:00:00Z", "timestamp_malformed")
        offset = m._parse_utc(
            "2026-09-26T11:00:00+00:00", "timestamp_malformed"
        )
        self.assertEqual(zulu, offset)
        self.assertEqual(zulu.utcoffset().total_seconds(), 0)

        for invalid in (
            "2026-09-26T11:00:00+01:00",
            "2026-09-26T11:00:00-04:00",
            "2026-09-26T11:00:00",
            "2026-09-26T11:00:00+00:00 ",
            None,
        ):
            with self.subTest(invalid=invalid):
                self.assert_hold(
                    lambda value=invalid: m._parse_utc(
                        value, "timestamp_malformed"
                    ),
                    "timestamp_malformed",
                )

    def test_grid_accepts_synthetic_provider_zero_offset_timestamps(self):
        sessions = json.loads(self.fixture.sessions_raw)
        source = next(
            row for row in sessions
            if str(row["session_key"]) == self.fixture.qualifying_id
        )
        target = next(
            row for row in sessions
            if str(row["session_key"]) == self.fixture.race_id
        )
        source["date_end"] = "2026-09-25T13:00:00+00:00"
        target["date_start"] = "2026-09-26T11:00:00+00:00"
        sessions_raw = self.json_bytes(sessions)
        members = self.artifact_members(
            "starting_grid", sessions=sessions_raw
        )
        result = json.loads(self.build(
            "starting_grid",
            root=self.write_artifact("starting_grid", members=members),
        ))

        self.assertEqual(result["status"], m.STATUS)
        self.assertTrue(all(result[field] is False for field in m.FALSE_FLAGS))
        relation = result["source_to_target_relationship"]
        self.assertFalse(relation["cross_session_producer_authorization"])
        self.assertFalse(result["source_session_classification_authenticated"])

    # 7
    def test_manifest_contains_no_raw_source_bytes_paths_or_secrets(self):
        data = self.build("drivers")
        text = data.decode("utf-8")
        self.assertNotIn("DRIVER 44", text)
        self.assertNotIn("_runtime/", text)
        self.assertNotIn("credentials", text.lower())
        self.assertNotIn("source_artifact", text)

    # 8
    def test_raw_tamper_holds(self):
        root = self.write_artifact("weather")
        (root / "weather.response.json").write_bytes(
            (root / "weather.response.json").read_bytes() + b" "
        )
        self.assert_hold(lambda: self.build("weather", root=root), "raw_hash")

    # 9
    def test_receipt_tamper_holds(self):
        root = self.write_artifact("drivers")
        path = root / "source_capture_receipt.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_hold(lambda: self.build("drivers", root=root), "not_canonical")

    # 10
    def test_noncanonical_receipt_holds(self):
        members = self.artifact_members("weather")
        pretty = self.json_bytes(json.loads(members["source_capture_receipt.json"]))
        members["source_capture_receipt.json"] = pretty
        root = self.write_artifact("weather", members=members)
        self.assert_hold(lambda: self.build("weather", root=root), "not_canonical")

    # 11
    def test_duplicate_receipt_json_key_holds(self):
        members = self.artifact_members("weather")
        members["source_capture_receipt.json"] = b'{"schema_version":"x","schema_version":"y"}'
        root = self.write_artifact("weather", members=members)
        self.assert_hold(lambda: self.build("weather", root=root), "duplicate_key")

    # 12
    def test_shadow_manifest_hash_tamper_holds(self):
        members = self.artifact_members(
            "drivers", manifest_changes={"raw_response_sha256": "0" * 64}
        )
        root = self.write_artifact("drivers", members=members)
        self.assert_hold(lambda: self.build("drivers", root=root), "raw_response_sha256")

    # 13
    def test_capture_assessment_tamper_holds(self):
        members = self.artifact_members(
            "weather", assessment_changes={"receipt_sha256": "0" * 64}
        )
        root = self.write_artifact("weather", members=members)
        self.assert_hold(lambda: self.build("weather", root=root), "receipt_sha256")

    # 14
    def test_grid_discovery_tamper_holds(self):
        root = self.write_artifact("starting_grid")
        path = root / "sessions.response.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_hold(lambda: self.build("starting_grid", root=root), "discovery")

    # 15-17
    def test_wrong_endpoint_run_and_head_hold(self):
        weather = self.write_artifact("weather")
        self.assert_hold(lambda: self.build("drivers", root=weather), "member_set")
        self.assert_hold(
            lambda: self.build("weather", root=weather, run_id="999"),
            "execution_mismatch:run_id",
        )
        self.assert_hold(
            lambda: self.build("weather", root=weather, head_sha="b" * 40),
            "execution_mismatch:head_sha",
        )

    # 18-20
    def test_wrong_ref_attempt_and_scope_hold(self):
        root = self.write_artifact("weather")
        self.assert_hold(
            lambda: self.build("weather", root=root, git_ref="refs/heads/dev"),
            "source_ref_not_main",
        )
        self.assert_hold(
            lambda: self.build("weather", root=root, run_attempt="2"),
            "execution_mismatch:run_attempt",
        )
        self.assert_hold(
            lambda: self.build("weather", root=root, session_key="9999"),
            "session_mismatch",
        )

    # 21
    def test_missing_source_member_holds(self):
        members = self.artifact_members("weather")
        del members["weather.response.json"]
        root = self.write_artifact("weather", members=members)
        self.assert_hold(lambda: self.build("weather", root=root), "member_set")

    # 22
    def test_extra_member_holds(self):
        root = self.write_artifact("drivers")
        (root / ".hidden").write_bytes(b"extra")
        self.assert_hold(lambda: self.build("drivers", root=root), "member_set")

    # 23
    def test_nested_directory_or_unsafe_member_holds(self):
        members = self.artifact_members("weather")
        del members["weather.response.json"]
        members["%2e%2e-weather.response.json"] = self.fixture.weather_raw
        root = self.write_artifact("weather", members=members)
        self.assert_hold(lambda: self.build("weather", root=root), "member_set")

    # 24
    def test_symlink_member_holds(self):
        root = self.write_artifact("weather")
        target = root.parent / "outside.json"
        target.write_bytes((root / "weather.response.json").read_bytes())
        (root / "weather.response.json").unlink()
        (root / "weather.response.json").symlink_to(target)
        self.assert_hold(lambda: self.build("weather", root=root), "regular_file")

    # 25
    def test_oversized_member_holds(self):
        root = self.write_artifact("weather")
        with mock.patch.object(m, "MAX_MEMBER_BYTES", 1):
            self.assert_hold(lambda: self.build("weather", root=root), "size")

    # 26
    def test_grid_source_must_be_distinct_qualifying_before_race(self):
        for changes in (
            {"grid_target_race_session_id": self.fixture.qualifying_id},
            {"grid_source_session_kind": "Race"},
        ):
            members = self.artifact_members(
                "starting_grid", manifest_changes=changes
            )
            root = self.write_artifact("starting_grid", members=members)
            self.assert_hold(lambda: self.build("starting_grid", root=root))

    # 27
    def test_grid_requires_both_attempts_and_exact_integer_http_200(self):
        for field, value in (
            ("session_discovery_request_attempted", False),
            ("starting_grid_request_attempted", False),
            ("session_discovery_http_status_code", 403),
            ("starting_grid_http_status_code", "200"),
        ):
            with self.subTest(field=field):
                members = self.artifact_members(
                    "starting_grid", manifest_changes={field: value}
                )
                root = self.write_artifact("starting_grid", members=members)
                self.assert_hold(lambda: self.build("starting_grid", root=root))

    # 28
    def test_prepare_writes_only_canonical_manifest(self):
        _root, output, manifest_bytes, _bundle = self.prepared_output("weather")
        self.assertEqual([path.name for path in output.iterdir()], ["custody_manifest.json"])
        self.assertEqual((output / "custody_manifest.json").read_bytes(), manifest_bytes)
        self.assertEqual(m.canonical_json_bytes(json.loads(manifest_bytes)), manifest_bytes)

    # 29
    def test_local_bundle_preservation_never_claims_verification(self):
        _root, output, manifest_bytes, bundle_path = self.prepared_output("weather")
        metadata_bytes = self.preserve(output, bundle_path)
        metadata = json.loads(metadata_bytes)
        self.assertEqual(
            metadata["subject_sha256"], hashlib.sha256(manifest_bytes).hexdigest()
        )
        self.assertTrue(metadata["dsse_subject_digest_consistency_checked"])
        self.assertTrue(all(
            metadata[field] is False for field in m.LOCAL_ONLY_FALSE_FLAGS
        ))
        self.assertTrue(all(metadata[field] is False for field in m.FALSE_FLAGS))

    # 30
    def test_bundle_and_manifest_bytes_are_preserved_exactly(self):
        _root, output, manifest_bytes, bundle_path = self.prepared_output("drivers")
        bundle_bytes = bundle_path.read_bytes()
        self.preserve(output, bundle_path)
        self.assertEqual((output / "custody_manifest.json").read_bytes(), manifest_bytes)
        self.assertEqual((output / "github_attestation.bundle.json").read_bytes(), bundle_bytes)

    # 31
    def test_empty_or_malformed_fake_signature_holds(self):
        root, output, manifest_bytes, _bundle_path = self.prepared_output("weather")
        bundle_path = root / "bad.bundle.json"
        bundle_path.write_bytes(self.fake_bundle(manifest_bytes, signature=b""))
        self.assert_hold(lambda: self.preserve(output, bundle_path), "signature")
        self.assertFalse((output / "github_attestation_metadata.json").exists())

    # 32
    def test_wrong_dsse_subject_digest_holds(self):
        root, output, manifest_bytes, _bundle_path = self.prepared_output("weather")
        bundle_path = root / "wrong.bundle.json"
        bundle_path.write_bytes(self.fake_bundle(manifest_bytes, digest="0" * 64))
        self.assert_hold(lambda: self.preserve(output, bundle_path), "digest")

    # 33
    def test_attestation_output_identity_mismatch_holds(self):
        _root, output, _manifest_bytes, bundle_path = self.prepared_output("weather")
        self.assert_hold(
            lambda: self.preserve(output, bundle_path, head_sha="b" * 40),
            "execution_mismatch:head_sha",
        )

    # 34
    def test_original_workflow_bytes_are_exactly_unchanged_before_new_job(self):
        assert_workflow_compatibility(self, WORKFLOW.read_bytes())

    def test_workflow_compatibility_rejects_protected_mutations(self):
        predecessor = git_blob_bytes(PREDECESSOR_WORKFLOW_BLOB)
        successor = git_blob_bytes(SUCCESSOR_WORKFLOW_BLOB)
        cases = {
            "manual_weather_driver_grid_inputs": predecessor.replace(
                b"          - drivers\n", b"          - drivers_changed\n", 1
            ),
            "publication_block": successor.replace(
                b"--expected-completed-only", b"--completed-only-unbound", 1
            ),
            "top_level_permissions": predecessor.replace(
                b"permissions:\n  contents: write",
                b"permissions:\n  contents: read", 1,
            ),
            "custody_permissions": successor.replace(
                b"      id-token: write", b"      id-token: read", 1
            ),
            "custody_suffix": predecessor.replace(
                b"actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6",
                b"actions/attest@unauthorized", 1,
            ),
        }
        for label, changed in cases.items():
            with self.subTest(label=label), self.assertRaises(AssertionError):
                assert_workflow_compatibility(self, changed)

    # 35
    def test_workflow_has_exactly_one_added_follow_on_job(self):
        parsed = yaml.safe_load(WORKFLOW.read_text())
        self.assertEqual(set(parsed["jobs"]), {
            "openf1-lightweight-source-closure",
            "openf1-manual-shadow-custody-attestation",
        })
        job = parsed["jobs"]["openf1-manual-shadow-custody-attestation"]
        self.assertEqual(job["needs"], "openf1-lightweight-source-closure")
        self.assertEqual(job["runs-on"], "ubuntu-latest")

    # 36
    def test_follow_on_job_has_only_required_explicit_permissions(self):
        parsed = yaml.safe_load(WORKFLOW.read_text())
        permissions = parsed["jobs"][
            "openf1-manual-shadow-custody-attestation"
        ]["permissions"]
        self.assertEqual(permissions, {
            "contents": "read",
            "actions": "read",
            "id-token": "write",
            "attestations": "write",
        })

    # 37
    def test_job_condition_skips_schedule_empty_key_invalid_endpoint_and_failure(self):
        def allowed(event, key, ref, endpoint, result):
            return (
                event == "workflow_dispatch"
                and key != ""
                and ref == m.MAIN_REF
                and endpoint in m.EXPECTED_MEMBERS
                and result == "success"
            )

        self.assertFalse(allowed("schedule", "1", m.MAIN_REF, "weather", "success"))
        self.assertFalse(allowed("workflow_dispatch", "", m.MAIN_REF, "weather", "success"))
        self.assertFalse(allowed("workflow_dispatch", "1", m.MAIN_REF, "bad", "success"))
        self.assertFalse(allowed("workflow_dispatch", "1", m.MAIN_REF, "weather", "failure"))
        self.assertTrue(allowed("workflow_dispatch", "1", m.MAIN_REF, "weather", "success"))
        condition = yaml.safe_load(WORKFLOW.read_text())["jobs"][
            "openf1-manual-shadow-custody-attestation"
        ]["if"]
        for value in (
            "workflow_dispatch", "provenance_shadow_session_key", "refs/heads/main",
            "weather", "drivers", "starting_grid", ".result == 'success'",
        ):
            self.assertIn(value, condition)

    # 38
    def test_exact_h2_attestation_action_and_official_download_pin_are_used(self):
        suffix = WORKFLOW.read_text().split(
            "# K4R28 manual-shadow custody follow-on job; original workflow above is unchanged.\n"
        )[1]
        self.assertEqual(suffix.count(m.ATTESTATION_ACTION), 1)
        self.assertEqual(
            suffix.count(
                "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093"
            ),
            1,
        )

    # 39
    def test_checkout_is_exact_head_and_credentials_are_disabled(self):
        parsed = yaml.safe_load(WORKFLOW.read_text())
        steps = parsed["jobs"]["openf1-manual-shadow-custody-attestation"]["steps"]
        checkout = next(step for step in steps if step.get("uses") == "actions/checkout@v6")
        self.assertEqual(checkout["with"]["ref"], "${{ github.sha }}")
        self.assertFalse(checkout["with"]["persist-credentials"])

    # 40
    def test_new_job_has_no_provider_request_or_repository_write_surface(self):
        suffix = WORKFLOW.read_text().split(
            "# K4R28 manual-shadow custody follow-on job; original workflow above is unchanged.\n"
        )[1]
        for forbidden in (
            "api.openf1.org", "requests", "curl ", "wget ", "git push",
            "contents: write", "latest/", "history/",
        ):
            self.assertNotIn(forbidden, suffix)

    # 41
    def test_custody_upload_excludes_downloaded_original_source(self):
        parsed = yaml.safe_load(WORKFLOW.read_text())
        steps = parsed["jobs"]["openf1-manual-shadow-custody-attestation"]["steps"]
        upload = steps[-1]
        self.assertEqual(upload["uses"], "actions/upload-artifact@v6")
        self.assertNotIn("source_artifact", upload["with"]["path"])
        self.assertEqual(upload["with"]["retention-days"], 30)
        self.assertEqual(upload["with"]["if-no-files-found"], "error")

    # 42
    def test_prepare_precedes_attestation_and_preservation(self):
        parsed = yaml.safe_load(WORKFLOW.read_text())
        steps = parsed["jobs"]["openf1-manual-shadow-custody-attestation"]["steps"]
        names = [step.get("name", "") for step in steps]
        self.assertLess(
            names.index("Validate original evidence and prepare exact custody manifest"),
            names.index("Attest exact successful custody manifest"),
        )
        self.assertLess(
            names.index("Attest exact successful custody manifest"),
            names.index("Preserve exact bundle and factual unverified metadata"),
        )


if __name__ == "__main__":
    unittest.main()
