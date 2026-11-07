import csv
import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "zip_index", ROOT / "scripts/maintenance/f1_retained_zip_central_directory_index_v1.py"
)
zip_index = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = zip_index
SPEC.loader.exec_module(zip_index)


def make_zip(names=None, compression=zipfile.ZIP_DEFLATED):
    names = names or [
        "raw/car_data/session_key=1/driver_number=10/chunk_0000.parquet",
        "raw/location/session_key=1/driver_number=10/chunk_0000.parquet",
    ]
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=compression) as archive:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for idx, name in enumerate(names):
                archive.writestr(name, (f"payload-{idx}" * 20).encode())
    return target.getvalue()


def make_zip64(data):
    eocd_at = data.rfind(b"PK\x05\x06")
    eocd = bytearray(data[eocd_at:])
    fields = struct.unpack_from("<4s4H2IH", eocd)
    entries, cd_size, cd_offset = fields[4], fields[5], fields[6]
    zip64_offset = eocd_at
    zip64_eocd = struct.pack(
        "<4sQ2H2I4Q", b"PK\x06\x06", 44, 45, 45, 0, 0,
        entries, entries, cd_size, cd_offset,
    )
    locator = struct.pack("<4sIQI", b"PK\x06\x07", 0, zip64_offset, 1)
    struct.pack_into("<HHII", eocd, 8, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
    return data[:eocd_at] + zip64_eocd + locator + bytes(eocd)


def index_bytes(data, limits=None):
    def fetch(start, end, _purpose):
        return data[start:end + 1]
    budget = zip_index.RangeBudget(len(data), fetch, limits or zip_index.Limits())
    return zip_index.index_zip(budget), budget


class ZipIndexTests(unittest.TestCase):
    def test_normal_catalog_is_metadata_only_and_deterministic(self):
        result, budget = index_bytes(make_zip())
        self.assertEqual(result["central_directory_entries"], 2)
        self.assertEqual(len(result["catalog"]), 2)
        self.assertTrue(all(x["payload_status"] == zip_index.PAYLOAD_STATUS for x in result["catalog"]))
        self.assertLessEqual(budget.total_bytes, zip_index.MAX_TOTAL_BYTES)
        again, _ = index_bytes(make_zip())
        self.assertEqual(result["catalog_canonical_json_sha256"], again["catalog_canonical_json_sha256"])

    def test_zip64_end_records(self):
        result, _ = index_bytes(make_zip64(make_zip()))
        self.assertTrue(result["zip64"])
        self.assertEqual(len(result["catalog"]), 2)

    def test_duplicate_path_rejected(self):
        path = "raw/car_data/session_key=1/driver_number=10/chunk_0000.parquet"
        with self.assertRaisesRegex(zip_index.Hold, "DUPLICATE_MEMBER_PATH"):
            index_bytes(make_zip([path, path]))

    def test_path_traversal_rejected(self):
        with self.assertRaisesRegex(zip_index.Hold, "UNSAFE_MEMBER_PATH"):
            index_bytes(make_zip(["../raw/car_data/session_key=1/driver_number=10/chunk_0000.parquet"]))

    def test_wrong_compression_method_rejected(self):
        with self.assertRaisesRegex(zip_index.Hold, "UNSUPPORTED_COMPRESSION_METHOD"):
            index_bytes(make_zip(compression=zipfile.ZIP_BZIP2))

    def test_malformed_count_rejected(self):
        data = bytearray(make_zip())
        eocd = data.rfind(b"PK\x05\x06")
        struct.pack_into("<H", data, eocd + 10, 3)
        with self.assertRaises(zip_index.Hold):
            index_bytes(bytes(data))

    def test_malformed_offset_rejected(self):
        data = bytearray(make_zip())
        eocd = data.rfind(b"PK\x05\x06")
        struct.pack_into("<I", data, eocd + 16, len(data) + 100)
        with self.assertRaisesRegex(zip_index.Hold, "INVALID_CENTRAL_DIRECTORY"):
            index_bytes(bytes(data))

    def test_range_budget_rejects_per_request_oversize(self):
        budget = zip_index.RangeBudget(100, lambda s, e, p: b"x" * (e - s + 1), zip_index.Limits(100, 4, 12))
        with self.assertRaisesRegex(zip_index.Hold, "PER_REQUEST_LIMIT"):
            budget.get(0, 4, "oversize")

    def test_range_budget_rejects_aggregate_and_count(self):
        fetch = lambda s, e, p: b"x" * (e - s + 1)
        aggregate = zip_index.RangeBudget(100, fetch, zip_index.Limits(5, 5, 12))
        aggregate.get(0, 4, "first")
        with self.assertRaisesRegex(zip_index.Hold, "AGGREGATE_BYTE_LIMIT"):
            aggregate.get(5, 5, "second")
        count = zip_index.RangeBudget(100, fetch, zip_index.Limits(100, 5, 1))
        count.get(0, 0, "first")
        with self.assertRaisesRegex(zip_index.Hold, "REQUEST_COUNT_LIMIT"):
            count.get(1, 1, "second")

    def test_wrong_digest_rejected(self):
        metadata = {
            "id": 1, "name": "x", "size_in_bytes": 2, "digest": "sha256:wrong",
            "expired": False, "expires_at": "2030-01-01T00:00:00Z",
        }
        expected = {"id": 1, "name": "x", "size_in_bytes": 2, "digest": "sha256:right"}
        with self.assertRaisesRegex(zip_index.Hold, "METADATA_MISMATCH"):
            zip_index.validate_artifact_metadata(metadata, expected, datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_expiration_rejected(self):
        metadata = {
            "id": 1, "name": "x", "size_in_bytes": 2, "digest": "sha256:right",
            "expired": False, "expires_at": "2025-01-01T00:00:00Z",
        }
        expected = {"id": 1, "name": "x", "size_in_bytes": 2, "digest": "sha256:right"}
        with self.assertRaisesRegex(zip_index.Hold, "METADATA_MISMATCH"):
            zip_index.validate_artifact_metadata(metadata, expected, datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_coverage_classifications(self):
        catalog = [
            {"session_key": 1, "driver_number": 10, "endpoint": "car_data", "path": "a"},
            {"session_key": 1, "driver_number": 10, "endpoint": "location", "path": "b"},
            {"session_key": 3, "driver_number": 44, "endpoint": "car_data", "path": "c"},
        ]
        rows = [
            ["event_round", "event_name", "meeting_key", "session_key", "session_name", "session_type", "verified_drivers", "endpoint_combinations", "source_rows", "feature_rows_30s", "telemetry_status", "feature_status", "evidence_pointer", "notes"],
            ["1", "A", "1", "1", "P1", "Practice", "1", "2", "", "", "V", "V", "artifact 11916289450", ""],
            ["2", "B", "2", "2", "P1", "Practice", "1", "2", "", "", "V", "V", "Library checkpoint", ""],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coverage.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(rows)
            result = zip_index.compare_coverage(catalog, path)
        self.assertEqual(result["category_counts"]["OBSERVED_IN_ARCHIVE"], 1)
        self.assertEqual(result["category_counts"]["RETAINED_ELSEWHERE"], 1)
        self.assertEqual(result["category_counts"]["UNABLE_TO_PROVE"], 1)


if __name__ == "__main__":
    unittest.main()
