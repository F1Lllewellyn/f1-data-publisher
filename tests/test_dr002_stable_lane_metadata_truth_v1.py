"""Focused regression tests for the stable-lane metadata identity correction."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


writer = load_module(
    "gate_writer", "scripts/forecast_bundles/write_gate_forecast_rows_v1.py"
)
locker = load_module(
    "bundle_locker", "scripts/forecast_bundles/create_forecast_bundles_v1.py"
)

STABLE_CONFIG = "StableBaseline_LanePolicy_v1"
LEGACY_ENGINE = "Engine_2026-06-07_STABLE"
STABLE_NOTE = (
    "stable_baseline is a lane/policy label; no separate protected stable-engine "
    "execution is claimed."
)
NON_STABLE = {
    "control_room_overlay": "MethodE_ControlRoom_Overlay",
    "experimental_challenger": "IntegratedSpecialist_RecalibratedReliability_EOL_EXPERIMENTAL",
}
LOCKER_NON_STABLE = {
    "control_room_overlay": "MethodE_ControlRoom_Overlay",
    "experimental_challenger": "Integrated_Recalibrated_Specialist_Challenger",
}


class StableLaneMetadataTruthTests(unittest.TestCase):
    def sample_row(self, config=LEGACY_ENGINE):
        row = {column: "" for column in writer.REQUIRED_COLUMNS}
        row.update(
            {
                "engine_lane_config": config,
                "forecast_timestamp_utc": "2026-10-05T14:00:00Z",
                "predicted_qualifying_position": "3",
                "predicted_race_finish_position": "2",
                "predicted_points_band": "18-25",
                "predicted_dnf_probability": "0.04",
                "predicted_top1_probability": "0.22",
                "predicted_top3_probability": "0.64",
                "predicted_top5_probability": "0.81",
                "predicted_top10_probability": "0.97",
                "predicted_mean_finish_position": "2.8",
                "confidence_score": "0.72",
                "notes": "source note",
            }
        )
        return row

    def test_live_mappings_use_lane_policy_identity(self):
        self.assertEqual(writer.LANE_CONFIG["stable_baseline"], STABLE_CONFIG)
        self.assertEqual(locker.LANES["stable_baseline"], STABLE_CONFIG)
        self.assertEqual(
            {lane: writer.LANE_CONFIG[lane] for lane in NON_STABLE}, NON_STABLE
        )
        self.assertEqual(
            {lane: locker.LANES[lane] for lane in LOCKER_NON_STABLE},
            LOCKER_NON_STABLE,
        )
        for module_path in (
            ROOT / "scripts/forecast_bundles/write_gate_forecast_rows_v1.py",
            ROOT / "scripts/forecast_bundles/create_forecast_bundles_v1.py",
        ):
            self.assertNotIn(LEGACY_ENGINE, module_path.read_text(encoding="utf-8"))

    def test_writer_replaces_stale_stable_config_and_disclaims_execution(self):
        source = self.sample_row()
        with patch.object(writer, "utcnow", return_value="2026-10-05T15:00:00Z"):
            row = writer.normalize_rows(
                [source], "synthetic-event", "post_qualifying", "stable_baseline"
            )[0]
        self.assertEqual(row["engine_lane"], "stable_baseline")
        self.assertEqual(row["engine_lane_config"], STABLE_CONFIG)
        self.assertIn(STABLE_NOTE, row["notes"])
        self.assertNotIn(LEGACY_ENGINE, row["engine_lane_config"])

    def test_writer_preserves_prediction_values_and_non_stable_behavior(self):
        source = self.sample_row(config="")
        expected_predictions = {
            key: value for key, value in source.items() if key.startswith("predicted_")
        }
        for lane, expected_config in NON_STABLE.items():
            with self.subTest(lane=lane), patch.object(
                writer, "utcnow", return_value="2026-10-05T15:00:00Z"
            ):
                row = writer.normalize_rows(
                    [source], "synthetic-event", "post_qualifying", lane
                )[0]
                self.assertEqual(row["engine_lane_config"], expected_config)
                self.assertEqual(
                    {key: row[key] for key in expected_predictions},
                    expected_predictions,
                )
                self.assertNotIn(STABLE_NOTE, row["notes"])
        existing = self.sample_row(config="Existing_NonStable_Config")
        row = writer.normalize_rows(
            [existing], "synthetic-event", "post_qualifying", "control_room_overlay"
        )[0]
        self.assertEqual(row["engine_lane_config"], "Existing_NonStable_Config")

    def test_locker_writes_fail_closed_metadata_without_changing_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = (
                root
                / "source/latest/forecasts/event/post_qualifying/stable_baseline/forecast_rows.csv"
            )
            source.parent.mkdir(parents=True)
            original = self.sample_row()
            with source.open("w", newline="", encoding="utf-8") as handle:
                output = csv.DictWriter(handle, fieldnames=writer.REQUIRED_COLUMNS)
                output.writeheader()
                output.writerow(original)
            # G5 closes the direct scientific bypass. Label-only source rows
            # cannot create a bundle, even with a truthful lane configuration.
            before=source.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'HOLD_STABLE_ENGINE_NOT_EXECUTED'):
                locker.create_bundle(root/'repo','event','2026','1','Synthetic','post_qualifying','stable_baseline',root/'source',False,include_existing_bundles=False)
            self.assertEqual(source.read_bytes(),before)
            self.assertFalse((root/'repo').exists())

    def test_locker_non_stable_configs_remain_unchanged(self):
        self.assertEqual(
            locker.LANES["control_room_overlay"],
            "MethodE_ControlRoom_Overlay",
        )
        self.assertEqual(
            locker.LANES["experimental_challenger"],
            "Integrated_Recalibrated_Specialist_Challenger",
        )

    def test_current_producer_blob_is_unchanged(self):
        data = (ROOT / "scripts/forecasts/produce_actual_forecast_rows_v1.py").read_bytes()
        git_blob = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        ).hexdigest()
        self.assertEqual(git_blob, "af27586668c767de126af829c1131c6bae4634ad")


if __name__ == "__main__":
    unittest.main()
