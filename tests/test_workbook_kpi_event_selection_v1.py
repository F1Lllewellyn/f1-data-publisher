#!/usr/bin/env python3
"""Fail-closed active-event regressions for the Workbook/KPI Refresh Applier."""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "workbook_kpi_refresh" / "apply_workbook_kpi_refresh_v1.py"
SPEC = importlib.util.spec_from_file_location("workbook_kpi_applier", MODULE_PATH)
assert SPEC and SPEC.loader
applier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(applier)

NOW = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
AUSTIN = "2026_1297_united_states_austin_austin"
BAHRAIN = "2026_1308_bahrain_kuala_lumpur_kuala_lumpur"
FP1_KEY = 11389
FP2_KEY = 11390
MANUAL_REVIEW_FLAGS = (
    "data_readiness.needs_manual_review",
    "data_readiness.source_needs_manual_review",
    "combined_source.source_needs_manual_review",
    "source_readiness.source_needs_manual_review",
    "readiness_aggregation.needs_manual_review",
)


def write_json(root: Path, relative: str, value: object) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def session_identity(
    meeting_key: int = 1297,
    session_key: int = FP2_KEY,
    session_name: str = "Practice 2",
    session_type: str = "Practice",
    start: str = "2026-10-23T21:00:00+00:00",
    end: str = "2026-10-23T22:00:00+00:00",
) -> dict:
    return {
        "date_start": start,
        "date_end": end,
        "gate": "post_fp2",
        "meeting_key": meeting_key,
        "session_key": session_key,
        "session_name": session_name,
        "session_type": session_type,
    }


def fixture_payloads(
    *,
    event_id: str = AUSTIN,
    meeting_key: int = 1297,
    session_key: int = FP2_KEY,
    session_name: str = "Practice 2",
    session_type: str = "Practice",
    status: str = "clean",
    quality: str = "usable_with_optional_context_gaps",
    start: str = "2026-10-23T21:00:00+00:00",
    end: str = "2026-10-23T22:00:00+00:00",
    generated: str = "2026-10-24T16:56:30Z",
) -> dict[str, object]:
    session = session_identity(
        meeting_key,
        session_key,
        session_name,
        session_type,
        start,
        end,
    )
    slug = session_name.lower().replace(" ", "_")
    processor = f"latest/session_data_processor/{event_id}/{slug}_{session_key}"
    source_summaries = {
        f"openf1_{endpoint}": {
            "rows": 20 + index,
            "status": "clean",
            "driver_count": 20 if endpoint != "weather" else 0,
            "max_lap_number": 30 if endpoint == "laps" else None,
        }
        for index, endpoint in enumerate(("drivers", "laps", "position", "weather"))
    }
    per_source = {
        name: {
            "endpoint": name.removeprefix("openf1_"),
            "role": "required",
            "raw_status": summary["status"],
            "effective_status": summary["status"],
            "classification": "critical_clean",
            "rows": summary["rows"],
            "blocking": False,
            "reason": "required_source_clean",
            "missing_required_columns": [],
            "anomalies": [],
        }
        for name, summary in source_summaries.items()
    }
    aggregation = {
        "schema_version": "source_readiness_aggregation_v2",
        "overall_status": status,
        "readiness_quality": quality,
        "needs_manual_review": False,
        "critical_endpoints": ["drivers", "laps", "position", "weather"],
        "missing_required_endpoints": [],
        "blocking_issues": [],
        "critical_late": [],
        "critical_partial": [],
        "optional_context_gaps": [],
        "per_source": per_source,
    }
    ledger = {
        "schema_version": "forecast_bundle_ledger_session_snapshot_v1",
        "created_utc": generated,
        "event_id": event_id,
        "overall_status": status,
        "promotion_allowed": False,
        "race_name": "United States - Austin - Austin",
        "session": copy.deepcopy(session),
    }
    source = {
        "schema_version": "session_readiness_manifest_v1",
        "created_utc": generated,
        "event_id": event_id,
        "overall_status": status,
        "readiness_quality": quality,
        "source_needs_manual_review": False,
        "race_name": "United States - Austin - Austin",
        "session": copy.deepcopy(session),
        "readiness_aggregation": aggregation,
        "forecast_bundle_ledger_snapshot": copy.deepcopy(ledger),
        "sources": copy.deepcopy(source_summaries),
        "workbook_kpi_update": {
            "path": f"{processor}/workbook_kpi_readiness.json",
            "mode": "sandbox_artifact",
            "canonical_workbook_modified": False,
        },
    }
    selector = {
        "schema_version": "latest_manifest_v2_session_processor",
        "event_id": event_id,
        "session_key": session_key,
        "session_name": session_name,
        "overall_status": status,
        "latest_session_data_processor_manifest": f"{processor}/source_readiness_manifest.json",
        "updated_utc": generated,
    }
    readiness = {
        "schema_version": "data_readiness_v2_session_processor",
        "event_id": event_id,
        "race_name": "United States - Austin - Austin",
        "session": copy.deepcopy(session),
        "overall_status": status,
        "readiness_quality": quality,
        "needs_manual_review": False,
        "source_needs_manual_review": False,
        "sources": {
            name: {"rows": value["rows"], "status": value["status"]}
            for name, value in source_summaries.items()
        },
        "updated_utc": generated,
    }
    combined = {
        "schema_version": "combined_source_manifest_v2_session_processor",
        "event_id": event_id,
        "session_key": session_key,
        "overall_status": status,
        "readiness_quality": quality,
        "source_needs_manual_review": False,
        "source_layers": {"session_data_processor": f"{processor}/source_readiness_manifest.json"},
        "updated_utc": generated,
    }
    workbook = {
        "schema_version": "workbook_kpi_readiness_v1_session_processor",
        "created_utc": generated,
        "event_id": event_id,
        "race_name": "United States - Austin - Austin",
        "session": copy.deepcopy(session),
        "overall_status": status,
        "sources": copy.deepcopy(source_summaries),
    }
    plan = {
        "schema_version": "sandbox_workbook_update_plan_v1",
        "created_utc": generated,
        "canonical_workbook_modified": False,
    }
    return {
        "processor": processor,
        "selector": selector,
        "readiness": readiness,
        "combined": combined,
        "source": source,
        "ledger": ledger,
        "workbook": workbook,
        "plan": plan,
    }


def set_status(payloads: dict[str, object], status: str, quality: str) -> None:
    for name in ("selector", "readiness", "combined", "source", "ledger", "workbook"):
        payloads[name]["overall_status"] = status  # type: ignore[index]
    payloads["readiness"]["readiness_quality"] = quality  # type: ignore[index]
    payloads["combined"]["readiness_quality"] = quality  # type: ignore[index]
    payloads["source"]["readiness_quality"] = quality  # type: ignore[index]
    aggregation = payloads["source"]["readiness_aggregation"]  # type: ignore[index]
    aggregation["overall_status"] = status
    aggregation["readiness_quality"] = quality


def set_manual_review_flags(payloads: dict[str, object], value: bool) -> None:
    payloads["readiness"]["needs_manual_review"] = value  # type: ignore[index]
    payloads["readiness"]["source_needs_manual_review"] = value  # type: ignore[index]
    payloads["combined"]["source_needs_manual_review"] = value  # type: ignore[index]
    payloads["source"]["source_needs_manual_review"] = value  # type: ignore[index]
    payloads["source"]["readiness_aggregation"]["needs_manual_review"] = value  # type: ignore[index]


def manual_flag_target(payloads: dict[str, object], label: str) -> tuple[dict, str]:
    if label == "data_readiness.needs_manual_review":
        return payloads["readiness"], "needs_manual_review"  # type: ignore[return-value]
    if label == "data_readiness.source_needs_manual_review":
        return payloads["readiness"], "source_needs_manual_review"  # type: ignore[return-value]
    if label == "combined_source.source_needs_manual_review":
        return payloads["combined"], "source_needs_manual_review"  # type: ignore[return-value]
    if label == "source_readiness.source_needs_manual_review":
        return payloads["source"], "source_needs_manual_review"  # type: ignore[return-value]
    if label == "readiness_aggregation.needs_manual_review":
        return payloads["source"]["readiness_aggregation"], "needs_manual_review"  # type: ignore[return-value,index]
    raise AssertionError(f"unknown manual-review flag: {label}")


def install_session_artifacts(root: Path, payloads: dict[str, object]) -> list[Path]:
    processor = payloads["processor"]
    paths = [
        write_json(root, f"{processor}/source_readiness_manifest.json", payloads["source"]),
        write_json(root, f"{processor}/sandbox_workbook_update_plan.json", payloads["plan"]),
        write_json(root, f"{processor}/workbook_kpi_readiness.json", payloads["workbook"]),
        write_json(root, f"{processor}/forecast_bundle_ledger_snapshot.json", payloads["ledger"]),
    ]
    sources = payloads["workbook"]["sources"]  # type: ignore[index]
    csv_path = root / str(processor) / "workbook_kpi_readiness.csv"
    applier.write_csv(
        csv_path,
        [
            {
                "endpoint": name,
                "status": value["status"],
                "rows": value["rows"],
                "driver_count": value["driver_count"],
                "max_lap_number": value["max_lap_number"],
            }
            for name, value in sources.items()
        ],
    )
    paths.append(csv_path)
    return paths


def install_fixture(root: Path, payloads: dict[str, object] | None = None) -> dict[str, object]:
    payloads = copy.deepcopy(payloads or fixture_payloads())
    write_json(root, "latest/latest_manifest.json", payloads["selector"])
    write_json(root, "latest/data_readiness.json", payloads["readiness"])
    write_json(root, "latest/combined_source_manifest.json", payloads["combined"])
    install_session_artifacts(root, payloads)
    return payloads


def run_main(root: Path, *, safe_test: bool = False) -> dict:
    argv = [str(MODULE_PATH), "--repo-root", str(root)]
    if safe_test:
        argv.append("--safe-test")
    with (
        mock.patch.object(applier, "utc_datetime", return_value=NOW),
        mock.patch("sys.argv", argv),
        redirect_stdout(io.StringIO()),
    ):
        result = applier.main()
    assert result == 0
    name = "workbook_kpi_refresh_applier_safe_test.json" if safe_test else "workbook_kpi_refresh_status.json"
    return json.loads((root / "_runtime" / name).read_text(encoding="utf-8"))


def assert_no_publication(test: unittest.TestCase, root: Path) -> None:
    test.assertFalse((root / "latest/workbook_kpi_refresh_applier").exists())
    test.assertFalse((root / "history/workbook_kpi_refresh_applier").exists())


class WorkbookKpiEventSelectionTests(unittest.TestCase):
    def test_austin_fp1_then_fp2_selects_exact_authoritative_fp2(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            install_fixture(root)
            fp1 = fixture_payloads(session_key=FP1_KEY, session_name="Practice 1")
            for path in install_session_artifacts(root, fp1):
                os.utime(path, (2_000_000_000, 2_000_000_000))

            state = applier.build_authority_state(root, NOW)

            self.assertTrue(state["valid"], state["reasons"])
            self.assertEqual(state["session_key"], FP2_KEY)
            self.assertEqual(applier.repo_relative(state["session_root"], root), fixture_payloads()["processor"])

    def test_newer_bahrain_mtime_and_reversed_traversal_never_displace_austin(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            install_fixture(root)
            for index in reversed(range(12)):
                bahrain = fixture_payloads(
                    event_id=BAHRAIN,
                    meeting_key=1308,
                    session_key=11731 + index,
                    session_name=f"Race {index}",
                    session_type="Race",
                )
                for path in install_session_artifacts(root, bahrain):
                    os.utime(path, (2_100_000_000 - index, 2_100_000_000 - index))

            with mock.patch.object(Path, "rglob", side_effect=AssertionError("recursive discovery forbidden")):
                state = applier.build_authority_state(root, NOW)

            self.assertTrue(state["valid"], state["reasons"])
            self.assertEqual(state["event_id"], AUSTIN)
            self.assertEqual(state["session_key"], FP2_KEY)

    def test_safe_test_does_not_pass_from_arbitrary_historical_source(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            historical = fixture_payloads(event_id=BAHRAIN, meeting_key=1308, session_key=11731, session_name="Race", session_type="Race")
            write_json(root, f"{historical['processor']}/source_readiness_manifest.json", historical["source"])

            result = run_main(root, safe_test=True)

            self.assertEqual(result["status"], "safe_test_hold")
            self.assertFalse(result["commit_allowed"])
            assert_no_publication(self, root)

    def test_missing_traversed_escaped_or_incomplete_authority_fails_closed(self):
        cases = ("missing_selector", "path_traversal", "symlink_escape", "missing_required")
        for case in cases:
            with self.subTest(case=case), TemporaryDirectory() as td:
                base = Path(td)
                root = base / "repo"
                payloads = install_fixture(root)
                if case == "missing_selector":
                    (root / "latest/latest_manifest.json").unlink()
                elif case == "path_traversal":
                    selector_path = root / "latest/latest_manifest.json"
                    selector = json.loads(selector_path.read_text())
                    selector["latest_session_data_processor_manifest"] = (
                        "latest/session_data_processor/../outside/source_readiness_manifest.json"
                    )
                    write_json(root, "latest/latest_manifest.json", selector)
                elif case == "symlink_escape":
                    manifest = root / str(payloads["processor"]) / "source_readiness_manifest.json"
                    outside = write_json(base, "outside.json", payloads["source"])
                    manifest.unlink()
                    manifest.symlink_to(outside)
                else:
                    (root / str(payloads["processor"]) / "forecast_bundle_ledger_snapshot.json").unlink()

                result = run_main(root)

                self.assertEqual(result["status"], "no_action")
                self.assertFalse(result["commit_allowed"])
                assert_no_publication(self, root)

    def test_symlinked_publication_targets_hold_before_any_publish_or_outside_write(self):
        cases = ("dangling_latest_file", "symlinked_latest_directory", "symlinked_history_parent")
        for case in cases:
            with self.subTest(case=case), TemporaryDirectory() as td:
                base = Path(td)
                root = base / "repo"
                outside = base / "outside"
                install_fixture(root)
                latest_out = root / "latest/workbook_kpi_refresh_applier"
                history_parent = root / "history/workbook_kpi_refresh_applier"

                if case == "dangling_latest_file":
                    latest_out.mkdir(parents=True)
                    outside_file = outside / "escaped.json"
                    (latest_out / "upstream_latest_manifest_snapshot.json").symlink_to(outside_file)
                elif case == "symlinked_latest_directory":
                    outside.mkdir()
                    latest_out.parent.mkdir(parents=True, exist_ok=True)
                    latest_out.symlink_to(outside, target_is_directory=True)
                else:
                    outside.mkdir()
                    history_parent.parent.mkdir(parents=True)
                    history_parent.symlink_to(outside, target_is_directory=True)

                result = run_main(root)

                self.assertEqual(result["status"], "no_action")
                self.assertEqual(result["reason"], "unsafe_or_existing_output_target")
                self.assertFalse(result["commit_allowed"])
                self.assertFalse((outside / "escaped.json").exists())
                if outside.exists():
                    self.assertEqual(list(outside.iterdir()), [])
                if case == "dangling_latest_file":
                    self.assertEqual(
                        [path.name for path in latest_out.iterdir()],
                        ["upstream_latest_manifest_snapshot.json"],
                    )
                elif case == "symlinked_history_parent":
                    self.assertFalse(latest_out.exists())
                self.assertFalse((history_parent / NOW.strftime("%Y%m%dT%H%M%SZ")).exists())

    def test_event_meeting_session_and_status_disagreements_fail_closed(self):
        cases = ("event", "meeting", "session", "session_type", "status")
        for case in cases:
            with self.subTest(case=case), TemporaryDirectory() as td:
                root = Path(td)
                payloads = install_fixture(root)
                if case == "event":
                    payloads["workbook"]["event_id"] = BAHRAIN  # type: ignore[index]
                    write_json(root, f"{payloads['processor']}/workbook_kpi_readiness.json", payloads["workbook"])
                elif case == "meeting":
                    payloads["readiness"]["session"]["meeting_key"] = 1308  # type: ignore[index]
                    write_json(root, "latest/data_readiness.json", payloads["readiness"])
                elif case == "session":
                    payloads["ledger"]["session"]["session_key"] = 99999  # type: ignore[index]
                    write_json(root, f"{payloads['processor']}/forecast_bundle_ledger_snapshot.json", payloads["ledger"])
                elif case == "session_type":
                    payloads["source"]["session"]["session_type"] = "Race"  # type: ignore[index]
                    write_json(root, f"{payloads['processor']}/source_readiness_manifest.json", payloads["source"])
                else:
                    payloads["combined"]["overall_status"] = "partial"  # type: ignore[index]
                    write_json(root, "latest/combined_source_manifest.json", payloads["combined"])

                result = run_main(root)

                self.assertEqual(result["status"], "no_action")
                self.assertFalse(result["commit_allowed"])
                assert_no_publication(self, root)

    def test_each_contradictory_manual_review_flag_fails_closed(self):
        for label in MANUAL_REVIEW_FLAGS:
            with self.subTest(label=label), TemporaryDirectory() as td:
                root = Path(td)
                payloads = fixture_payloads()
                target, key = manual_flag_target(payloads, label)
                target[key] = True
                install_fixture(root, payloads)

                result = run_main(root)

                self.assertEqual(result["status"], "no_action")
                self.assertFalse(result["commit_allowed"])
                self.assertIn("manual_review_flag_mismatch", result["hold_reasons"])
                self.assertFalse(result["downstream_eligible"])
                assert_no_publication(self, root)

    def test_missing_or_malformed_manual_review_authority_fails_closed(self):
        for label in MANUAL_REVIEW_FLAGS:
            for mode in ("missing", "malformed"):
                with self.subTest(label=label, mode=mode), TemporaryDirectory() as td:
                    root = Path(td)
                    payloads = fixture_payloads()
                    target, key = manual_flag_target(payloads, label)
                    if mode == "missing":
                        target.pop(key)
                    else:
                        target[key] = "false"
                    install_fixture(root, payloads)

                    result = run_main(root)

                    self.assertEqual(result["status"], "no_action")
                    self.assertFalse(result["commit_allowed"])
                    self.assertIn(
                        f"missing_or_invalid_manual_review_flag:{label}",
                        result["hold_reasons"],
                    )
                    self.assertFalse(result["downstream_eligible"])
                    assert_no_publication(self, root)

    def test_missing_session_name_or_type_across_authority_fails_closed(self):
        for field in ("session_name", "session_type"):
            with self.subTest(field=field), TemporaryDirectory() as td:
                root = Path(td)
                payloads = fixture_payloads()
                for name in ("readiness", "source", "workbook", "ledger"):
                    payloads[name]["session"].pop(field)  # type: ignore[index]
                if field == "session_name":
                    payloads["selector"].pop("session_name")  # type: ignore[union-attr]
                payloads["source"]["forecast_bundle_ledger_snapshot"] = copy.deepcopy(payloads["ledger"])  # type: ignore[index]
                install_fixture(root, payloads)

                result = run_main(root)

                self.assertEqual(result["status"], "no_action")
                self.assertFalse(result["commit_allowed"])
                self.assertIn(f"invalid_authoritative_{field}", result["hold_reasons"])
                self.assertFalse(result["downstream_eligible"])
                assert_no_publication(self, root)

    def test_stale_future_and_invalid_chronology_fail_closed(self):
        cases = ("stale", "future", "chronology")
        for case in cases:
            with self.subTest(case=case), TemporaryDirectory() as td:
                root = Path(td)
                if case == "stale":
                    payloads = fixture_payloads(
                        start="2026-10-10T21:00:00Z",
                        end="2026-10-10T22:00:00Z",
                        generated="2026-10-10T22:01:00Z",
                    )
                else:
                    payloads = fixture_payloads()
                payloads = install_fixture(root, payloads)
                if case == "future":
                    payloads["selector"]["updated_utc"] = "2026-10-24T17:10:01Z"  # type: ignore[index]
                    write_json(root, "latest/latest_manifest.json", payloads["selector"])
                elif case == "chronology":
                    for name in ("readiness", "source", "workbook", "ledger"):
                        payloads[name]["session"]["date_end"] = "2026-10-23T20:00:00Z"  # type: ignore[index]
                    payloads["source"]["forecast_bundle_ledger_snapshot"] = copy.deepcopy(payloads["ledger"])  # type: ignore[index]
                    write_json(root, "latest/data_readiness.json", payloads["readiness"])
                    write_json(root, f"{payloads['processor']}/source_readiness_manifest.json", payloads["source"])
                    write_json(root, f"{payloads['processor']}/workbook_kpi_readiness.json", payloads["workbook"])
                    write_json(root, f"{payloads['processor']}/forecast_bundle_ledger_snapshot.json", payloads["ledger"])

                result = run_main(root)

                self.assertEqual(result["status"], "no_action")
                assert_no_publication(self, root)

    def test_authority_change_during_build_is_caught_before_publication(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            install_fixture(root)
            original = applier.create_or_update_sandbox_workbook

            def mutate_after_build(*args, **kwargs):
                original(*args, **kwargs)
                selector_path = root / "latest/latest_manifest.json"
                selector = json.loads(selector_path.read_text())
                selector["session_key"] = 99999
                write_json(root, "latest/latest_manifest.json", selector)

            argv = [str(MODULE_PATH), "--repo-root", str(root)]
            with (
                mock.patch.object(applier, "utc_datetime", return_value=NOW),
                mock.patch.object(applier, "create_or_update_sandbox_workbook", side_effect=mutate_after_build),
                mock.patch("sys.argv", argv),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(applier.main(), 0)

            result = json.loads((root / "_runtime/workbook_kpi_refresh_status.json").read_text())
            self.assertEqual(result["reason"], "authority_changed_during_in_process_build")
            self.assertFalse(result["commit_allowed"])
            assert_no_publication(self, root)

    def test_valid_clean_source_publishes_correct_sandbox_identity(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            install_fixture(root)

            safe_result = run_main(root, safe_test=True)

            self.assertEqual(safe_result["status"], "safe_test_pass")
            self.assertFalse(safe_result["commit_allowed"])
            self.assertTrue(safe_result["required_session_sources_present"])
            self.assertEqual(safe_result["event_id"], AUSTIN)
            self.assertEqual(safe_result["session_key"], FP2_KEY)
            assert_no_publication(self, root)

            result = run_main(root)

            self.assertEqual(result["status"], "refresh_applied")
            self.assertTrue(result["commit_allowed"])
            self.assertTrue(result["downstream_eligible"])
            self.assertEqual(result["event_id"], AUSTIN)
            self.assertEqual(result["session_key"], FP2_KEY)
            manifest = json.loads((root / "latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json").read_text())
            self.assertEqual(manifest["source_processor_root"], fixture_payloads()["processor"])
            self.assertEqual(manifest["session_key"], FP2_KEY)
            self.assertTrue(manifest["downstream_eligible"])
            self.assertFalse(manifest["governance"]["stable_engine_modified"])

    def test_approved_partial_is_eligible_but_manual_review_is_diagnostic_only(self):
        with TemporaryDirectory() as partial_td:
            partial_root = Path(partial_td)
            partial = fixture_payloads()
            set_status(partial, "partial", "usable_with_required_source_partial")
            weather = partial["source"]["readiness_aggregation"]["per_source"]["openf1_weather"]  # type: ignore[index]
            weather.update({
                "raw_status": "partial",
                "effective_status": "partial",
                "classification": "critical_partial",
                "reason": "required_source_partial_but_usable",
            })
            partial["source"]["readiness_aggregation"]["critical_partial"] = [{"endpoint": "weather"}]  # type: ignore[index]
            for name in ("source", "readiness", "workbook"):
                partial[name]["sources"]["openf1_weather"]["status"] = "partial"  # type: ignore[index]
            partial["source"]["forecast_bundle_ledger_snapshot"] = copy.deepcopy(partial["ledger"])  # type: ignore[index]
            install_fixture(partial_root, partial)
            partial_result = run_main(partial_root)
            self.assertTrue(partial_result["downstream_eligible"])

        with TemporaryDirectory() as manual_td:
            manual_root = Path(manual_td)
            manual = fixture_payloads()
            set_status(manual, "needs_manual_review", "blocked_manual_review_required_source")
            set_manual_review_flags(manual, True)
            aggregation = manual["source"]["readiness_aggregation"]  # type: ignore[index]
            aggregation["blocking_issues"] = [{"endpoint": "weather"}]
            weather = aggregation["per_source"]["openf1_weather"]
            weather.update({
                "raw_status": "needs_manual_review",
                "effective_status": "needs_manual_review",
                "blocking": True,
            })
            for name in ("source", "readiness", "workbook"):
                manual[name]["sources"]["openf1_weather"]["status"] = "needs_manual_review"  # type: ignore[index]
            manual["source"]["forecast_bundle_ledger_snapshot"] = copy.deepcopy(manual["ledger"])  # type: ignore[index]
            install_fixture(manual_root, manual)
            manual_result = run_main(manual_root)
            self.assertTrue(manual_result["commit_allowed"])
            self.assertTrue(manual_result["diagnostic_publish_allowed"])
            self.assertFalse(manual_result["downstream_eligible"])
            self.assertTrue(manual_result["manual_review_required"])


if __name__ == "__main__":
    unittest.main()
