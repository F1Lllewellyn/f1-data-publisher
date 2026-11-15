"""Synthetic operational byte custody; never scientific or live source evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


processor = load("custody_processor", "scripts/session_data_processor/session_data_processor_loop_v1.py")
dashboard = load("custody_dashboard", "scripts/dashboard_connector/publish_forecast_fantasy_readiness_dashboards_v1.py")


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True))


from test_sp2026_integrated_recovery_guard_v1 import bind_synthetic_fixture


class ByteCustodyTests(unittest.TestCase):
    def setUp(self):
        # Import lazily; legacy fixture imports this helper without a cycle.
        from test_dashboard_event_selection_readiness_v1 import install_fixture, NOW
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install_fixture(self.root)
        self.now = NOW
        self.selector = json.loads((self.root / "latest/latest_manifest.json").read_text())
        self.source_path = self.root / self.selector["latest_session_data_processor_manifest"]
        self.workbook_path = self.root / "latest/workbook_kpi_refresh_applier/workbook_kpi_refresh_manifest.json"

    def observe(self):
        return dashboard.discover_state(self.root, self.now)

    def test_complete_context_is_not_engine_execution(self):
        result = self.observe()
        self.assertTrue(result["downstream_eligible"], result["readiness_reasons"])
        self.assertGreater(len(result["consumed_fingerprints"]), 4)
        self.assertFalse(result["prediction_locked"])
        self.assertFalse(result["stable_engine_executed"])

    def test_workbook_corrupt_bytes_or_missing_binding_holds(self):
        workbook = json.loads(self.workbook_path.read_text())
        path = self.root / workbook["outputs"][0]["path"]
        path.write_bytes(path.read_bytes() + b"corrupt")
        result = self.observe()
        self.assertFalse(result["downstream_eligible"])
        self.assertIn("workbook_output_integrity_failed", result["readiness_reasons"])

    def test_source_tamper_even_with_matching_labels_holds(self):
        source = json.loads(self.source_path.read_text())
        path = self.root / source["sources"]["openf1_weather"]["json_path"]
        path.write_bytes(path.read_bytes() + b" ")
        self.assertFalse(self.observe()["downstream_eligible"])

    def test_rehashed_wrong_identity_or_future_rows_still_hold(self):
        for field, value in (("meeting_key", 999), ("session_key", 999), ("date", "2099-01-01T00:00:00Z")):
            with self.subTest(field=field):
                bind_synthetic_fixture(self.root)
                source = json.loads(self.source_path.read_text())
                report = source["sources"]["openf1_weather"]
                path = self.root / report["json_path"]
                rows = json.loads(path.read_text()); rows[0][field] = value; write(path, rows)
                report["json_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                write(self.source_path, source)
                result = self.observe()
                self.assertFalse(result["downstream_eligible"])
                self.assertTrue(any(r.startswith("source_bytes_unverified:openf1_weather") for r in result["readiness_reasons"]))

    def test_upstream_republication_invalidates_old_workbook(self):
        selector = copy.deepcopy(self.selector)
        selector["updated_utc"] = "2026-10-18T11:16:00Z"
        write(self.root / "latest/latest_manifest.json", selector)
        self.assertIn("workbook_authority_bytes_changed", self.observe()["readiness_reasons"])

    def test_symlink_or_deleted_artifact_holds(self):
        workbook = json.loads(self.workbook_path.read_text())
        path = self.root / workbook["outputs"][0]["path"]
        path.unlink()
        path.symlink_to(self.source_path)
        self.assertFalse(self.observe()["downstream_eligible"])

    def test_rehashed_unknown_driver_fails_independent_roster_verification(self):
        source = json.loads(self.source_path.read_text())
        report = source['sources']['openf1_position']; path = self.root/report['json_path']
        rows=json.loads(path.read_text()); rows[0]['driver_number']=999; write(path, rows)
        report['json_sha256']=hashlib.sha256(path.read_bytes()).hexdigest(); write(self.source_path,source)
        workbook=json.loads(self.workbook_path.read_text())
        workbook['authority_fingerprints'][self.source_path.relative_to(self.root).as_posix()] = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        write(self.workbook_path,workbook)
        result=self.observe()
        self.assertFalse(result['downstream_eligible'])
        self.assertIn('source_driver_identity_unverified:openf1_position',result['readiness_reasons'])

    def test_manifest_cannot_demote_weather_to_optional(self):
        source=json.loads(self.source_path.read_text())
        source['readiness_aggregation']['critical_endpoints'].remove('weather')
        source['readiness_aggregation']['per_source']['openf1_weather']['role']='optional_context'
        write(self.source_path,source)
        workbook=json.loads(self.workbook_path.read_text())
        workbook['authority_fingerprints'][self.source_path.relative_to(self.root).as_posix()] = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        write(self.workbook_path,workbook)
        result=self.observe()
        self.assertFalse(result['downstream_eligible'])
        self.assertIn('required_source_policy_mismatch',result['readiness_reasons'])


class ProcessorBoundaryTests(unittest.TestCase):
    def test_roster_validation_is_order_independent_and_rejects_invalid_numbers(self):
        for value in (None, True, 0, -1, 1.5, '1.0', 999):
            reports={f'openf1_{e}':dict(status='clean',anomalies=[]) for e in ('drivers','position')}
            rows={'position':[dict(driver_number=value)],'drivers':[dict(driver_number=1)]}
            processor.validate_driver_custody(reports,rows)
            self.assertEqual(reports['openf1_position']['status'],'conflicting',value)
        reports={'openf1_drivers':dict(status='clean',anomalies=[])}
        processor.validate_driver_custody(reports,{'drivers':[dict(driver_number=1,name='A'),dict(driver_number=1,name='B')]})
        self.assertEqual(reports['openf1_drivers']['status'],'conflicting')
        self.assertFalse(reports['openf1_drivers']['driver_custody']['official_entry_list_verified'])

    def test_missing_end_is_not_completed(self):
        session = dict(session_key=1, meeting_key=2, date_start="2026-11-21T00:00:00Z", session_name="Practice 1")
        now = processor.parse_time("2026-11-21T01:00:00Z")
        self.assertIsNone(processor.select_recent_completed_session([session], now, 36))

    def test_sparse_identity_row_is_not_clean(self):
        session = dict(session_key=1, meeting_key=2)
        rows = [dict(session_key=1, meeting_key=2, date="2026-01-01T00:00:00Z"), dict(date="2026-01-01T00:01:00Z")]
        report = processor.analyze_rows("weather", rows, session, {"ok": True})
        self.assertEqual(report["status"], "conflicting")
        self.assertIn("wrong_session_key_rows=1", report["anomalies"])

    def test_access_and_outage_latch_prevents_endpoint_retry_storm(self):
        helper = load("budget_for_processor", "scripts/openf1/publish_openf1_lightweight_source_closure.py")
        for status in (401, 403, 429, 503):
            budget = helper.NormalRequestBudget()
            with self.subTest(status=status), patch.object(processor, "REQUEST_BUDGET", budget), patch.object(processor.urllib.request, "urlopen", side_effect=urllib.error.HTTPError("offline", status, "offline", {}, None)) as get:
                for _ in range(12):
                    rows, meta = processor.http_json("https://api.openf1.org/v1/drivers?session_key=1")
                    self.assertFalse(meta["ok"])
                    self.assertEqual(rows, [])
                self.assertEqual(get.call_count, 1)
                self.assertEqual(budget.total_requests, 1)

    def test_error_object_is_not_wrapped_into_source_row(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b'{"error":"provider outage"}'
        with patch.object(processor, "REQUEST_BUDGET", MagicMock()), patch.object(processor.urllib.request, "urlopen", return_value=response):
            rows, meta = processor.http_json("https://api.openf1.org/v1/drivers")
            self.assertFalse(meta["ok"])
            self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
