#!/usr/bin/env python3
"""Bounded metadata-only inventory of a retained GitHub Actions ZIP artifact.

This deliberately reads only the ZIP tail and central directory.  It never
decompresses members and never treats a directory CRC32 as payload proof.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import os
import re
import struct
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable


MAX_TOTAL_BYTES = 12 * 1024 * 1024
MAX_RANGE_BYTES = 4 * 1024 * 1024
MAX_RANGE_REQUESTS = 12
MAX_CENTRAL_ENTRIES = 200_000
TAIL_BYTES = 128 * 1024
PAYLOAD_STATUS = "METADATA_ONLY_UNVERIFIED_PAYLOAD"
CANONICAL_RE = re.compile(
    r"^raw/(?P<endpoint>car_data|location)/"
    r"session_key=(?P<session>\d+)/driver_number=(?P<driver>\d+)/"
    r"(?P<member>[^/]+\.parquet)$"
)


class Hold(RuntimeError):
    """Fail-closed classification for an invalid or unprovable input."""


@dataclass(frozen=True)
class Limits:
    aggregate_bytes: int = MAX_TOTAL_BYTES
    per_request_bytes: int = MAX_RANGE_BYTES
    requests: int = MAX_RANGE_REQUESTS


class RangeBudget:
    def __init__(self, archive_size: int, fetch: Callable[[int, int, str], bytes], limits: Limits = Limits()):
        if archive_size <= 0:
            raise Hold("HOLD_INVALID_ARCHIVE_SIZE")
        self.archive_size = archive_size
        self.fetch = fetch
        self.limits = limits
        self.total_bytes = 0
        self.records: list[dict] = []

    def get(self, start: int, end: int, purpose: str) -> bytes:
        if start < 0 or end < start or end >= self.archive_size:
            raise Hold(f"HOLD_INVALID_RANGE:{purpose}")
        length = end - start + 1
        if length > self.limits.per_request_bytes:
            raise Hold(f"HOLD_PER_REQUEST_LIMIT:{purpose}")
        if len(self.records) >= self.limits.requests:
            raise Hold("HOLD_REQUEST_COUNT_LIMIT")
        if self.total_bytes + length > self.limits.aggregate_bytes:
            raise Hold("HOLD_AGGREGATE_BYTE_LIMIT")
        started = time.monotonic()
        body = self.fetch(start, end, purpose)
        elapsed = time.monotonic() - started
        if len(body) != length:
            raise Hold(f"HOLD_RANGE_BODY_SIZE:{purpose}")
        self.total_bytes += len(body)
        self.records.append(
            {
                "purpose": purpose,
                "start": start,
                "end": end,
                "response_body_bytes": len(body),
                "elapsed_seconds": round(elapsed, 6),
            }
        )
        return body

    def span(self, start: int, length: int, purpose: str) -> bytes:
        if length < 0 or start < 0 or start + length > self.archive_size:
            raise Hold(f"HOLD_INVALID_SPAN:{purpose}")
        chunks = []
        offset = 0
        while offset < length:
            size = min(self.limits.per_request_bytes, length - offset)
            chunks.append(self.get(start + offset, start + offset + size - 1, f"{purpose}_{len(chunks)+1}"))
            offset += size
        return b"".join(chunks)


class AzureRangeFetcher:
    def __init__(self, signed_url: str, archive_size: int):
        parsed = urllib.parse.urlsplit(signed_url)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".blob.core.windows.net"):
            raise Hold("HOLD_UNEXPECTED_SIGNED_URL_ORIGIN")
        self.parsed = parsed
        self.archive_size = archive_size

    def __call__(self, start: int, end: int, purpose: str) -> bytes:
        expected = end - start + 1
        conn = http.client.HTTPSConnection(self.parsed.hostname, self.parsed.port or 443, timeout=45)
        target = self.parsed.path + (("?" + self.parsed.query) if self.parsed.query else "")
        conn.request("GET", target, headers={"Range": f"bytes={start}-{end}", "User-Agent": "f1-bounded-zip-index-v1"})
        response = conn.getresponse()
        status = response.status
        content_range = response.getheader("Content-Range")
        content_length = response.getheader("Content-Length")
        if status == 200:
            conn.close()
            raise Hold(f"HOLD_UNEXPECTED_FULL_BODY:{purpose}")
        if status != 206:
            conn.close()
            raise Hold(f"HOLD_RANGE_HTTP_{status}:{purpose}")
        if content_range != f"bytes {start}-{end}/{self.archive_size}":
            conn.close()
            raise Hold(f"HOLD_CONTENT_RANGE:{purpose}")
        if content_length is None or int(content_length) != expected:
            conn.close()
            raise Hold(f"HOLD_CONTENT_LENGTH:{purpose}")
        body = response.read(expected + 1)
        conn.close()
        return body


def _api_get(repository: str, token: str, path: str) -> tuple[int, bytes, str | None]:
    conn = http.client.HTTPSConnection("api.github.com", timeout=30)
    conn.request(
        "GET",
        path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "f1-bounded-zip-index-v1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    response = conn.getresponse()
    body = response.read(1024 * 1024 + 1)
    status = response.status
    location = response.getheader("Location")
    conn.close()
    return status, body, location


def validate_artifact_metadata(metadata: dict, expected: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    checks = {
        "id": metadata.get("id") == expected["id"],
        "name": metadata.get("name") == expected["name"],
        "size": metadata.get("size_in_bytes") == expected["size_in_bytes"],
        "digest": metadata.get("digest") == expected["digest"],
        "unexpired_flag": metadata.get("expired") is False,
    }
    expires_at = metadata.get("expires_at")
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00")) if expires_at else None
    except (TypeError, ValueError) as exc:
        raise Hold("HOLD_ARTIFACT_EXPIRY_INVALID") from exc
    checks["unexpired_time"] = expiry is not None and expiry > now
    if not all(checks.values()):
        raise Hold("HOLD_ARTIFACT_METADATA_MISMATCH:" + json.dumps(checks, sort_keys=True))
    return {"checks": checks, "expires_at": expires_at}


def _zip64_values(extra: bytes, needs: tuple[bool, bool, bool]) -> tuple[int | None, int | None, int | None]:
    pos = 0
    payload = None
    while pos < len(extra):
        if pos + 4 > len(extra):
            raise Hold("HOLD_MALFORMED_EXTRA_HEADER")
        kind, size = struct.unpack_from("<HH", extra, pos)
        pos += 4
        if pos + size > len(extra):
            raise Hold("HOLD_MALFORMED_EXTRA_LENGTH")
        if kind == 0x0001:
            if payload is not None:
                raise Hold("HOLD_DUPLICATE_ZIP64_EXTRA")
            payload = extra[pos : pos + size]
        pos += size
    if not any(needs):
        return None, None, None
    if payload is None:
        raise Hold("HOLD_ZIP64_EXTRA_MISSING")
    cursor = 0
    values: list[int | None] = []
    for needed in needs:
        if not needed:
            values.append(None)
            continue
        if cursor + 8 > len(payload):
            raise Hold("HOLD_ZIP64_EXTRA_TRUNCATED")
        values.append(struct.unpack_from("<Q", payload, cursor)[0])
        cursor += 8
    return values[0], values[1], values[2]


def _safe_name(name: str) -> None:
    parts = PurePosixPath(name).parts
    if not name or name.startswith("/") or "\\" in name or "\x00" in name or ".." in parts or "." in parts:
        raise Hold("HOLD_UNSAFE_MEMBER_PATH")


def parse_central_directory(central: bytes, total_entries: int, cd_offset: int) -> list[dict]:
    if total_entries <= 0 or total_entries > MAX_CENTRAL_ENTRIES:
        raise Hold("HOLD_CENTRAL_ENTRY_COUNT_LIMIT")
    entries = []
    names: set[str] = set()
    pos = 0
    while pos < len(central):
        if len(entries) >= total_entries or pos + 46 > len(central) or central[pos : pos + 4] != b"PK\x01\x02":
            raise Hold("HOLD_MALFORMED_CENTRAL_DIRECTORY")
        h = struct.unpack_from("<4s6H3I5H2I", central, pos)
        flags, method, crc32, comp, uncomp = h[3], h[4], h[7], h[8], h[9]
        name_len, extra_len, comment_len, disk_start, local_offset = h[10], h[11], h[12], h[13], h[16]
        end = pos + 46 + name_len + extra_len + comment_len
        if name_len <= 0 or name_len > 4096 or end > len(central):
            raise Hold("HOLD_CENTRAL_ENTRY_BOUNDS")
        raw_name = central[pos + 46 : pos + 46 + name_len]
        extra = central[pos + 46 + name_len : pos + 46 + name_len + extra_len]
        try:
            name = raw_name.decode("utf-8" if flags & 0x800 else "cp437")
        except UnicodeDecodeError as exc:
            raise Hold("HOLD_MEMBER_NAME_DECODE") from exc
        _safe_name(name)
        if name in names:
            raise Hold("HOLD_DUPLICATE_MEMBER_PATH")
        names.add(name)
        zu, zc, zo = _zip64_values(extra, (uncomp == 0xFFFFFFFF, comp == 0xFFFFFFFF, local_offset == 0xFFFFFFFF))
        uncomp = zu if zu is not None else uncomp
        comp = zc if zc is not None else comp
        local_offset = zo if zo is not None else local_offset
        if disk_start not in (0, 0xFFFF):
            raise Hold("HOLD_UNSUPPORTED_ENTRY_DISK")
        if flags & 0x1:
            raise Hold("HOLD_ENCRYPTED_MEMBER")
        if method not in (0, 8):
            raise Hold("HOLD_UNSUPPORTED_COMPRESSION_METHOD")
        if local_offset < 0 or local_offset >= cd_offset or comp < 0 or uncomp < 0:
            raise Hold("HOLD_MEMBER_BOUNDS")
        match = CANONICAL_RE.fullmatch(name)
        entries.append(
            {
                "path": name,
                "flags": flags,
                "compression_method": method,
                "declared_crc32": f"{crc32:08x}",
                "compressed_size": comp,
                "uncompressed_size": uncomp,
                "archive_offset": local_offset,
                "central_name_bytes": name_len,
                "is_target_telemetry": bool(match),
                "endpoint": match.group("endpoint") if match else None,
                "session_key": int(match.group("session")) if match else None,
                "driver_number": int(match.group("driver")) if match else None,
                "payload_status": PAYLOAD_STATUS,
            }
        )
        pos = end
    if pos != len(central) or len(entries) != total_entries:
        raise Hold("HOLD_CENTRAL_DIRECTORY_COUNT_MISMATCH")

    ordered = sorted(entries, key=lambda item: item["archive_offset"])
    for idx, entry in enumerate(ordered):
        next_offset = ordered[idx + 1]["archive_offset"] if idx + 1 < len(ordered) else cd_offset
        minimum_end = entry["archive_offset"] + 30 + entry["central_name_bytes"] + entry["compressed_size"]
        if next_offset <= entry["archive_offset"] or minimum_end > next_offset:
            raise Hold("HOLD_OVERLAPPING_OR_IMPOSSIBLE_MEMBER_SPAN")
    return entries


def index_zip(reader: RangeBudget) -> dict:
    archive_size = reader.archive_size
    tail_size = min(TAIL_BYTES, archive_size)
    tail_start = archive_size - tail_size
    tail = reader.get(tail_start, archive_size - 1, "zip_tail")
    eocd_rel = tail.rfind(b"PK\x05\x06")
    if eocd_rel < 0 or eocd_rel + 22 > len(tail):
        raise Hold("HOLD_ZIP_EOCD_NOT_FOUND")
    eocd_abs = tail_start + eocd_rel
    eocd = struct.unpack_from("<4s4H2IH", tail, eocd_rel)
    disk, cd_disk, disk_entries, total_entries, cd_size, cd_offset, comment_len = eocd[1:]
    if eocd_abs + 22 + comment_len != archive_size:
        raise Hold("HOLD_ZIP_EOCD_BOUNDARY")
    if disk != 0 or cd_disk != 0 or disk_entries != total_entries:
        raise Hold("HOLD_UNSUPPORTED_MULTIDISK_ZIP")

    zip64 = total_entries == 0xFFFF or cd_size == 0xFFFFFFFF or cd_offset == 0xFFFFFFFF
    if zip64:
        locator_abs = eocd_abs - 20
        locator = (
            tail[locator_abs - tail_start : locator_abs - tail_start + 20]
            if locator_abs >= tail_start
            else reader.span(locator_abs, 20, "zip64_locator")
        )
        if len(locator) != 20 or locator[:4] != b"PK\x06\x07":
            raise Hold("HOLD_ZIP64_LOCATOR_MISSING")
        _, zip64_disk, zip64_offset, total_disks = struct.unpack("<4sIQI", locator)
        if zip64_disk != 0 or total_disks != 1 or zip64_offset + 56 > archive_size:
            raise Hold("HOLD_ZIP64_LAYOUT")
        zip64_eocd = (
            tail[zip64_offset - tail_start : zip64_offset - tail_start + 56]
            if tail_start <= zip64_offset and zip64_offset + 56 <= archive_size
            else reader.span(zip64_offset, 56, "zip64_eocd")
        )
        if len(zip64_eocd) != 56 or zip64_eocd[:4] != b"PK\x06\x06":
            raise Hold("HOLD_ZIP64_EOCD_MISSING")
        z = struct.unpack("<4sQ2H2I4Q", zip64_eocd)
        if z[1] < 44 or z[4] != 0 or z[5] != 0 or z[6] != z[7]:
            raise Hold("HOLD_ZIP64_LAYOUT")
        total_entries, cd_size, cd_offset = z[7], z[8], z[9]

    if total_entries <= 0 or cd_size <= 0 or cd_offset < 0 or cd_offset + cd_size > eocd_abs:
        raise Hold("HOLD_INVALID_CENTRAL_DIRECTORY")
    if cd_size > reader.limits.aggregate_bytes - reader.total_bytes:
        raise Hold("HOLD_CENTRAL_DIRECTORY_TRANSFER_LIMIT")
    central = (
        tail[cd_offset - tail_start : cd_offset - tail_start + cd_size]
        if tail_start <= cd_offset and cd_offset + cd_size <= archive_size
        else reader.span(cd_offset, cd_size, "central_directory")
    )
    entries = parse_central_directory(central, total_entries, cd_offset)
    catalog = [
        {k: entry[k] for k in ("session_key", "driver_number", "endpoint", "path", "archive_offset", "compressed_size", "uncompressed_size", "declared_crc32", "payload_status")}
        for entry in entries
        if entry["is_target_telemetry"]
    ]
    catalog.sort(key=lambda x: (x["session_key"], x["driver_number"], x["endpoint"], x["path"]))
    if not catalog:
        raise Hold("HOLD_NO_CANONICAL_TELEMETRY_MEMBERS")
    canonical = (json.dumps(catalog, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return {
        "zip64": zip64,
        "central_directory_offset": cd_offset,
        "central_directory_size": cd_size,
        "central_directory_entries": total_entries,
        "all_member_count": len(entries),
        "catalog": catalog,
        "catalog_canonical_json_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def compare_coverage(catalog: list[dict], csv_path: Path) -> dict:
    by_session: dict[int, list[dict]] = {}
    for item in catalog:
        by_session.setdefault(item["session_key"], []).append(item)
    comparisons = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"session_key", "verified_drivers", "endpoint_combinations", "evidence_pointer", "event_name", "session_name"}
    if not rows or not required.issubset(rows[0]):
        raise Hold("HOLD_COVERAGE_CSV_SCHEMA")
    csv_sessions: set[int] = set()
    for row in rows:
        try:
            session = int(row["session_key"])
            expected_drivers = int(row["verified_drivers"])
            expected_combinations = int(row["endpoint_combinations"])
        except (TypeError, ValueError) as exc:
            raise Hold("HOLD_COVERAGE_CSV_VALUE") from exc
        if session in csv_sessions:
            raise Hold("HOLD_COVERAGE_CSV_DUPLICATE_SESSION")
        csv_sessions.add(session)
        members = by_session.get(session, [])
        drivers = {m["driver_number"] for m in members}
        combinations = {(m["endpoint"], m["driver_number"]) for m in members}
        duplicate_chunks = len(members) != len(combinations)
        elsewhere = "artifact 11916289450" not in row["evidence_pointer"]
        if elsewhere:
            classification = "RETAINED_ELSEWHERE"
        elif not members:
            classification = "MISSING_OR_AMBIGUOUS"
        elif duplicate_chunks or len(drivers) != expected_drivers or len(combinations) != expected_combinations:
            classification = "MISSING_OR_AMBIGUOUS"
        else:
            classification = "OBSERVED_IN_ARCHIVE"
        comparisons.append(
            {
                "session_key": session,
                "event_name": row["event_name"],
                "session_name": row["session_name"],
                "classification": classification,
                "archive_member_count": len(members),
                "archive_distinct_drivers": len(drivers),
                "archive_endpoint_driver_combinations": len(combinations),
                "expected_drivers": expected_drivers,
                "expected_endpoint_combinations": expected_combinations,
                "metadata_duplicate_chunks_or_ambiguity": duplicate_chunks,
            }
        )
    for session in sorted(set(by_session) - csv_sessions):
        members = by_session[session]
        comparisons.append(
            {
                "session_key": session,
                "event_name": None,
                "session_name": None,
                "classification": "UNABLE_TO_PROVE",
                "archive_member_count": len(members),
                "archive_distinct_drivers": len({m["driver_number"] for m in members}),
                "archive_endpoint_driver_combinations": len({(m["endpoint"], m["driver_number"]) for m in members}),
                "expected_drivers": None,
                "expected_endpoint_combinations": None,
                "metadata_duplicate_chunks_or_ambiguity": len(members) != len({(m["endpoint"], m["driver_number"]) for m in members}),
            }
        )
    counts = {key: 0 for key in ("OBSERVED_IN_ARCHIVE", "RETAINED_ELSEWHERE", "MISSING_OR_AMBIGUOUS", "UNABLE_TO_PROVE")}
    for item in comparisons:
        counts[item["classification"]] += 1
    return {"summary_rows": len(rows), "category_counts": counts, "sessions": sorted(comparisons, key=lambda x: x["session_key"])}


def run(args: argparse.Namespace) -> dict:
    token = args.token or os.environ.get("GH_TOKEN")
    if not token:
        raise Hold("HOLD_MISSING_GITHUB_TOKEN")
    expected = {"id": args.artifact_id, "name": args.artifact_name, "size_in_bytes": args.archive_size, "digest": args.archive_digest}
    status, body, _ = _api_get(args.repository, token, f"/repos/{args.repository}/actions/artifacts/{args.artifact_id}")
    if status != 200 or len(body) > 1024 * 1024:
        raise Hold(f"HOLD_ARTIFACT_METADATA_HTTP_{status}")
    try:
        metadata = json.loads(body)
    except json.JSONDecodeError as exc:
        raise Hold("HOLD_ARTIFACT_METADATA_JSON") from exc
    metadata_result = validate_artifact_metadata(metadata, expected)

    status, body, signed_url = _api_get(args.repository, token, f"/repos/{args.repository}/actions/artifacts/{args.artifact_id}/zip")
    if status != 302 or body or not signed_url:
        raise Hold(f"HOLD_ARTIFACT_REDIRECT_HTTP_{status}")
    budget = RangeBudget(args.archive_size, AzureRangeFetcher(signed_url, args.archive_size))
    started = time.monotonic()
    index = index_zip(budget)
    comparison = compare_coverage(index["catalog"], args.coverage_csv)
    elapsed = time.monotonic() - started
    endpoints = {item["endpoint"] for item in index["catalog"]}
    if endpoints != {"car_data", "location"}:
        raise Hold("HOLD_ENDPOINT_SET_MISMATCH")
    total_compressed = sum(item["compressed_size"] for item in index["catalog"])
    total_uncompressed = sum(item["uncompressed_size"] for item in index["catalog"])
    coverage_bytes = args.coverage_csv.read_bytes()
    report = {
        "outcome": "PASS_METADATA_ONLY_CENTRAL_DIRECTORY_INDEX",
        "work_order_id": "F1-WO-HF-ZIP-INDEX-20261024-001",
        "run": {"id": os.environ.get("GITHUB_RUN_ID"), "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"), "head_sha": os.environ.get("GITHUB_SHA"), "ref": os.environ.get("GITHUB_REF")},
        "source_artifact": {
            "id": args.artifact_id,
            "name": args.artifact_name,
            "size_in_bytes": args.archive_size,
            "digest": args.archive_digest,
            "expires_at": metadata_result["expires_at"],
            "metadata_checks": metadata_result["checks"],
        },
        "accepted_predecessor": {"run_id": 39937882699, "attempt": 1, "head_sha": "4780ed3b552954f911a27c0ca0f89e0fef9d90be", "workflow_blob": "a64745a967ecc7c7a551e44731acfe24268b5459", "classification": "PASS_RANGE_MEMBER_RETRIEVAL_LIMITED_PROVENANCE"},
        "comparison_source": {"pr": 312, "head_sha": "317201cd7bca8914861c9beee4af13a1aba008f7", "git_blob_sha1": args.coverage_blob, "file_sha256": hashlib.sha256(coverage_bytes).hexdigest()},
        "transfer": {
            "archive_range_request_count": len(budget.records),
            "archive_response_body_bytes": budget.total_bytes,
            "limits": {"aggregate_bytes": budget.limits.aggregate_bytes, "per_request_bytes": budget.limits.per_request_bytes, "requests": budget.limits.requests},
            "ranges": budget.records,
            "full_archive_download": False,
            "member_decompression": False,
            "elapsed_seconds": round(elapsed, 6),
            "total_network_traffic": "not measured; archive response-body bytes are measured separately",
        },
        "index": {k: v for k, v in index.items() if k != "catalog"},
        "indexing_coverage": {
            "catalog_members": len(index["catalog"]),
            "unique_sessions": len({x["session_key"] for x in index["catalog"]}),
            "unique_drivers": len({x["driver_number"] for x in index["catalog"]}),
            "endpoint_driver_combinations": len({(x["session_key"], x["endpoint"], x["driver_number"]) for x in index["catalog"]}),
            "endpoints": sorted(endpoints),
        },
        "comparison": comparison,
        "catalog": index["catalog"],
        "next_true_data_verification_estimate": {
            "declared_compressed_payload_bytes": total_compressed,
            "declared_uncompressed_payload_bytes": total_uncompressed,
            "minimum_4MiB_payload_chunks_if_perfectly_coalesced": (total_compressed + MAX_RANGE_BYTES - 1) // MAX_RANGE_BYTES,
            "note": "True payload verification requires reading and hashing payload bytes plus local headers; this metadata-only proof does not authorize or perform that work and cost would approach the retained archive scale.",
        },
        "limitations": [
            "ZIP central-directory CRC32 and sizes are archive assertions, not independent payload verification.",
            "Every unextracted catalog member is METADATA_ONLY_UNVERIFIED_PAYLOAD; no member SHA256 or row count is claimed.",
            "The source artifact expires; this proof creates no durable storage or recovery architecture.",
            "No production incremental skip, weekly workflow modification, prediction, promotion, or stable-engine change is authorized.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    args.output.write_bytes(rendered)
    return {"report": report, "report_file_sha256": hashlib.sha256(rendered).hexdigest(), "output": str(args.output)}


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default="F1Lllewellyn/f1-data-publisher")
    parser.add_argument("--artifact-id", type=int, default=11916289450)
    parser.add_argument("--artifact-name", default="openf1-full-historical-auto-final-2026-19")
    parser.add_argument("--archive-size", type=int, default=603154203)
    parser.add_argument("--archive-digest", default="sha256:4ca78ad6fbd1af8626429ef50166929c830f2a157520a92df7b92a182462c7dd")
    parser.add_argument("--coverage-csv", type=Path, required=True)
    parser.add_argument("--coverage-blob", default="ea6a24d20a708e6e10f157af44c5e628c6703100")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    try:
        result = run(parse_args(argv))
    except Hold as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("WORK_RESULT_BEGIN")
    print(json.dumps({k: v for k, v in result.items() if k != "report"}, indent=2, sort_keys=True))
    print("WORK_RESULT_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
