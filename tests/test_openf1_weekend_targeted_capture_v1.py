"""Issue #359: deterministic offline targeted acquisition and independent replay.

Synthetic HTTP responses are not publisher attestation or genuine Mexico
telemetry. Retained Mexico manifests are used only as immutable identity checks.
"""
import copy
import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Minimal offline images need not install HTTP/progress packages. A missing
# dependency is stubbed only in this test process, never in implementation.
if "requests" not in sys.modules:
    try:
        import requests
    except ModuleNotFoundError:
        requests = types.ModuleType("requests")
        requests.get = mock.Mock(side_effect=AssertionError("live HTTP forbidden"))
        sys.modules["requests"] = requests
try:
    import tqdm.auto
except ModuleNotFoundError:
    tqdm = types.ModuleType("tqdm")
    tqdm_auto = types.ModuleType("tqdm.auto")
    tqdm_auto.tqdm = lambda iterable, **kwargs: iterable
    sys.modules["tqdm"] = tqdm
    sys.modules["tqdm.auto"] = tqdm_auto

from scripts.openf1 import openf1_high_frequency_auto_ingest as m

NOW = "2026-10-31T15:00:00+00:00"


def encode(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


class Clock:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def time(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds

    def utc(self):
        return (dt.datetime.fromisoformat(NOW) + dt.timedelta(seconds=self.value)).isoformat()


class Response:
    def __init__(self, raw, url, status=200, headers=None, chunk_size=91):
        self.raw, self.url, self.status_code = raw, url, status
        self.headers = {"Content-Length": str(len(raw))} if headers is None else headers
        self.chunk_size = chunk_size
        self.closed = False
        self.chunks_read = 0

    def iter_content(self, chunk_size):
        for i in range(0, len(self.raw), self.chunk_size):
            self.chunks_read += 1
            yield self.raw[i:i + self.chunk_size]

    def close(self):
        self.closed = True


class TargetedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "experimental" / "capture"
        self.spec = {"year": 2026, "meeting_key": 1298, "targets": [
            {"session_key": 11397, "driver_numbers": [1, 44]},
            {"session_key": 11398, "driver_numbers": [18]},
        ]}
        sessions = []
        for sk, start, end, name in [(11397, "18:30", "19:30", "Practice 1"), (11398, "22:00", "23:00", "Practice 2")]:
            sessions.append({"session_key": sk, "meeting_key": 1298, "year": 2026,
                             "country_name": "Mexico", "location": "Mexico City",
                             "circuit_short_name": "Mexico City", "session_name": name,
                             "session_type": "Practice", "date_start": f"2026-10-30T{start}:00Z",
                             "date_end": f"2026-10-30T{end}:00Z", "completion_confirmed": True,
                             "completion_observed_at_utc": f"2026-10-30T{end}:00Z"})
        # Unselected history proves no season sweep, without inventing FP3 IDs.
        history = dict(sessions[0], session_key=1, meeting_key=1)
        self.metadata = {"observed_at_utc": "2026-10-31T01:00:00Z", "sessions": sessions + [history]}
        self.roster = {"observed_at_utc": "2026-10-31T01:00:00Z", "drivers": [
            {"meeting_key": 1298, "session_key": sk, "driver_number": dn}
            for sk, dns in [(11397, [1, 44]), (11398, [18])] for dn in dns]}
        self.clock = Clock()
        self.calls, self.responses = [], []
        self.handler = None
        self.network = mock.patch.object(socket.socket, "connect", side_effect=AssertionError("live socket forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def inputs(self, *, now=NOW):
        paths = []
        for name, value in [("spec", self.spec), ("metadata", self.metadata), ("roster", self.roster)]:
            path = self.root / (name + ".json")
            path.write_bytes(encode(value))
            paths.append(path)
        return m.load_target_plan(paths[0], paths[1], m.target_sha(paths[1].read_bytes()),
                                  paths[2], m.target_sha(paths[2].read_bytes()), now=now)

    def rows(self, endpoint, params):
        s = next(s for s in self.metadata["sessions"] if s["session_key"] == params["session_key"])
        values = {"rpm": 9000, "speed": 200, "n_gear": 5, "throttle": 90, "brake": 0} if endpoint == "car_data" else {"x": 1, "y": 2, "z": 3}
        return [dict(meeting_key=1298, **params, date=s["date_start"], **values),
                dict(meeting_key=1298, **params, date=s["date_end"], **values)]

    def get(self, url, *, params, stream, allow_redirects, headers, timeout):
        self.assertTrue(stream)
        self.assertFalse(allow_redirects)
        self.assertEqual(headers, {"Accept-Encoding": "identity"})
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append((endpoint, dict(params), self.clock.value))
        response = Response(encode(self.rows(endpoint, params)), url + "?" + urlencode(params))
        if self.handler:
            self.handler(response, endpoint, params)
        self.responses.append(response)
        return response

    def capture(self, *, plan=None, **kwargs):
        return m.capture_targeted(plan or self.inputs(), self.output, http_get=self.get,
                                  budget=m.target_budget(clock=self.clock.time, sleeper=self.clock.sleep,
                                                         max_requests=kwargs.pop("max_requests", 720),
                                                         max_elapsed_seconds=kwargs.pop("max_seconds", 1440)),
                                  utc_clock=self.clock.utc, **kwargs)

    def assert_hold(self, result, reason=None):
        self.assertIs(result["hold"], True)
        self.assertEqual(result["status"], "HOLD")
        if reason:
            self.assertEqual(result["reason"], reason)
        for key in m.TARGET_TRUST:
            self.assertIs(result[key], False)

    def mutate_packet(self, change):
        path = self.output / "targeted_manifest.json"
        value = json.loads(path.read_text())
        change(value)
        path.write_bytes(encode(value))

    def test_exact_two_session_selection_bytes_hashes_timestamps_and_full_matrix(self):
        plan = self.inputs()
        result = self.capture(plan=plan)
        self.assertEqual(result["status"], "PASS")
        expected = [(ep, {"session_key": s["session_key"], "driver_number": dn}) for s, dn, ep in m.target_expected(plan)]
        self.assertEqual([(ep, p) for ep, p, _ in self.calls], expected)
        self.assertEqual([t for _, _, t in self.calls], [0, 0, 0, 1, 1, 1])
        self.assertEqual(len(result["entries"]), 6)
        self.assertEqual(m.verify_targeted_packet(self.output, plan, now=self.clock.utc())["status"], "PASS")
        for entry, response in zip(result["entries"], self.responses):
            self.assertEqual((self.output / entry["file_path"]).read_bytes(), response.raw)
            self.assertEqual(entry["sha256"], hashlib.sha256(response.raw).hexdigest())
            self.assertEqual(entry["size_bytes"], len(response.raw))
            self.assertEqual(entry["rows"], 2)
            self.assertTrue(response.closed)
        for key in m.TARGET_TRUST:
            self.assertIs(result[key], False)
        self.assertIs(result["provider_sampling_completeness_established"], False)
        self.assertFalse((self.root / "latest").exists())
        self.assertFalse((self.root / "history").exists())

    def test_two_22_driver_sessions_share_second_and_minute_budget(self):
        for item in self.spec["targets"]:
            item["driver_numbers"] = list(range(1, 23))
        self.roster["drivers"] = [
            {"meeting_key": 1298, "session_key": sk, "driver_number": dn}
            for sk in (11397, 11398) for dn in range(1, 23)]
        result = self.capture()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(self.calls), 88)
        self.assertEqual(len(result["entries"]), 88)
        times = [t for _, _, t in self.calls]
        self.assertEqual(times[3], 1.0)
        self.assertEqual(times[30], 60.0)
        self.assertEqual(times[60], 120.0)
        for now in times:
            self.assertLessEqual(sum(now - 1 < t <= now for t in times), 3)
            self.assertLessEqual(sum(now - 60 < t <= now for t in times), 30)
        self.assertEqual(result["request_budget"]["provider_requests_performed"], 88)
        self.assertEqual(m.verify_targeted_packet(self.output, self.inputs(), now=self.clock.utc())["status"], "PASS")

    def test_explicit_roster_subset_cannot_self_certify_coverage(self):
        self.spec["targets"][0]["driver_numbers"] = [1]
        with self.assertRaisesRegex(m.TargetHold, "roster_coverage_mismatch"):
            self.inputs()
        self.assertEqual(self.calls, [])

    def test_identity_metadata_negatives_before_any_request(self):
        cases = [
            (lambda: self.metadata["sessions"][0].update(meeting_key=999), "session_identity_mismatch"),
            (lambda: self.metadata["sessions"][0].update(year=2025), "session_identity_mismatch"),
            (lambda: self.metadata["sessions"][0].update(session_key=999), "session_metadata_missing_or_duplicate"),
            (lambda: self.metadata["sessions"][0].pop("date_end"), "invalid_utc_time"),
            (lambda: self.metadata["sessions"][0].update(location=""), "session_text_identity_missing"),
            (lambda: self.metadata["sessions"].append(self.metadata["sessions"][0]), "session_metadata_missing_or_duplicate"),
            (lambda: self.roster["drivers"][0].update(meeting_key=999), "roster_identity_mismatch"),
            (lambda: self.roster["drivers"].append(self.roster["drivers"][0]), "duplicate_roster_evidence"),
            (lambda: self.spec["targets"].append(self.spec["targets"][0]), "duplicate_target_session"),
            (lambda: self.spec["targets"][0]["driver_numbers"].append(1), "duplicate_target_driver"),
            (lambda: self.metadata["sessions"][0].update(is_cancelled=True), "cancelled_session"),
        ]
        original = copy.deepcopy((self.spec, self.metadata, self.roster))
        for action, reason in cases:
            with self.subTest(reason=reason):
                self.spec, self.metadata, self.roster = copy.deepcopy(original)
                action()
                with self.assertRaisesRegex(m.TargetHold, reason):
                    self.inputs()
        self.assertEqual(self.calls, [])

    def test_live_uncompleted_future_and_stale_metadata_rejected(self):
        for now in ["2026-10-30T18:30:00Z", "2026-10-30T23:30:00Z"]:
            with self.subTest(now=now), self.assertRaises(m.TargetHold):
                self.inputs(now=now)
        for key in ["metadata", "roster"]:
            original = getattr(self, key)["observed_at_utc"]
            for bad in ["2026-10-29T00:00:00Z", "2026-11-01T00:00:00Z"]:
                getattr(self, key)["observed_at_utc"] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(m.TargetHold):
                    self.inputs()
            getattr(self, key)["observed_at_utc"] = original
        self.assertEqual(self.calls, [])

    def test_scheduled_end_cannot_substitute_for_observed_completion(self):
        for value in [None, False, "true", 1]:
            with self.subTest(value=value):
                self.metadata["sessions"][0]["completion_confirmed"] = value
                with self.assertRaisesRegex(m.TargetHold, "session_completion_unverified"):
                    self.inputs()
        self.metadata["sessions"][0]["completion_confirmed"] = True
        self.metadata["sessions"][0]["completion_observed_at_utc"] = "2026-10-30T18:30:00Z"
        with self.assertRaisesRegex(m.TargetHold, "completion_chronology_invalid"):
            self.inputs()
        self.metadata["sessions"][0]["completion_observed_at_utc"] = "2026-10-31T00:45:00Z"
        with self.assertRaisesRegex(m.TargetHold, "session_incomplete_or_live_window"):
            self.inputs(now="2026-10-31T01:15:00Z")
        self.assertEqual(self.calls, [])

    def test_actual_end_plus_thirty_minute_boundary(self):
        self.metadata["observed_at_utc"] = self.roster["observed_at_utc"] = "2026-10-30T23:01:00Z"
        with self.assertRaisesRegex(m.TargetHold, "session_incomplete_or_live_window"):
            self.inputs(now="2026-10-30T23:30:00Z")
        self.assertEqual(len(self.inputs(now="2026-10-30T23:30:00.000001Z")["targets"]), 2)

    def test_metadata_pins_required_and_tampering_rejected(self):
        self.inputs()
        for pin in [None, "", "0" * 64]:
            with self.subTest(pin=pin), self.assertRaises(m.TargetHold):
                m.load_target_plan(self.root / "spec.json", self.root / "metadata.json", pin,
                                   self.root / "roster.json", m.target_sha(encode(self.roster)), now=NOW)
        self.assertEqual(self.calls, [])

    def test_wrong_session_meeting_driver_rows_stop_exactly_after_first_request(self):
        for field in ["session_key", "meeting_key", "driver_number"]:
            with self.subTest(field=field):
                self.output = self.root / "experimental" / field
                self.calls.clear()
                def alter(response, ep, params):
                    rows = self.rows(ep, params)
                    rows[-1][field] = 999
                    response.raw = encode(rows)
                    response.headers = {}
                self.handler = alter
                result = self.capture()
                self.assert_hold(result, "row_identity_mismatch")
                self.assertEqual(len(self.calls), 1)
                self.assertEqual([e["status"] for e in result["entries"]], ["hold"] + ["deferred"] * 5)
                self.assertTrue((self.output / "rejected_response_0.bin").exists())

    def test_missing_endpoint_never_produces_pass_or_later_requests(self):
        def missing(response, endpoint, _):
            if endpoint == "location":
                response.status_code = 404
        self.handler = missing
        result = self.capture()
        self.assert_hold(result, "provider_http_404")
        self.assertEqual([ep for ep, _, _ in self.calls], ["car_data", "car_data", "location"])
        self.assertEqual([e["status"] for e in result["entries"]], ["complete", "complete", "hold", "deferred", "deferred", "deferred"])

    def test_401_403_429_503_redirect_stop_no_retries(self):
        for code in [401, 403, 429, 503, 302]:
            with self.subTest(code=code):
                self.output = self.root / "experimental" / str(code)
                self.calls.clear()
                self.handler = lambda response, ep, p: setattr(response, "status_code", code)
                result = self.capture()
                self.assert_hold(result, f"provider_http_{code}")
                self.assertEqual(len(self.calls), 1)
                self.assertEqual(self.responses[-1].chunks_read, 0)
                self.assertTrue(self.responses[-1].closed)

    def test_altered_url_and_compressed_response_stop(self):
        for kind in ["url", "encoding"]:
            self.output = self.root / "experimental" / kind
            self.calls.clear()
            def alter(response, ep, p):
                if kind == "url":
                    response.url = "https://untrusted.invalid/data"
                else:
                    response.headers["Content-Encoding"] = "gzip"
            self.handler = alter
            result = self.capture()
            self.assert_hold(result, "response_url_mismatch" if kind == "url" else "encoded_response_rejected")
            self.assertEqual(len(self.calls), 1)

    def test_malformed_empty_duplicate_and_stale_rows_stop(self):
        for kind in ["invalid_json", "empty", "duplicate", "stale", "measurement", "deep"]:
            self.output = self.root / "experimental" / kind
            self.calls.clear()
            def alter(response, ep, p):
                rows = self.rows(ep, p)
                if kind == "duplicate": rows.append(rows[0])
                if kind == "stale": rows[0]["date"] = "2025-01-01T00:00:00Z"
                if kind == "measurement": rows[0].pop("speed")
                response.raw = b"?" if kind == "invalid_json" else b"[]" if kind == "empty" else b"["*2000+b"]"*2000 if kind == "deep" else encode(rows)
                response.headers = {}
            self.handler = alter
            result = self.capture()
            self.assert_hold(result)
            self.assertEqual(len(self.calls), 1)

    def test_transfer_content_length_and_stream_caps(self):
        cases = [(lambda r: None, "response_length_invalid_or_excessive"),
                 (lambda r: r.headers.clear(), "response_transfer_limit")]
        for i, (change, reason) in enumerate(cases):
            self.output = self.root / "experimental" / str(i)
            self.calls.clear()
            self.handler = lambda r, ep, p: change(r)
            result = self.capture(max_file_bytes=30)
            self.assert_hold(result, reason)
            self.assertEqual(len(self.calls), 1)
            self.assertLessEqual(self.responses[-1].chunks_read, 1)

    def test_truncated_content_length_rejected(self):
        self.handler = lambda r, ep, p: r.headers.update({"Content-Length": str(len(r.raw) + 1)})
        self.assert_hold(self.capture(), "response_length_mismatch")
        self.assertEqual(len(self.calls), 1)

    def test_total_byte_cap_stops_before_another_request(self):
        first_bytes = len(encode(self.rows("car_data", {"session_key": 11397, "driver_number": 1})))
        result = self.capture(max_total_bytes=first_bytes)
        self.assert_hold(result, "total_transfer_budget_exhausted")
        self.assertEqual(len(self.calls), 1)
        self.assertIs(result["entries"][1]["attempted"], False)

    def test_run_request_cap_retains_partial_proof_and_deferred_cells(self):
        result = self.capture(max_requests=2)
        self.assert_hold(result, "run_request_budget_exhausted")
        self.assertEqual(len(self.calls), 2)
        self.assertIs(result["entries"][2]["attempted"], False)

    def test_time_cap_cannot_authorize_fourth_request(self):
        result = self.capture(max_seconds=0.5)
        self.assert_hold(result, "run_time_budget_exhausted")
        self.assertEqual(len(self.calls), 3)

    def test_midstream_timeout_holds_and_closes(self):
        def slow(response, ep, params):
            self.clock.value += 20
        self.handler = slow
        result = self.capture(max_seconds=10)
        self.assert_hold(result, "run_time_budget_exhausted")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.responses[0].closed)

    def test_output_overwrite_refused_without_calls_or_changes(self):
        self.capture()
        before = {str(p): p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        self.calls.clear()
        self.assert_hold(self.capture(), "output_already_exists")
        self.assertEqual(self.calls, [])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.output.rglob("*") if p.is_file()})

    def test_unsafe_output_paths_and_symlinks_rejected(self):
        for suffix in ["latest/x", "history/x", "Engine_2026-06-07_STABLE/x", "../latest/x", "../elsewhere/x"]:
            self.output = self.root / "experimental" / suffix
            self.assert_hold(self.capture(), "unsafe_experimental_output")
        outside = self.root / "elsewhere"
        outside.mkdir()
        (self.root / "experimental").mkdir(exist_ok=True)
        (self.root / "experimental" / "link").symlink_to(outside, target_is_directory=True)
        self.output = self.root / "experimental" / "link" / "capture"
        self.assert_hold(self.capture(), "unsafe_experimental_output")
        self.assertEqual(self.calls, [])
        self.assertEqual(list(outside.iterdir()), [])

    def test_one_driver_partial_packet_rejected_by_independent_matrix(self):
        plan = self.inputs()
        self.capture(plan=plan)
        self.mutate_packet(lambda v: v.update(entries=v["entries"][:1]))
        self.assert_hold(m.verify_targeted_packet(self.output, plan, now=self.clock.utc()), "matrix_coverage_incomplete")

    def test_duplicate_cell_missing_location_and_wrong_roster_rejected(self):
        plan = self.inputs()
        self.capture(plan=plan)
        self.mutate_packet(lambda v: v["entries"].__setitem__(2, v["entries"][0]))
        self.assert_hold(m.verify_targeted_packet(self.output, plan, now=self.clock.utc()), "matrix_cell_identity_mismatch")

    def test_tampered_bytes_and_rebound_hash_still_reject_wrong_identity(self):
        plan = self.inputs()
        result = self.capture(plan=plan)
        entry = result["entries"][0]
        path = self.output / entry["file_path"]
        rows = json.loads(path.read_bytes())
        rows[0]["session_key"] = 999
        raw = encode(rows)
        path.write_bytes(raw)
        self.assert_hold(m.verify_targeted_packet(self.output, plan, now=self.clock.utc()), "packet_bytes_mismatch")
        self.mutate_packet(lambda v: v["entries"][0].update(sha256=m.target_sha(raw), size_bytes=len(raw)))
        self.assert_hold(m.verify_targeted_packet(self.output, plan, now=self.clock.utc()), "row_identity_mismatch")

    def test_packet_request_identity_timing_and_trust_ceiling_tampering(self):
        plan = self.inputs()
        self.capture(plan=plan)
        original = (self.output / "targeted_manifest.json").read_bytes()
        changes = [lambda v: v["entries"][0].update(params={"session_key": 999, "driver_number": 1}),
                   lambda v: v["entries"][0].update(observed_at_utc="2026-10-29T00:00:00Z"),
                   lambda v: v.update(generated_at_utc="2026-11-01T00:00:00Z"),
                   lambda v: v.update(prospective_forecast_eligibility_established=True),
                   lambda v: v.update(provider_sampling_completeness_established=True),
                   lambda v: v["entries"][0].update(file_path="../../outside")]
        for i, change in enumerate(changes):
            with self.subTest(case=i):
                (self.output / "targeted_manifest.json").write_bytes(original)
                self.mutate_packet(change)
                self.assert_hold(m.verify_targeted_packet(self.output, plan, now=self.clock.utc()))

    def test_verified_cache_reuse_no_calls_no_timestamp_rewrite(self):
        plan = self.inputs()
        first = self.capture(plan=plan)
        cache = self.output
        manifest_raw = (cache / "targeted_manifest.json").read_bytes()
        self.output = self.root / "experimental" / "reuse"
        self.calls.clear()
        result = self.capture(plan=plan, cache_dir=cache, cache_manifest_sha256=m.target_sha(manifest_raw))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(self.calls, [])
        self.assertEqual(result["request_budget"]["provider_requests_performed"], 0)
        for a, b in zip(first["entries"], result["entries"]):
            self.assertEqual(a["observed_at_utc"], b["observed_at_utc"])
            self.assertEqual(a["sha256"], b["sha256"])
        self.assertEqual((cache / "targeted_manifest.json").read_bytes(), manifest_raw)
        self.assertEqual(m.verify_targeted_packet(self.output, plan, now=self.clock.utc())["status"], "PASS")

    def test_corrupt_empty_missing_or_unpinned_cache_no_fallback_requests(self):
        plan = self.inputs()
        result = self.capture(plan=plan)
        cache = self.output
        pin = m.target_sha((cache / "targeted_manifest.json").read_bytes())
        path = cache / result["entries"][0]["file_path"]
        original = path.read_bytes()
        for i, (raw, use_pin) in enumerate([(b"corrupt", pin), (b"", pin), (None, pin), (original, None)]):
            with self.subTest(case=i):
                self.output = self.root / "experimental" / f"cache_bad_{i}"
                if raw is None: path.unlink()
                else: path.write_bytes(raw)
                self.calls.clear()
                self.assert_hold(self.capture(plan=plan, cache_dir=cache, cache_manifest_sha256=use_pin))
                self.assertEqual(self.calls, [])
                self.assertFalse(self.output.exists())

    def test_changed_target_cache_rejected_without_provider_calls(self):
        plan = self.inputs()
        self.capture(plan=plan)
        cache = self.output
        pin = m.target_sha((cache / "targeted_manifest.json").read_bytes())
        self.spec["targets"] = self.spec["targets"][:1]
        self.calls.clear()
        self.output = self.root / "experimental" / "different_target"
        self.assert_hold(self.capture(cache_dir=cache, cache_manifest_sha256=pin), "cache_coverage_or_provenance_invalid")
        self.assertEqual(self.calls, [])

    def test_immutable_retained_mexico_identity_reference_only(self):
        for sk, blob in [(11397, "4fa9ca39d8432553b71b90f7de86c5dfc6508ec2"),
                         (11398, "7305fc5c2b73a009dcda22877ffc18cabc433442")]:
            raw = subprocess.check_output(["git", "cat-file", "blob", blob], cwd=ROOT)
            self.assertEqual(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(), blob)
            reference = json.loads(raw)
            self.assertEqual(reference["event_id"], "2026_1298_mexico_mexico_city_mexico_city")
            session = reference["forecast_bundle_ledger_snapshot"]["session"]
            self.assertEqual(session["session_key"], sk)
            self.assertEqual(session["meeting_key"], 1298)
            self.assertEqual(session["date_start"], next(s for s in self.metadata["sessions"] if s["session_key"] == sk)["date_start"].replace("Z", "+00:00"))
            self.assertFalse(reference["promotion_allowed"])
            self.assertNotIn("car_data", reference["readiness_aggregation"]["critical_endpoints"])

    def test_cli_opt_in_checkpoint_bypasses_legacy_sweep(self):
        self.inputs()
        from scripts.openf1 import openf1_high_frequency_extract_checkpoint as checkpoint
        argv = ["checkpoint", "--mode", "prerace", "--output-dir", str(self.output),
                "--target-spec", str(self.root / "spec.json"),
                "--target-metadata", str(self.root / "metadata.json"),
                "--target-metadata-sha256", m.target_sha(encode(self.metadata)),
                "--target-roster", str(self.root / "roster.json"),
                "--target-roster-sha256", m.target_sha(encode(self.roster))]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(checkpoint, "run_target_cli", return_value=1) as target, mock.patch.object(checkpoint, "discover_sessions", side_effect=AssertionError("sweep forbidden")):
            self.assertEqual(checkpoint.main(), 1)
            target.assert_called_once()
        # The actual CLI boundary also holds on invalid input before any client.
        args = target.call_args.args[0]
        args.target_metadata_sha256 = "0" * 64
        with mock.patch.object(m.requests, "get", side_effect=AssertionError("HTTP forbidden")), mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(m.run_target_cli(args), 1)

    def test_strict_validator_cli_nonzero_on_intact_but_partial_packet(self):
        self.capture()
        self.mutate_packet(lambda v: v.update(entries=v["entries"][:1]))
        spec = importlib.util.spec_from_file_location("strict_output_validator", ROOT / "tests/validate_openf1_high_frequency_output.py")
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        argv = ["validator", "--mode", "prerace", "--output-dir", str(self.output),
                "--target-spec", str(self.root / "spec.json"),
                "--target-metadata", str(self.root / "metadata.json"),
                "--target-metadata-sha256", m.target_sha(encode(self.metadata)),
                "--target-roster", str(self.root / "roster.json"),
                "--target-roster-sha256", m.target_sha(encode(self.roster))]
        with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", new=io.StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                validator.main()
            self.assertEqual(raised.exception.code, 1)
            self.assert_hold(json.loads(output.getvalue()), "matrix_coverage_incomplete")


if __name__ == "__main__":
    unittest.main()
