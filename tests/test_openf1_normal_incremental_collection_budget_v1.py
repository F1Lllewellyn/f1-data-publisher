import datetime as dt
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/openf1/publish_openf1_lightweight_source_closure.py"
WORKFLOW = ROOT / ".github/workflows/f1-openf1-lightweight-source-closure.yml"
GUARD_SCRIPT = ROOT / "scripts/ops/f1_source_closure_publish_guard_v1.py"

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("real network is forbidden in incremental tests")

    requests_stub.get = unexpected_network
    sys.modules["requests"] = requests_stub

spec = importlib.util.spec_from_file_location("openf1_normal_incremental", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

guard_spec = importlib.util.spec_from_file_location(
    "openf1_incremental_publication_guard", GUARD_SCRIPT
)
guard = importlib.util.module_from_spec(guard_spec)
sys.modules[guard_spec.name] = guard
guard_spec.loader.exec_module(guard)


class Response:
    def __init__(self, status_code=200, data=None, *, text="", json_error=None):
        self.status_code = status_code
        self.data = [] if data is None else data
        self.text = text
        self.json_error = json_error

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.data


def session(
    session_key=11396,
    *,
    meeting_key=1297,
    name="Race",
    circuit="Austin",
    year=2026,
):
    return {
        "session_key": session_key,
        "meeting_key": meeting_key,
        "year": year,
        "country_name": "United States",
        "location": circuit,
        "circuit_short_name": circuit,
        "session_name": name,
        "session_type": name,
        "date_start": f"{year}-10-25T19:00:00Z",
        "date_end": f"{year}-10-25T21:00:00Z",
    }


def endpoint_row(endpoint, params, sessions):
    session_key = int(params.get("session_key", sessions[-1]["session_key"]))
    selected = next(
        (row for row in sessions if int(row["session_key"]) == session_key),
        sessions[-1],
    )
    meeting_key = int(params.get("meeting_key", selected["meeting_key"]))
    row = {
        "session_key": session_key,
        "meeting_key": meeting_key,
        "date": "2026-10-25T20:00:00Z",
    }
    if endpoint in {
        "intervals", "position", "stints", "pit", "starting_grid", "drivers",
        "team_radio",
    }:
        row["driver_number"] = int(params.get("driver_number", 44))
    return row


class Router:
    def __init__(self, sessions, handler=None):
        self.sessions = sessions
        self.handler = handler
        self.calls = []

    def __call__(self, url, *, params, timeout):
        endpoint = url.rsplit("/", 1)[-1]
        clean = dict(params)
        self.calls.append((endpoint, clean, timeout))
        if self.handler is not None:
            result = self.handler(endpoint, clean)
            if result is not None:
                if isinstance(result, BaseException):
                    raise result
                return result
        if endpoint == "sessions":
            return Response(data=self.sessions)
        return Response(data=[endpoint_row(endpoint, clean, self.sessions)])


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


class Harness:
    def __init__(self, testcase):
        self.temp = tempfile.TemporaryDirectory()
        testcase.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run(
        self,
        sessions,
        *,
        now,
        handler=None,
        season=2026,
        completed_only=True,
        max_requests=None,
        max_seconds=None,
    ):
        router = Router(sessions, handler)
        clock = FakeClock()
        argv = [
            "collector",
            "--season", str(season),
            "--completed-only", str(completed_only).lower(),
            "--output-root", str(self.root),
        ]
        patches = [
            mock.patch.object(m.requests, "get", side_effect=router),
            mock.patch.object(m, "utc_now", return_value=now),
            mock.patch.object(m.time, "monotonic", side_effect=clock.monotonic),
            mock.patch.object(m.time, "sleep", side_effect=clock.sleep),
            mock.patch.object(sys, "argv", argv),
        ]
        if max_requests is not None:
            patches.append(mock.patch.object(m, "NORMAL_MAX_RUN_REQUESTS", max_requests))
        if max_seconds is not None:
            patches.append(mock.patch.object(
                m, "NORMAL_MAX_COLLECTION_SECONDS", max_seconds
            ))
        for patcher in patches:
            patcher.start()
        try:
            rc = m.main()
        finally:
            for patcher in reversed(patches):
                patcher.stop()
        latest = self.root / "latest/openf1_lightweight_source_closure"
        manifest = json.loads((latest / "latest_manifest.json").read_text())
        diagnostics = m._read_csv_frame(latest / "zero_lane_diagnostics.csv")
        request_log = m._read_csv_frame(latest / "request_log.csv")
        return {
            "rc": rc,
            "router": router,
            "clock": clock,
            "latest": latest,
            "manifest": manifest,
            "normal": manifest["normal_collection"],
            "diagnostics": diagnostics,
            "request_log": request_log,
        }


class OpenF1NormalIncrementalBudgetTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.harness = Harness(self)
        self.first_now = dt.datetime(2026, 10, 26, 12, tzinfo=dt.UTC)
        self.second_now = dt.datetime(2026, 10, 26, 13, tzinfo=dt.UTC)

    def test_sliding_window_accounts_for_burst_and_minute_limit(self):
        clock = FakeClock()
        budget = m.NormalRequestBudget(
            requests_per_window=30,
            window_seconds=60,
            max_requests=31,
            max_elapsed_seconds=61,
            clock=clock.monotonic,
            sleeper=clock.sleep,
        )
        observed = []
        for _ in range(31):
            budget.acquire()
            observed.append(clock.value)
        self.assertEqual(observed[:30], [0.0] * 30)
        self.assertEqual(observed[30], 60.0)
        self.assertEqual(clock.sleeps, [60.0])
        self.assertEqual(budget.total_requests, 31)
        self.assertEqual(budget.evidence()["requests_per_minute"], 30)

    def test_complete_hardened_session_reuses_exact_evidence(self):
        first = self.harness.run([session()], now=self.first_now)
        self.assertEqual(first["rc"], 0)
        self.assertEqual(len(first["router"].calls), 10)
        first_observed = set(first["diagnostics"]["first_observed_utc"])

        second = self.harness.run([session()], now=self.second_now)
        self.assertEqual(second["rc"], 0)
        self.assertEqual([call[0] for call in second["router"].calls], ["sessions"])
        self.assertEqual(second["normal"]["reused_session_count"], 1)
        self.assertEqual(second["normal"]["fresh_session_count"], 0)
        self.assertEqual(second["normal"]["provider_requests_avoided"], 9)
        self.assertEqual(set(second["diagnostics"]["first_observed_utc"]), first_observed)
        self.assertEqual(set(second["diagnostics"]["cache_source"]), {"hardened_latest"})

    def test_new_session_only_is_fetched_within_budget(self):
        self.harness.run([session()], now=self.first_now)
        new = session(11397, meeting_key=1298, circuit="Mexico City")
        result = self.harness.run(
            [session(), new], now=self.second_now, max_requests=12
        )
        self.assertEqual(result["rc"], 0)
        self.assertEqual(len(result["router"].calls), 10)
        self.assertEqual(result["normal"]["reused_session_count"], 1)
        self.assertEqual(result["normal"]["fresh_session_count"], 1)
        self.assertEqual(
            set(result["diagnostics"].query("session_key == 11396")["cache_source"]),
            {"hardened_latest"},
        )
        self.assertEqual(
            set(result["diagnostics"].query("session_key == 11397")["cache_source"]),
            {"fresh_provider"},
        )

    def test_corrupted_lane_cache_is_rejected_and_never_reused(self):
        first = self.harness.run([session()], now=self.first_now)
        weather = first["latest"] / "data/openf1_weather.csv"
        weather.write_bytes(weather.read_bytes() + b"\ncorrupt")
        result = self.harness.run([session()], now=self.second_now)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(len(result["router"].calls), 10)
        self.assertEqual(result["normal"]["reused_session_count"], 0)
        self.assertIn(
            "cache_source_hash_mismatch:weather",
            result["normal"]["cache_evidence"]["hardened_cache_rejection_reason"],
        )

    def test_partial_diagnostics_cache_is_rejected(self):
        first = self.harness.run([session()], now=self.first_now)
        path = first["latest"] / "zero_lane_diagnostics.csv"
        rows = path.read_text().splitlines()
        path.write_text("\n".join(rows[:-1]) + "\n")
        result = self.harness.run([session()], now=self.second_now)
        self.assertEqual(result["normal"]["reused_session_count"], 0)
        self.assertEqual(len(result["router"].calls), 10)
        self.assertIn(
            "hardened_cache_hash_mismatch:zero_lane_diagnostics_sha256",
            result["normal"]["cache_evidence"]["hardened_cache_rejection_reason"],
        )

    def test_changed_session_identity_is_fetched_not_retroactively_rebound(self):
        self.harness.run([session()], now=self.first_now)
        changed = session(circuit="Austin Revised")
        result = self.harness.run([changed], now=self.second_now)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(result["normal"]["verified_cache_candidate_sessions"], 1)
        self.assertEqual(result["normal"]["reused_session_count"], 0)
        self.assertEqual(len(result["router"].calls), 10)

    def test_run_budget_exhaustion_sends_no_request_beyond_cap(self):
        result = self.harness.run(
            [session()], now=self.first_now, max_requests=1
        )
        self.assertEqual(result["rc"], 1)
        self.assertEqual([call[0] for call in result["router"].calls], ["sessions"])
        self.assertEqual(
            result["normal"]["request_budget"]["deferred_reason"],
            "run_request_budget_exhausted",
        )
        self.assertTrue(any(
            str(value).startswith("deferred_run_request_budget_exhausted")
            for value in result["request_log"]["status"]
        ))
        self.assertFalse(result["manifest"]["publication_eligible"])

    def test_discovery_access_rate_transport_and_schema_fail_distinctly(self):
        cases = {
            "http_401": Response(401, text="authentication required"),
            "http_403": Response(403, text="forbidden"),
            "http_429": Response(429, text="rate limited"),
            "http_503": Response(503, text="unavailable"),
            "invalid_json": Response(json_error=ValueError("bad json")),
            "invalid_response_schema": Response(data={"error": "not a list"}),
            "exception": TimeoutError("offline fixture timeout"),
        }
        for label, response in cases.items():
            with self.subTest(label=label):
                harness = Harness(self)
                result = harness.run(
                    [],
                    now=self.first_now,
                    handler=lambda endpoint, _params, value=response: (
                        value if endpoint == "sessions" else None
                    ),
                )
                self.assertEqual(result["rc"], 1)
                self.assertEqual(len(result["router"].calls), 1)
                self.assertEqual(
                    result["manifest"]["session_discovery_status"], label
                )
                self.assertNotEqual(
                    result["manifest"]["session_discovery_availability"],
                    "available",
                )

    def test_legitimate_200_empty_is_not_transport_success_fabrication(self):
        result = self.harness.run([], now=self.first_now)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(len(result["router"].calls), 1)
        self.assertEqual(result["manifest"]["session_discovery_status"], "zero_rows")
        self.assertEqual(result["manifest"]["source_quality_status"], "complete_empty")
        self.assertEqual(result["manifest"]["session_discovery_availability"], "available")

    def test_required_zero_and_transport_fail_but_semantic_404_is_warning(self):
        semantic = self.harness.run(
            [session()],
            now=self.first_now,
            handler=lambda endpoint, _params: (
                Response(404, text="not available")
                if endpoint in {"intervals", "team_radio"} else None
            ),
        )
        self.assertEqual(semantic["rc"], 0)
        self.assertEqual(
            semantic["diagnostics"].query("lane == 'intervals'").iloc[0]["status"],
            "pass_with_warnings",
        )

        zero_harness = Harness(self)
        zero = zero_harness.run(
            [session()],
            now=self.first_now,
            handler=lambda endpoint, _params: (
                Response(data=[]) if endpoint == "weather" else None
            ),
        )
        self.assertEqual(zero["rc"], 1)
        self.assertEqual(
            zero["diagnostics"].query("lane == 'weather'").iloc[0]["reason"],
            "required_session_zero_rows",
        )

        transport_harness = Harness(self)
        transport = transport_harness.run(
            [session()],
            now=self.first_now,
            handler=lambda endpoint, _params: (
                TimeoutError("offline fixture") if endpoint == "weather" else None
            ),
        )
        self.assertEqual(transport["rc"], 1)
        self.assertEqual(len(transport["router"].calls), 2)
        self.assertEqual(
            transport["normal"]["request_budget"]["deferred_reason"],
            "transport_exception",
        )

    def test_verified_legacy_snapshot_refuses_aggregate_and_replays_sessions(self):
        cache, evidence = m._load_verified_legacy_cache(
            ROOT, season=2026, completed_only=True
        )
        self.assertFalse(evidence["aggregate_pass_accepted"])
        self.assertEqual(evidence["verified_sessions"], 40)
        self.assertEqual(evidence["rejected_sessions"], 66)
        self.assertIn("11392", cache)
        self.assertNotIn("11396", cache)
        saved = pd.read_csv(
            ROOT / m.NORMAL_LEGACY_HISTORY_REL / "request_log.csv"
        )
        self.assertEqual(len(saved), 2612)
        self.assertEqual(int((saved["status"] == "http_429").sum()), 1869)

    def test_corrupted_legacy_snapshot_identity_is_rejected(self):
        destination = self.harness.root / m.NORMAL_LEGACY_HISTORY_REL
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / m.NORMAL_LEGACY_HISTORY_REL, destination)
        request_log = destination / "request_log.csv"
        request_log.write_bytes(request_log.read_bytes() + b"\ncorrupt")
        cache, evidence = m._load_verified_legacy_cache(
            self.harness.root, season=2026, completed_only=True
        )
        self.assertEqual(cache, {})
        self.assertEqual(evidence["reason"], "legacy_snapshot_identity_mismatch")

    def test_provider_429_fallback_is_bounded_and_can_recover(self):
        def handler(endpoint, params):
            if endpoint == "position" and "session_key" in params:
                return Response(429, text="rate limited")
            return None

        result = self.harness.run(
            [session()], now=self.first_now, handler=handler
        )
        self.assertEqual(result["rc"], 0)
        row = result["diagnostics"].query("lane == 'position'").iloc[0]
        self.assertEqual(row["request_statuses"], "http_429,pass")
        self.assertEqual(row["reason"], "endpoint_fallback_recovered_complete")
        self.assertIn(
            "provider_rate_limited_http_429",
            result["normal"]["request_budget"]["restriction_events"],
        )

    def test_fail_closed_outputs_never_raise_trust_ceilings(self):
        result = self.harness.run(
            [session()], now=self.first_now, max_requests=1
        )
        normal = result["normal"]
        for field in (
            "prospective_forecast_eligibility_established",
            "source_readiness_promoted",
            "dr002_activated",
            "stable_engine_modified",
        ):
            self.assertIs(normal[field], False)
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Upload legacy source closure artifact", workflow)
        self.assertIn("if: ${{ success()", workflow)

    def test_positive_incremental_output_preserves_publication_contract(self):
        result = self.harness.run([session()], now=self.first_now)
        candidate = guard.validate_candidate(
            self.harness.root,
            expected_season=2026,
            expected_completed_only=True,
            now=self.first_now + dt.timedelta(minutes=1),
        )
        self.assertEqual(result["rc"], 0)
        self.assertEqual(candidate.manifest["normal_collection"]["schema_version"],
                         m.NORMAL_CACHE_SCHEMA_VERSION)
        self.assertEqual(set(candidate.sessions), {"11396"})

    def test_manual_shadow_branch_precedes_all_normal_collection_logic(self):
        source = SCRIPT.read_text(encoding="utf-8")
        shadow = source.index("if args.provenance_shadow_session_key:")
        normal = source.index("hardened_cache, hardened_cache_evidence")
        self.assertLess(shadow, normal)
        self.assertEqual(m.SHADOW_ENDPOINTS, ("weather", "drivers", "starting_grid"))


if __name__ == "__main__":
    unittest.main()
