import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock
import zipfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/openf1/publish_openf1_lightweight_source_closure.py"
ORCHESTRATOR = (
    ROOT / "scripts/forecast_bundles/orchestrate_forecast_gate_pipeline_v1.py"
)

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("real network is forbidden in request-quality tests")

    requests_stub.get = unexpected_network
    sys.modules["requests"] = requests_stub

spec = importlib.util.spec_from_file_location("source_closure_request_quality", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

orchestrator_spec = importlib.util.spec_from_file_location(
    "source_closure_caller_quality", ORCHESTRATOR
)
orchestrator = importlib.util.module_from_spec(orchestrator_spec)
orchestrator_spec.loader.exec_module(orchestrator)


FIXED_NOW = m.dt.datetime(2026, 10, 26, 12, 0, 0, tzinfo=m.dt.UTC)


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


def session(session_key=11396, *, name="Race", meeting_key=1297):
    return {
        "session_key": session_key,
        "meeting_key": meeting_key,
        "year": 2026,
        "country_name": "United States",
        "location": "Austin",
        "circuit_short_name": "Austin",
        "session_name": name,
        "session_type": name,
        "date_start": "2026-10-25T19:00:00Z",
        "date_end": "2026-10-25T21:00:00Z",
    }


def endpoint_row(endpoint, params):
    session_key = int(params.get("session_key", 11396))
    meeting_key = int(params.get("meeting_key", 1297))
    row = {
        "session_key": session_key,
        "meeting_key": meeting_key,
        "date": "2026-10-25T20:00:00Z",
    }
    if endpoint in {"intervals", "position", "stints", "pit", "starting_grid", "drivers", "team_radio"}:
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
        return Response(data=[endpoint_row(endpoint, clean)])


class SourceClosureRequestQualityTests(unittest.TestCase):
    maxDiff = None

    def run_collection(
        self,
        sessions,
        handler=None,
        *,
        seed_previous=None,
        season=2026,
        completed_only=True,
        now=FIXED_NOW,
        previous_season=None,
        previous_completed_only=None,
    ):
        router = Router(sessions, handler)
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            latest = output / "latest/openf1_lightweight_source_closure"
            if seed_previous is not None:
                (latest / "data").mkdir(parents=True)
                seeded_season = previous_season
                if seeded_season is None:
                    seeded_season = (
                        seed_previous[0].get("year", season)
                        if seed_previous else season
                    )
                seeded_completed_only = previous_completed_only
                if seeded_completed_only is None:
                    seeded_completed_only = completed_only
                (latest / "latest_manifest.json").write_text(json.dumps({
                    "generated_utc": "2026-10-25T18:53:47Z",
                    "season": seeded_season,
                    "completed_only": seeded_completed_only,
                    "target_session_count": len(seed_previous),
                }))
                pd.DataFrame(seed_previous).to_csv(
                    latest / "data/target_sessions.csv", index=False
                )
            argv = [
                "collector", "--season", str(season), "--completed-only",
                str(completed_only).lower(),
                "--output-root", td,
            ]
            with mock.patch.object(m.requests, "get", side_effect=router), \
                    mock.patch.object(m.time, "sleep"), \
                    mock.patch.object(m, "utc_now", return_value=now), \
                    mock.patch.object(sys, "argv", argv):
                rc = m.main()
            history = (
                output / "history/openf1_lightweight_source_closure"
                / now.strftime("%Y%m%d_%H%M%S")
            )
            manifest = json.loads((latest / "latest_manifest.json").read_text())
            request_log = pd.read_csv(latest / "request_log.csv").fillna("")

            def read_optional_csv(path):
                try:
                    return pd.read_csv(path).fillna("")
                except pd.errors.EmptyDataError:
                    return pd.DataFrame()

            diagnostics = read_optional_csv(
                latest / "zero_lane_diagnostics.csv"
            )
            readiness = pd.read_csv(
                latest / "source_readiness_summary.csv"
            ).fillna("")
            report = (latest / "source_closure_report.md").read_text()
            zip_path = latest / "openf1_lightweight_source_closure.zip"
            zip_digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            declared_digest = (
                latest / "openf1_lightweight_source_closure.zip.sha256.txt"
            ).read_text().split()[0]
            with zipfile.ZipFile(zip_path) as archive:
                zip_members = sorted(archive.namelist())
            return {
                "rc": rc,
                "calls": list(router.calls),
                "manifest": manifest,
                "request_log": request_log.to_dict("records"),
                "diagnostics": diagnostics.to_dict("records"),
                "readiness": readiness.to_dict("records"),
                "report": report,
                "zip_digest": zip_digest,
                "declared_digest": declared_digest,
                "zip_members": zip_members,
                "history_exists": history.is_dir(),
            }

    def lane_row(self, result, lane, session_key=11396):
        return next(
            row for row in result["diagnostics"]
            if row["lane"] == lane and int(row["session_key"]) == session_key
        )

    def readiness_row(self, result, lane):
        return next(row for row in result["readiness"] if row["lane"] == lane)

    def test_sessions_http_401_and_429_hold_after_one_request(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                result = self.run_collection(
                    [],
                    lambda endpoint, _params: Response(
                        status, text="provider unavailable"
                    ) if endpoint == "sessions" else None,
                )
                self.assertEqual(result["rc"], 1)
                self.assertEqual(len(result["calls"]), 1)
                self.assertFalse(result["manifest"]["publication_eligible"])
                self.assertEqual(result["manifest"]["target_session_count"], 0)
                self.assertEqual(
                    result["manifest"]["session_discovery_status"],
                    f"http_{status}",
                )
                self.assertIn("Publication eligible: false", result["report"])

    def test_sessions_5xx_timeout_invalid_json_and_schema_hold(self):
        cases = {
            "http_503": Response(503, text="unavailable"),
            "timeout": TimeoutError("offline timeout fixture"),
            "invalid_json": Response(json_error=ValueError("bad json")),
            "object": Response(data={"error": "not a sessions list"}),
            "scalar_row": Response(data=[1]),
        }
        for label, response in cases.items():
            with self.subTest(label=label):
                result = self.run_collection(
                    [],
                    lambda endpoint, _params, value=response: (
                        value if endpoint == "sessions" else None
                    ),
                )
                self.assertEqual(result["rc"], 1)
                self.assertFalse(result["manifest"]["publication_eligible"])
                self.assertEqual(len(result["calls"]), 1)

    def test_malformed_sessions_identity_schema_holds(self):
        malformed = session()
        malformed.pop("session_type")
        result = self.run_collection([malformed])
        self.assertEqual(result["rc"], 1)
        self.assertEqual(
            result["manifest"]["session_discovery_status"],
            "invalid_sessions_schema",
        )

    def test_discovery_identity_and_chronology_fail_closed(self):
        wrong_year = session()
        wrong_year["year"] = 2025
        fractional_session = session(11396.5)
        fractional_meeting = session(meeting_key=1297.5)
        fractional_year = session()
        fractional_year["year"] = 2026.5
        zero_session = session(0)
        malformed_session = session("11396x")
        malformed_meeting = session(meeting_key=" 1297")
        invalid_start = session()
        invalid_start["date_start"] = "not-a-date"
        invalid_end = session()
        invalid_end["date_end"] = "not-a-date"
        reversed_clock = session()
        reversed_clock["date_start"] = "2026-10-25T22:00:00Z"
        reversed_clock["date_end"] = "2026-10-25T21:00:00Z"
        duplicate = [session(11396), session(11396)]
        cases = {
            "wrong_year": ([wrong_year], "wrong_season:"),
            "duplicate": (duplicate, "duplicate_session_key:"),
            "fractional_session": (
                [fractional_session], "invalid_session_key:"
            ),
            "fractional_meeting": (
                [fractional_meeting], "invalid_meeting_key:"
            ),
            "fractional_year": ([fractional_year], "wrong_season:"),
            "zero_session": ([zero_session], "invalid_session_key:"),
            "malformed_session": (
                [malformed_session], "invalid_session_key:"
            ),
            "malformed_meeting": (
                [malformed_meeting], "invalid_meeting_key:"
            ),
            "invalid_start": ([invalid_start], "invalid_session_start:"),
            "invalid_end": ([invalid_end], "invalid_session_end:"),
            "reversed_clock": (
                [reversed_clock], "invalid_session_chronology:"
            ),
        }
        for label, (payload, reason) in cases.items():
            with self.subTest(label=label):
                result = self.run_collection(payload)
                self.assertEqual(result["rc"], 1)
                self.assertEqual(len(result["calls"]), 1)
                self.assertFalse(result["manifest"]["publication_eligible"])
                self.assertEqual(
                    result["manifest"]["session_discovery_status"],
                    "invalid_sessions_schema",
                )
                self.assertTrue(
                    str(result["request_log"][0]["error"]).startswith(reason)
                )

    def test_future_or_unknown_end_sessions_remain_unselected_not_invalid(self):
        future = session()
        future["date_start"] = "2026-12-01T10:00:00Z"
        future["date_end"] = "2026-12-01T12:00:00Z"
        unknown_end = session(11397)
        unknown_end["date_start"] = "2026-12-02T10:00:00Z"
        unknown_end.pop("date_end")
        result = self.run_collection([future, unknown_end])
        self.assertEqual(result["rc"], 0)
        self.assertEqual(len(result["calls"]), 1)
        self.assertEqual(result["manifest"]["target_session_count"], 0)
        self.assertEqual(result["manifest"]["session_discovery_status"], "pass")
        self.assertEqual(result["manifest"]["source_quality_status"], "complete_empty")

    def test_legitimate_http_200_empty_completed_set_is_explicit(self):
        result = self.run_collection([])
        self.assertEqual(result["rc"], 0)
        self.assertEqual(len(result["calls"]), 1)
        self.assertTrue(result["manifest"]["publication_eligible"])
        self.assertEqual(result["manifest"]["source_quality_status"], "complete_empty")
        self.assertEqual(result["manifest"]["session_discovery_status"], "zero_rows")

    def test_empty_completed_set_cannot_replace_known_coverage(self):
        previous = [session(10000), session(10001)]
        result = self.run_collection([], seed_previous=previous)
        self.assertEqual(result["rc"], 1)
        self.assertFalse(result["manifest"]["publication_eligible"])
        self.assertIn(
            "completed_session_count_regression:2->0",
            result["manifest"]["source_quality_reasons"],
        )

    def test_clean_complete_collection_is_publishable_and_integral(self):
        result = self.run_collection([session()])
        self.assertEqual(result["rc"], 0)
        self.assertEqual(len(result["calls"]), 10)
        self.assertTrue(result["manifest"]["publication_eligible"])
        self.assertEqual(result["manifest"]["source_quality_status"], "complete")
        self.assertEqual(result["manifest"]["pass_count"], 9)
        self.assertEqual(result["zip_digest"], result["declared_digest"])
        self.assertIn("latest_manifest.json", result["zip_members"])
        self.assertTrue(result["history_exists"])

    def test_session_rows_require_rowwise_exact_non_null_identity(self):
        def mixed_or_wrong(endpoint, _params):
            if endpoint == "weather":
                return Response(data=[
                    {
                        "session_key": "11396",
                        "meeting_key": "1297",
                        "date": "2026-10-25T20:00:00Z",
                    },
                    {
                        "session_key": None,
                        "meeting_key": None,
                        "date": "2026-10-25T20:01:00Z",
                    },
                ])
            return None

        mixed = self.run_collection([session()], mixed_or_wrong)
        self.assertEqual(mixed["rc"], 1)
        row = self.lane_row(mixed, "weather")
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["reason"], "session_identity_unproven")
        self.assertEqual(row["rows"], 2)

        identity_cases = {
            "wrong_session": {"session_key": "99999", "meeting_key": "1297"},
            "wrong_meeting": {"session_key": "11396", "meeting_key": "9999"},
            "missing_session_column": {"meeting_key": "1297"},
            "blank_meeting": {"session_key": "11396", "meeting_key": ""},
        }
        for label, identity in identity_cases.items():
            def handler(endpoint, _params, values=identity):
                if endpoint == "weather":
                    return Response(data=[{
                        **values,
                        "date": "2026-10-25T20:00:00Z",
                    }])
                return None

            with self.subTest(label=label):
                result = self.run_collection([session()], handler)
                self.assertEqual(result["rc"], 1)
                self.assertEqual(
                    self.lane_row(result, "weather")["reason"],
                    "session_identity_unproven",
                )

    def test_exact_canonical_string_identity_is_accepted(self):
        def handler(endpoint, _params):
            if endpoint == "weather":
                return Response(data=[{
                    "session_key": "11396",
                    "meeting_key": "1297",
                    "date": "2026-10-25T20:00:00Z",
                }])
            return None

        result = self.run_collection([session()], handler)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(self.lane_row(result, "weather")["status"], "pass")

    def test_new_season_ignores_prior_season_count_but_same_season_regresses(self):
        previous_2026 = [session(10000 + index) for index in range(106)]
        first_2027 = session(12001)
        first_2027.update({
            "year": 2027,
            "country_name": "Australia",
            "location": "Melbourne",
            "circuit_short_name": "Melbourne",
            "date_start": "2027-03-07T04:00:00Z",
            "date_end": "2027-03-07T06:00:00Z",
        })
        next_season = self.run_collection(
            [first_2027],
            seed_previous=previous_2026,
            season=2027,
            now=m.dt.datetime(2027, 3, 8, 12, 0, 0, tzinfo=m.dt.UTC),
            previous_season=2026,
        )
        self.assertEqual(next_season["rc"], 0)
        self.assertTrue(next_season["manifest"]["publication_eligible"])
        self.assertFalse(
            next_season["manifest"]["previous_coverage_compatible"]
        )
        self.assertFalse(any(
            "coverage_regression" in reason or "count_regression" in reason
            for reason in next_season["manifest"]["source_quality_reasons"]
        ))

        same_season = self.run_collection(
            previous_2026[:105],
            seed_previous=previous_2026,
            season=2026,
            previous_season=2026,
        )
        self.assertEqual(same_season["rc"], 1)
        self.assertFalse(same_season["manifest"]["publication_eligible"])
        self.assertTrue(
            same_season["manifest"]["previous_coverage_compatible"]
        )
        self.assertIn(
            "completed_session_count_regression:106->105",
            same_season["manifest"]["source_quality_reasons"],
        )

        incompatible_policy = self.run_collection(
            [session(13001)],
            seed_previous=previous_2026,
            season=2026,
            completed_only=False,
            previous_season=2026,
            previous_completed_only=True,
        )
        self.assertEqual(incompatible_policy["rc"], 0)
        self.assertFalse(
            incompatible_policy["manifest"]["previous_coverage_compatible"]
        )

    def test_required_weather_failure_holds_despite_other_session_rows(self):
        sessions = [session(11395), session(11396)]

        def handler(endpoint, params):
            if endpoint == "weather" and int(params.get("session_key", 0)) == 11396:
                return Response(429, text="rate limited")
            return None

        result = self.run_collection(sessions, handler)
        self.assertEqual(result["rc"], 1)
        self.assertGreater(
            sum(int(row["rows"]) for row in result["diagnostics"]
                if row["lane"] == "weather"),
            0,
        )
        self.assertEqual(self.lane_row(result, "weather")["status"], "fail")
        self.assertEqual(self.readiness_row(result, "weather")["result"], "fail")

    def test_required_session_silent_empty_holds(self):
        sessions = [session(11395), session(11396)]

        def handler(endpoint, params):
            if endpoint == "weather" and int(params.get("session_key", 0)) == 11396:
                return Response(data=[])
            return None

        result = self.run_collection(sessions, handler)
        self.assertEqual(result["rc"], 1)
        row = self.lane_row(result, "weather")
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["reason"], "required_session_zero_rows")

    def test_position_material_failure_can_be_provably_recovered(self):
        def handler(endpoint, params):
            if endpoint == "position" and "session_key" in params:
                return Response(429, text="rate limited")
            return None

        result = self.run_collection([session()], handler)
        self.assertEqual(result["rc"], 0)
        row = self.lane_row(result, "position")
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["reason"], "endpoint_fallback_recovered_complete")
        self.assertTrue(row["fallback_recovered"])
        self.assertEqual(row["request_statuses"], "http_429,pass")
        self.assertEqual(len(result["calls"]), 11)

    def test_position_fallback_wrong_session_or_exhausted_holds(self):
        for label, fallback in (
            ("wrong_session", Response(data=[endpoint_row(
                "position", {"session_key": 99999, "meeting_key": 1297}
            )])),
            ("exhausted", Response(503, text="still unavailable")),
        ):
            def handler(endpoint, params, value=fallback):
                if endpoint == "position" and "session_key" in params:
                    return Response(429, text="rate limited")
                if endpoint == "position" and "meeting_key" in params:
                    return value
                return None

            with self.subTest(label=label):
                result = self.run_collection([session()], handler)
                self.assertEqual(result["rc"], 1)
                self.assertEqual(self.lane_row(result, "position")["status"], "fail")

    def test_driver_material_failure_can_be_recovered_only_for_all_observed(self):
        def recovered(endpoint, params):
            if endpoint == "drivers" and "driver_number" not in params:
                return Response(429, text="rate limited")
            return None

        result = self.run_collection([session()], recovered)
        self.assertEqual(result["rc"], 0)
        row = self.lane_row(result, "drivers")
        self.assertEqual(row["status"], "pass")
        self.assertTrue(row["fallback_recovered"])
        self.assertEqual(len(result["calls"]), 11)

        def exhausted(endpoint, params):
            if endpoint == "drivers":
                return Response(429, text="rate limited")
            return None

        failed = self.run_collection([session()], exhausted)
        self.assertEqual(failed["rc"], 1)
        self.assertEqual(self.lane_row(failed, "drivers")["status"], "fail")

    def test_optional_and_semantic_absence_do_not_blanket_veto(self):
        def handler(endpoint, _params):
            if endpoint in {"intervals", "team_radio"}:
                return Response(404, text="not available")
            return None

        result = self.run_collection([session()], handler)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(self.lane_row(result, "intervals")["status"],
                         "pass_with_warnings")
        self.assertEqual(self.lane_row(result, "team_radio")["status"],
                         "pass_with_warnings")

    def test_required_race_pit_404_holds_but_practice_pit_is_skipped(self):
        result = self.run_collection(
            [session()],
            lambda endpoint, _params: (
                Response(404, text="missing") if endpoint == "pit" else None
            ),
        )
        self.assertEqual(result["rc"], 1)
        self.assertEqual(self.lane_row(result, "pit")["reason"],
                         "required_session_http_404")

        practice = session(name="Practice 1")
        practice["session_type"] = "Practice"
        practice_result = self.run_collection([practice])
        self.assertEqual(practice_result["rc"], 0)
        pit = self.lane_row(practice_result, "pit")
        self.assertEqual(pit["status"], "skipped_not_applicable")
        self.assertEqual(
            sum(1 for endpoint, _params, _timeout in practice_result["calls"]
                if endpoint == "pit"),
            0,
        )

    def test_saved_106_session_rate_limit_shape_cannot_aggregate_pass(self):
        saved = pd.read_csv(
            ROOT / "latest/openf1_lightweight_source_closure/request_log.csv"
        )
        self.assertEqual(len(saved), 2612)
        self.assertEqual(int((saved["status"] == "http_429").sum()), 1869)
        self.assertEqual(int((saved["status"] == "http_404").sum()), 201)
        self.assertEqual(int(
            ((saved["status"] == "http_429")
             & saved["params_json"].astype(str).str.contains("11396")).sum()
        ), 46)
        rows = [
            {"status": "pass", "lane": "weather"} for _ in range(105)
        ] + [{"status": "fail", "lane": "weather"}]
        self.assertEqual(
            m.classify_lane("weather", 7029, 106, 106, rows),
            ("fail", "session_coverage_incomplete:1"),
        )

    def test_scheduled_and_orchestrator_callers_block_nonzero_collector(self):
        workflow = (
            ROOT / ".github/workflows/f1-openf1-lightweight-source-closure.yml"
        ).read_text()
        self.assertIn("python scripts/openf1/publish_openf1_lightweight_source_closure.py", workflow)
        self.assertIn("if: ${{ success()", workflow)

        calls = []

        def fail_collector(label, cmd, dry_run=False):
            calls.append((label, cmd, dry_run))
            return {"label": label, "returncode": 1}

        with mock.patch.object(orchestrator, "run_command", side_effect=fail_collector):
            steps = orchestrator.run_pipeline(
                "2026_1297_austin", "Austin", "post_event", True, 2026, False
            )
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["returncode"], 1)
        self.assertEqual(len(calls), 1)

    def test_manual_shadow_entry_points_remain_separate(self):
        source = SCRIPT.read_text()
        self.assertIn("if args.provenance_shadow_session_key:", source)
        self.assertLess(
            source.index("if args.provenance_shadow_session_key:"),
            source.index("policy = load_policy()"),
        )
        self.assertEqual(m.SHADOW_ENDPOINTS, ("weather", "drivers", "starting_grid"))


if __name__ == "__main__":
    unittest.main()
