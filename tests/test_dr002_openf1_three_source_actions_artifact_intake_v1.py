import ast
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import struct
import sys
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "scripts/forecast_bundles"
SCRIPT = BUNDLE_DIR / "dr002_openf1_three_source_actions_artifact_intake_v1.py"
FIXTURE_SCRIPT = (
    ROOT / "tests/test_dr002_openf1_three_source_precutoff_candidate_v1.py"
)
sys.path.insert(0, str(BUNDLE_DIR))

spec = importlib.util.spec_from_file_location("actions_artifact_intake", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

fixture_spec = importlib.util.spec_from_file_location(
    "precutoff_candidate_fixture", FIXTURE_SCRIPT
)
_fixture_module = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(_fixture_module)


class ThreeSourceActionsArtifactIntakeTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        fixture_type = _fixture_module.ThreeSourcePrecutoffCandidateTests
        self.fixture = fixture_type(
            "test_valid_synthetic_event_is_only_unauthenticated_candidate"
        )
        self.fixture.setUp()
        self.archives = self.build_archives()

    @staticmethod
    def json_bytes(value):
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")

    @staticmethod
    def zip_bytes(members, *, compression=zipfile.ZIP_DEFLATED,
                  attrs=None, duplicate=None):
        sink = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(sink, "w") as archive:
                for name, data in members.items():
                    info = zipfile.ZipInfo(name, (2026, 10, 14, 0, 0, 0))
                    info.create_system = 3
                    info.compress_type = compression
                    info.external_attr = (
                        (stat.S_IFREG | 0o644) << 16
                        if attrs is None or name not in attrs
                        else attrs[name]
                    )
                    archive.writestr(info, data)
                if duplicate is not None:
                    info = zipfile.ZipInfo(duplicate, (2026, 10, 14, 0, 0, 0))
                    info.create_system = 3
                    info.compress_type = compression
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(info, members[duplicate])
        return sink.getvalue()

    def sidecar_members(self, role, *, receipt_bytes=None, raw=None,
                        sessions=None, manifest_changes=None):
        f = self.fixture
        if role == "weather":
            raw = f.weather_raw if raw is None else raw
            receipt_bytes = f.weather_receipt if receipt_bytes is None else receipt_bytes
            session_id = f.practice_id
            raw_name = "weather.response.json"
        elif role == "drivers":
            raw = f.drivers_raw if raw is None else raw
            receipt_bytes = f.drivers_receipt if receipt_bytes is None else receipt_bytes
            session_id = f.practice_id
            raw_name = "drivers.response.json"
        else:
            raw = f.grid_raw if raw is None else raw
            receipt_bytes = f.grid_receipt if receipt_bytes is None else receipt_bytes
            session_id = f.qualifying_id
            raw_name = "starting_grid.response.json"

        receipt = json.loads(receipt_bytes)
        payload = receipt["payload"]
        raw_sha = hashlib.sha256(raw).hexdigest()
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        common = {
            "status": m.capture_contract.VALIDATED,
            "k4r1_status": m.capture_contract.VALIDATED,
            "event_id": f.event_id,
            "meeting_id": f.meeting_id,
            "session_id": session_id,
            "raw_response_sha256": raw_sha,
            "receipt_sha256": receipt_sha,
            "receipt_type": "source_capture",
            "canonical_request_uri": payload["source_uri"],
            "first_observed_utc": payload["first_observed_utc"],
            "ingested_utc": payload["ingested_utc"],
            "receipt_created_utc": receipt["receipt_created_utc"],
            "verified_receipt_bindings_created": False,
            "latest_or_history_written": False,
            "repository_mutation_performed": False,
            "dr002_activated": False,
            "promotion_allowed": False,
        }
        if role == "drivers":
            common.update({
                "selected_endpoint": "drivers",
                "raw_response_filename": raw_name,
                "k4r6_status": m.drivers_adapter.VALIDATED,
            })
        elif role == "starting_grid":
            sessions = f.sessions_raw if sessions is None else sessions
            manifest = f.valid_manifest(
                grid_receipt=receipt_bytes, grid_raw=raw, sessions_raw=sessions
            )
            manifest.update(common)
            manifest.update({
                "raw_response_filename": raw_name,
                "session_discovery_filename": "sessions.response.json",
            })
            common = manifest

        if manifest_changes:
            common.update(manifest_changes)
        assessment = {
            "status": m.capture_contract.VALIDATED,
            "raw_response_sha256": raw_sha,
            "receipt_sha256": receipt_sha,
            "canonical_request_uri": payload["source_uri"],
        }
        members = {
            raw_name: raw,
            "source_capture_receipt.json": receipt_bytes,
            "shadow_manifest.json": self.json_bytes(common),
            "shadow_report.md": b"# DR-002 synthetic provenance shadow\n",
            "historical_rest_capture_assessment.json": self.json_bytes(assessment),
        }
        if role == "starting_grid":
            members["sessions.response.json"] = sessions
        return members

    def build_archives(self, **role_options):
        return {
            role: self.zip_bytes(self.sidecar_members(
                role, **role_options.get(role, {})
            ))
            for role in ("weather", "drivers", "starting_grid")
        }

    def args(self, *, archives=None, **changes):
        f = self.fixture
        archives = self.archives if archives is None else archives
        result = {
            "weather_artifact_zip_bytes": archives["weather"],
            "weather_archive_sha256": hashlib.sha256(
                archives["weather"]
            ).hexdigest(),
            "drivers_artifact_zip_bytes": archives["drivers"],
            "drivers_archive_sha256": hashlib.sha256(
                archives["drivers"]
            ).hexdigest(),
            "grid_artifact_zip_bytes": archives["starting_grid"],
            "grid_archive_sha256": hashlib.sha256(
                archives["starting_grid"]
            ).hexdigest(),
            "event_id": f.event_id,
            "meeting_id": f.meeting_id,
            "practice_session_id": f.practice_id,
            "qualifying_source_session_id": f.qualifying_id,
            "target_race_session_id": f.race_id,
            "forecast_cutoff_utc": f.cutoff,
        }
        result.update(changes)
        return result

    def assess(self, *, archives=None, **changes):
        return m.assess_openf1_three_source_actions_artifact_intake(
            **self.args(archives=archives, **changes)
        )

    def replace_archive(self, role, members, **zip_options):
        archives = dict(self.archives)
        archives[role] = self.zip_bytes(members, **zip_options)
        return archives

    def assert_hold_minimal(self, result):
        self.assertEqual(result["status"], m.HOLD)
        self.assertEqual(set(result), {
            "schema_version", "status", "reason_codes", *m.FALSE_FLAGS
        })
        self.assertTrue(result["reason_codes"])
        self.assertLessEqual(len(result["reason_codes"]), 8)
        self.assertTrue(all(result[field] is False for field in m.FALSE_FLAGS))
        serialized = json.dumps(result)
        self.assertNotIn("source_capture:", serialized)
        self.assertNotIn(fixture_digest := hashlib.sha256(
            self.archives["weather"]
        ).hexdigest(), serialized)
        self.assertTrue(fixture_digest)

    def test_valid_archives_return_only_unauthenticated_candidate(self):
        result = self.assess()
        self.assertEqual(result["status"], m.VALIDATED)
        self.assertEqual(result["classification"], m.CLASSIFICATION)
        self.assertTrue(result["candidate_content_is_in_memory_only"])
        self.assertEqual(result["candidate_result"]["status"], m.precutoff.VALIDATED)
        for role, archive in self.archives.items():
            self.assertEqual(
                result["archive_bindings"][role]["archive_sha256"],
                hashlib.sha256(archive).hexdigest(),
            )

    def test_embedded_candidate_and_manifest_hash_match_direct_k4r26(self):
        f = self.fixture
        result = self.assess()
        expected = m.precutoff.assess_openf1_three_source_precutoff_candidate(
            weather_source_capture_receipt_bytes=f.weather_receipt,
            raw_weather_response_bytes=f.weather_raw,
            drivers_source_capture_receipt_bytes=f.drivers_receipt,
            raw_drivers_response_bytes=f.drivers_raw,
            starting_grid_source_capture_receipt_bytes=f.grid_receipt,
            raw_starting_grid_response_bytes=f.grid_raw,
            sessions_response_bytes=f.sessions_raw,
            grid_shadow_manifest_bytes=self.sidecar_members(
                "starting_grid"
            )["shadow_manifest.json"],
            event_id=f.event_id,
            meeting_id=f.meeting_id,
            practice_session_id=f.practice_id,
            qualifying_source_session_id=f.qualifying_id,
            target_race_session_id=f.race_id,
            forecast_cutoff_utc=f.cutoff,
        )
        self.assertEqual(result["candidate_result"], expected)
        candidate = result["candidate_result"]
        self.assertEqual(
            candidate["candidate_manifest_sha256"],
            hashlib.sha256(candidate["candidate_manifest_bytes"]).hexdigest(),
        )

    def test_success_preserves_three_distinct_session_roles(self):
        result = self.assess()
        provenance = result["original_source_to_session_provenance"]
        self.assertEqual(provenance["weather"]["session_id"], self.fixture.practice_id)
        self.assertEqual(provenance["drivers"]["session_id"], self.fixture.practice_id)
        self.assertEqual(
            provenance["starting_grid"]["session_id"], self.fixture.qualifying_id
        )
        self.assertEqual(
            provenance["starting_grid"]["target_race_session_id"],
            self.fixture.race_id,
        )

    def test_all_scientific_and_operational_claims_remain_false(self):
        result = self.assess()
        self.assertTrue(all(result[field] is False for field in m.FALSE_FLAGS))

    def test_claimed_github_ids_are_explicitly_unverified(self):
        result = self.assess(
            weather_claimed_run_id="101", weather_claimed_artifact_id="201",
            drivers_claimed_run_id="102", drivers_claimed_artifact_id="202",
            grid_claimed_run_id="103", grid_claimed_artifact_id="203",
        )
        self.assertEqual(result["status"], m.VALIDATED)
        for binding in result["archive_bindings"].values():
            self.assertEqual(
                binding["claimed_identity_status"], "UNVERIFIED_CALLER_ASSERTION"
            )
            self.assertFalse(binding["github_identity_verified"])
            self.assertFalse(binding["archive_digest_is_github_custody_attestation"])

    def test_identical_inputs_are_deterministic(self):
        self.assertEqual(self.assess(), self.assess())

    def test_k4r26_is_invoked_exactly_once_after_valid_preflight(self):
        real = m.precutoff.assess_openf1_three_source_precutoff_candidate
        with mock.patch.object(
            m.precutoff,
            "assess_openf1_three_source_precutoff_candidate",
            wraps=real,
        ) as call:
            result = self.assess()
        self.assertEqual(result["status"], m.VALIDATED)
        call.assert_called_once()
        supplied = call.call_args.kwargs
        self.assertEqual(
            supplied["weather_source_capture_receipt_bytes"],
            self.fixture.weather_receipt,
        )
        self.assertEqual(supplied["raw_weather_response_bytes"], self.fixture.weather_raw)
        self.assertEqual(supplied["raw_drivers_response_bytes"], self.fixture.drivers_raw)
        self.assertEqual(supplied["raw_starting_grid_response_bytes"], self.fixture.grid_raw)

    def test_k4r26_is_not_invoked_for_archive_digest_failure(self):
        with mock.patch.object(
            m.precutoff, "assess_openf1_three_source_precutoff_candidate"
        ) as call:
            result = self.assess(weather_archive_sha256="0" * 64)
        self.assert_hold_minimal(result)
        call.assert_not_called()

    def test_each_archive_digest_is_independently_required(self):
        for field in (
            "weather_archive_sha256",
            "drivers_archive_sha256",
            "grid_archive_sha256",
        ):
            with self.subTest(field=field):
                self.assert_hold_minimal(self.assess(**{field: "f" * 64}))

    def test_malformed_digest_and_claimed_identity_hold(self):
        for field, value in (
            ("weather_archive_sha256", "A" * 64),
            ("weather_claimed_run_id", 1),
            ("grid_claimed_artifact_id", "01"),
        ):
            with self.subTest(field=field):
                self.assert_hold_minimal(self.assess(**{field: value}))

    def test_nonbytes_and_empty_archives_hold(self):
        for field, value in (
            ("weather_artifact_zip_bytes", bytearray(b"zip")),
            ("drivers_artifact_zip_bytes", b""),
            ("grid_artifact_zip_bytes", None),
        ):
            with self.subTest(field=field):
                self.assert_hold_minimal(self.assess(**{field: value}))

    def test_truncated_archive_holds(self):
        archives = dict(self.archives)
        archives["weather"] = archives["weather"][:-12]
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_prefixed_archive_holds_as_ambiguous(self):
        archives = dict(self.archives)
        archives["weather"] = b"hidden-prefix" + archives["weather"]
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_trailing_archive_bytes_hold_as_ambiguous(self):
        archives = dict(self.archives)
        archives["drivers"] += b"hidden-trailer"
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_wrong_member_set_holds(self):
        members = self.sidecar_members("weather")
        members["wrong.response.json"] = members.pop("weather.response.json")
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("weather", members)
        ))

    def test_extra_hidden_member_holds(self):
        members = self.sidecar_members("drivers")
        members[".hidden"] = b"forbidden"
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("drivers", members)
        ))

    def test_duplicate_member_holds(self):
        members = self.sidecar_members("weather")
        archives = self.replace_archive(
            "weather", members, duplicate="weather.response.json"
        )
        result = self.assess(archives=archives)
        self.assert_hold_minimal(result)
        self.assertIn("weather_archive_duplicate_member", result["reason_codes"])

    def test_directory_entry_holds(self):
        members = self.sidecar_members("weather")
        members["folder/"] = b""
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("weather", members)
        ))

    def test_unsafe_path_spellings_hold(self):
        for unsafe in (
            "../weather.response.json",
            "/weather.response.json",
            "folder\\weather.response.json",
            "%2e%2e-weather.response.json",
        ):
            with self.subTest(name=unsafe):
                members = self.sidecar_members("weather")
                members[unsafe] = members.pop("weather.response.json")
                self.assert_hold_minimal(self.assess(
                    archives=self.replace_archive("weather", members)
                ))

    def test_symlink_entry_holds(self):
        members = self.sidecar_members("weather")
        attrs = {"weather.response.json": (stat.S_IFLNK | 0o777) << 16}
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("weather", members, attrs=attrs)
        ))

    def test_special_file_entry_holds(self):
        members = self.sidecar_members("drivers")
        attrs = {"drivers.response.json": (stat.S_IFIFO | 0o644) << 16}
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("drivers", members, attrs=attrs)
        ))

    @staticmethod
    def patch_zip_metadata(data, *, flag_bits=None, compression=None):
        changed = bytearray(data)
        start = 0
        while True:
            offset = changed.find(b"PK\x03\x04", start)
            if offset < 0:
                break
            if flag_bits is not None:
                struct.pack_into("<H", changed, offset + 6, flag_bits)
            if compression is not None:
                struct.pack_into("<H", changed, offset + 8, compression)
            start = offset + 4
        start = 0
        while True:
            offset = changed.find(b"PK\x01\x02", start)
            if offset < 0:
                break
            if flag_bits is not None:
                struct.pack_into("<H", changed, offset + 8, flag_bits)
            if compression is not None:
                struct.pack_into("<H", changed, offset + 10, compression)
            start = offset + 4
        return bytes(changed)

    def test_encrypted_flag_holds(self):
        archives = dict(self.archives)
        archives["weather"] = self.patch_zip_metadata(
            archives["weather"], flag_bits=1
        )
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_unsupported_compression_holds(self):
        archives = dict(self.archives)
        archives["drivers"] = self.patch_zip_metadata(
            archives["drivers"], compression=99
        )
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_bad_crc_holds(self):
        members = self.sidecar_members("weather")
        archive = bytearray(self.zip_bytes(members, compression=zipfile.ZIP_STORED))
        raw = members["weather.response.json"]
        offset = archive.find(raw)
        self.assertGreaterEqual(offset, 0)
        archive[offset] ^= 1
        archives = dict(self.archives)
        archives["weather"] = bytes(archive)
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_high_compression_ratio_holds(self):
        members = self.sidecar_members("weather")
        members["shadow_report.md"] = b"# DR-002 " + b"0" * (1024 * 1024)
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("weather", members)
        ))

    def test_archive_and_member_size_caps_hold(self):
        with mock.patch.object(m, "MAX_ARCHIVE_BYTES", 1):
            self.assert_hold_minimal(self.assess())
        with mock.patch.object(m, "MAX_MEMBER_BYTES", 1):
            self.assert_hold_minimal(self.assess())

    def test_swapped_role_archives_hold(self):
        archives = dict(self.archives)
        archives["weather"], archives["drivers"] = (
            archives["drivers"], archives["weather"]
        )
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_raw_tamper_with_stale_sidecars_holds(self):
        members = self.sidecar_members("drivers")
        members["drivers.response.json"] += b" "
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("drivers", members)
        ))

    def test_receipt_tamper_with_stale_sidecars_holds(self):
        members = self.sidecar_members("weather")
        members["source_capture_receipt.json"] += b" "
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("weather", members)
        ))

    def test_grid_manifest_missing_request_attempt_or_http_200_holds(self):
        for field, value in (
            ("session_discovery_request_attempted", False),
            ("starting_grid_request_attempted", False),
            ("session_discovery_http_status_code", 403),
            ("starting_grid_http_status_code", "200"),
        ):
            with self.subTest(field=field):
                archives = self.build_archives(starting_grid={
                    "manifest_changes": {field: value}
                })
                self.assert_hold_minimal(self.assess(archives=archives))

    def test_grid_session_discovery_tamper_holds(self):
        members = self.sidecar_members("starting_grid")
        members["sessions.response.json"] += b" "
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("starting_grid", members)
        ))

    def test_sidecar_scope_mismatch_holds_before_k4r26(self):
        archives = self.build_archives(drivers={
            "manifest_changes": {"session_id": "9999"}
        })
        with mock.patch.object(
            m.precutoff, "assess_openf1_three_source_precutoff_candidate"
        ) as call:
            result = self.assess(archives=archives)
        self.assert_hold_minimal(result)
        call.assert_not_called()

    def test_cross_circuit_session_discovery_propagates_k4r26_hold(self):
        sessions = copy.deepcopy(self.fixture.sessions)
        sessions[2]["circuit_short_name"] = "Other Ring"
        sessions_raw = self.json_bytes(sessions)
        archives = self.build_archives(starting_grid={"sessions": sessions_raw})
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_sidecar_duplicate_json_key_holds(self):
        members = self.sidecar_members("weather")
        members["historical_rest_capture_assessment.json"] = (
            b'{"status":"x","status":"y"}'
        )
        self.assert_hold_minimal(self.assess(
            archives=self.replace_archive("weather", members)
        ))

    def test_mismatched_driver_grid_roster_propagates_minimal_k4r26_hold(self):
        f = self.fixture
        raw = f.json_bytes(f.drivers_rows[:-1])
        receipt = f.receipt(
            "drivers", f.practice_id, raw,
            "2026-01-02T13:33:00Z", "2026-01-02T13:34:00Z",
            "2026-01-02T13:35:00Z",
        )
        archives = self.build_archives(drivers={
            "raw": raw, "receipt_bytes": receipt
        })
        result = self.assess(archives=archives)
        self.assert_hold_minimal(result)
        self.assertTrue(result["reason_codes"][0].startswith("k4r26_hold:"))

    def test_every_source_after_cutoff_receipt_propagates_hold(self):
        f = self.fixture
        cases = (
            ("weather", "weather", f.practice_id, f.weather_raw),
            ("drivers", "drivers", f.practice_id, f.drivers_raw),
            ("starting_grid", "starting_grid", f.qualifying_id, f.grid_raw),
        )
        for role, endpoint, session_id, raw in cases:
            with self.subTest(role=role):
                receipt = f.receipt(
                    endpoint, session_id, raw,
                    "2026-01-03T14:01:00Z", "2026-01-03T14:02:00Z",
                    "2026-01-03T14:03:00Z",
                )
                archives = self.build_archives(**{
                    role: {"receipt_bytes": receipt}
                })
                self.assert_hold_minimal(self.assess(archives=archives))

    def test_post_race_k4r21_eligibility_cannot_be_laundered_as_prospective(self):
        f = self.fixture
        post_weather = f.receipt(
            "weather", f.practice_id, f.weather_raw,
            "2026-01-05T10:00:00Z", "2026-01-05T10:01:00Z",
            "2026-01-05T10:02:00Z",
        )
        post_drivers = f.receipt(
            "drivers", f.practice_id, f.drivers_raw,
            "2026-01-05T10:03:00Z", "2026-01-05T10:04:00Z",
            "2026-01-05T10:05:00Z",
        )
        post_grid = f.receipt(
            "starting_grid", f.qualifying_id, f.grid_raw,
            "2026-01-05T10:06:00Z", "2026-01-05T10:07:00Z",
            "2026-01-05T10:08:00Z",
        )
        manifest = f.json_bytes(f.valid_manifest(grid_receipt=post_grid))
        historical = _fixture_module.compatibility.assess_openf1_three_source_event_compatibility(
            weather_source_capture_receipt_bytes=post_weather,
            raw_weather_response_bytes=f.weather_raw,
            drivers_source_capture_receipt_bytes=post_drivers,
            raw_drivers_response_bytes=f.drivers_raw,
            starting_grid_source_capture_receipt_bytes=post_grid,
            raw_starting_grid_response_bytes=f.grid_raw,
            sessions_response_bytes=f.sessions_raw,
            grid_shadow_manifest_bytes=manifest,
            event_id=f.event_id,
            meeting_id=f.meeting_id,
            practice_session_id=f.practice_id,
            qualifying_source_session_id=f.qualifying_id,
            target_race_session_id=f.race_id,
        )
        self.assertEqual(historical["status"], _fixture_module.compatibility.VALIDATED)
        archives = self.build_archives(
            weather={"receipt_bytes": post_weather},
            drivers={"receipt_bytes": post_drivers},
            starting_grid={"receipt_bytes": post_grid},
        )
        self.assert_hold_minimal(self.assess(archives=archives))

    def test_malformed_candidate_result_is_minimal_hold(self):
        with mock.patch.object(
            m.precutoff,
            "assess_openf1_three_source_precutoff_candidate",
            return_value={"status": m.precutoff.VALIDATED},
        ):
            self.assert_hold_minimal(self.assess())

    def test_source_has_no_filesystem_network_clock_workflow_or_producer_surface(self):
        tree = ast.parse(SCRIPT.read_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imported.isdisjoint({
            "os", "pathlib", "requests", "urllib", "socket", "subprocess",
            "tempfile", "time", "datetime",
        }))
        text = SCRIPT.read_text()
        for forbidden in (
            "produce_actual_forecast_rows_v1", "evaluate_as_of(", "urlopen(",
            "requests.", "subprocess.", "Path(", "datetime.now",
            "datetime.utcnow",
        ):
            self.assertNotIn(forbidden, text)
        with mock.patch("builtins.open", side_effect=AssertionError("filesystem")):
            self.assertEqual(self.assess()["status"], m.VALIDATED)


if __name__ == "__main__":
    unittest.main()
