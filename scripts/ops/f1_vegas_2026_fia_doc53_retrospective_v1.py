#!/usr/bin/env python3
"""One-event original FIA final-grid read, never a retrospective forecast.

This is a fail-closed read-only authority observation, not a producer or a
permission to republish FIA result data. Raw PDF stays in process memory;
the public repository receives no 22-driver table or FIA PDF copy.
The narrow accepted DR-002 candidate boundary remains independently checked
and correctly HOLDS any post-cutoff source as prospective evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.forecast_bundles import dr002_fia_grid_document_candidate_v1 as candidate

INDEX = "https://www.fia.com/documents/championship/event/Las%20Vegas%20Grand%20Prix"
PDF = ("https://www.fia.com/system/files/decision-document/"
       "2026_las_vegas_grand_prix_-_final_starting_grid.pdf")
EVENT = "2026_1300_united_states_las_vegas_las_vegas"
MEETING = "1300"
RACE = "11420"
QUALIFYING = "11416"
PUBLISHED_UTC = "2026-11-22T03:00:00Z"
RACE_START_UTC = "2026-11-22T04:00:00Z"
GRID_DIGEST = "9d6790b907891890cd95c6325f72e012f466fab77b98151b839f0b6c49a741eb"
MAX_PDF_BYTES = 10 * 1024 * 1024


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def utc_iso(value):
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        raise ValueError("FIA_AUTHORITY_HOLD_CLOCK")
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def retrieve(url, max_bytes):
    # Exact HTTPS URL, with no custom or unauthenticated redirect target.
    if url not in {INDEX, PDF}:
        raise ValueError("FIA_AUTHORITY_HOLD_URL_SCOPE")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError("FIA_AUTHORITY_HOLD_REDIRECT")
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers={
        "User-Agent": "F1-Source-Custody-v1 (read-only)",
        "Accept": "text/html" if url == INDEX else "application/pdf",
    })
    with opener.open(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError("FIA_AUTHORITY_HOLD_HTTP_NOT_200")
        raw = response.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("FIA_AUTHORITY_HOLD_ORIGINAL_BYTES_SIZE")
    return raw


def extract_positions_from_pdf(raw):
    # Coordinate-based parsing is deliberately fail-closed. If the actual FIA
    # document layout changes, a new reviewed parser and source hash are needed.
    try:
        import pymupdf
        pdf = pymupdf.open(stream=raw, filetype="pdf")
        if len(pdf) != 2:
            raise ValueError("FIA_AUTHORITY_HOLD_PAGE_COUNT")
        header = " ".join(pdf[0].get_text().split())
        body = " ".join(pdf[1].get_text().split())
        words = pdf[1].get_text("words")
        width = float(pdf[1].rect.width)
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("FIA_AUTHORITY_HOLD_PDF_EXTRACTION") from exc
    # Report a precise bounded reason instead of one opaque combined HOLD;
    # no copyrighted FIA grid text or page content enters diagnostics.
    required_document_fields = (
        ("DOCUMENT_53", re.search(r"Document\s*:?\s*53\b", header, re.I)),
        ("DATE", "21 November 2026" in header),
        ("TITLE", re.search(r"Final\s+Starting\s+Grid", header, re.I)),
        ("EVENT", bool(re.search(r"(?:2026\s+LAS\s+VEGAS\s+GRAND\s+PRIX|LAS\s+VEGAS\s+GRAND\s+PRIX\s+2026)", header + " " + body, re.I))),
        ("GRID_TITLE", "Final Starting Grid" in body),
        ("CAR_87_PERMISSION", "Car 87" in body),
        ("CAR_12_PENALTY", "Car 12" in body),
        ("CAR_87_35_PLACE", re.search(r"35\s*place\s*grid\s*penalt", body, re.I)),
        ("CAR_12_5_PLACE", re.search(r"5\s*place\s*grid\s*penalt", body, re.I)),
    )
    for label, valid in required_document_fields:
        if not valid:
            raise ValueError("FIA_AUTHORITY_HOLD_DOCUMENT_" + label)
    notes = [w for w in words if str(w[4]).lower().startswith("notes")]
    if not notes:
        raise ValueError("FIA_AUTHORITY_HOLD_NOTES_UNAVAILABLE")
    cutoff_y = min(float(w[1]) for w in notes)
    matches = {}
    for x0, y0, x1, y1, token, *_ in words:
        token = str(token).strip()
        if not re.fullmatch(r"(?:[1-9]|1\d|2[0-2])", token):
            continue
        pos = int(token)
        # FIA layout has a 2-column list, with each black grid-position badge
        # left of its separate numeric car number. Do not parse numeric lap times.
        fraction = float(x0) / width
        if not (0.04 <= fraction <= 0.17 or 0.50 <= fraction <= 0.63):
            continue
        if y0 >= cutoff_y:
            continue
        cars = [
            w for w in words if float(w[0]) > float(x1) + 1.0
            and float(w[0]) < float(x1) + 55.0
            and abs(float(w[1]) - float(y0)) < 8.0
            and re.fullmatch(r"[1-9]\d?", str(w[4]).strip())
        ]
        if len(cars) != 1:
            continue
        if pos in matches and matches[pos] != int(cars[0][4]):
            raise ValueError("FIA_AUTHORITY_HOLD_GRID_DUPLICATE")
        matches[pos] = int(cars[0][4])
    if set(matches) != set(range(1, 23)):
        raise ValueError("FIA_AUTHORITY_HOLD_GRID_INCOMPLETE")
    ordered = [matches[n] for n in range(1, 23)]
    if len(set(ordered)) != 22:
        raise ValueError("FIA_AUTHORITY_HOLD_GRID_DUPLICATE_CAR")
    if digest(json.dumps(ordered, separators=(",", ":")).encode()) != GRID_DIGEST:
        raise ValueError("FIA_AUTHORITY_HOLD_GRID_REVISION_MISMATCH")
    return GRID_DIGEST


def observe(*, clock=None, reader=retrieve, parser=extract_positions_from_pdf):
    observed = clock or now_utc()
    status = {
        "schema": "vegas-fia-doc53-original-authority-observation-v1",
        "event_id": EVENT, "meeting_key": MEETING,
        "race_session_key": RACE, "qualifying_session_key": QUALIFYING,
        "source_index": INDEX, "source_document": PDF,
        "document_number": 53, "document_title": "Final Starting Grid",
        "fia_published_utc": PUBLISHED_UTC,
        "first_observed_utc": utc_iso(observed),
        "retrieval_mode": "RETROSPECTIVE_ONLY",
        "original_pdf_sha256": None, "observed_grid_digest": None,
        "forecast_eligible": False, "stable_engine_executed": False,
        "prediction_locked": False, "promotion_allowed": False,
        "source_authority_verified": False,
        "status": "FIA_AUTHORITY_HOLD",
        "reason_codes": [],
    }
    try:
        if observed <= dt.datetime.fromisoformat(RACE_START_UTC.replace("Z", "+00:00")):
            raise ValueError("FIA_AUTHORITY_HOLD_NOT_RETROSPECTIVE")
        index = reader(INDEX, 2*1024*1024)
        text = html.unescape(re.sub(r"<[^>]+>", " ", index.decode("utf-8")))
        if ("Doc 53 - Final Starting Grid" not in " ".join(text.split())
                or "Las Vegas Grand Prix" not in text):
            raise ValueError("FIA_AUTHORITY_HOLD_OFFICIAL_INDEX_MISMATCH")
        original = reader(PDF, MAX_PDF_BYTES)
        if not original.startswith(b"%PDF-"):
            raise ValueError("FIA_AUTHORITY_HOLD_NOT_A_PDF")
        grid = parser(original)
        if grid != GRID_DIGEST:
            raise ValueError("FIA_AUTHORITY_HOLD_GRID_REVISION_MISMATCH")
        candidate_result = candidate.assess_fia_grid_document_candidate(
            raw_document_bytes=original,
            document_type="final_starting_grid", document_number=53,
            document_title="Final Starting Grid",
            document_uri=PDF, official_index_uri=INDEX,
            event_id=EVENT, meeting_id=MEETING, session_id=RACE,
            published_utc=PUBLISHED_UTC,
            first_observed_utc=utc_iso(observed),
            ingested_utc=utc_iso(observed),
            receipt_created_utc=utc_iso(observed),
            forecast_cutoff_utc=RACE_START_UTC)
        # The accepted DR-002 prospective candidate MUST reject post-cutoff
        # observation. A matching PDF/document is NOT an observed pre-race grid.
        if (candidate_result.get("status") != "HOLD"
                or "first_observed_after_forecast_cutoff" not in
                candidate_result.get("reason_codes", [])):
            raise ValueError("FIA_AUTHORITY_HOLD_PRE_CUTOFF_BOUNDARY")
        status.update(source_authority_verified=True,
                      status="FIA_FINAL_GRID_VERIFIED_RETROSPECTIVE_ONLY",
                      original_pdf_sha256=digest(original),
                      original_pdf_size_bytes=len(original),
                      official_index_sha256=digest(index),
                      observed_grid_digest=grid,
                      reason_codes=["OBSERVED_AFTER_RACE_START",
                                    "NO_PROSPECTIVE_SOURCE_AUTHORITY"])
    except Exception as exc:
        # Preserve only a known category; arbitrary network failures can leak
        # URLs/tokens and should never be reproduced verbatim.
        reason = str(exc) if isinstance(exc, ValueError) and str(exc).startswith(
            "FIA_AUTHORITY_HOLD_") else "FIA_AUTHORITY_HOLD_ORIGINAL_SOURCE_UNAVAILABLE"
        status["reason_codes"] = [reason]
    return status


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    opts = parser.parse_args(argv)
    result = observe()
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["source_authority_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
