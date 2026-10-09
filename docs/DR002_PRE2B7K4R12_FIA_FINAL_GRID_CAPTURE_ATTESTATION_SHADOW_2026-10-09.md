# DR-002 pre-2B-7K4R12 — manual FIA final-grid capture and attestation shadow

**Date:** 2026-10-09

**Work order:** `F1-WO-DR002-PRE2B7K4R12-001` / Issue #240

**Status:** IMPLEMENTED, MANUAL-ONLY, NOT DISPATCHED

## Purpose and fixed pilot target

K4R12 adds a bounded future GitHub Actions shadow capability for exact-byte
custody of one fixed historical FIA document. It does not perform a live
capture in this work order.

The only permitted target is:

- FIA 2026 Australian Grand Prix `Final Starting Grid`;
- document number 55, dated 8 March 2026;
- PDF URI: `https://www.fia.com/system/files/decision-document/2026_australian_grand_prix_-_final_starting_grid.pdf`;
- source index: `https://www.fia.com/documents/championships/fia-formula-one-world-championship-14/event/Australian%20Grand%20Prix`;
- caller-claimed index publication time: `2026-03-08T03:00:00Z`, corresponding
  to the supplied index research's `08.03.26 04:00 CET` listing.

The fixed scope uses explicit FIA-local strings and contains no OpenF1 meeting
or session number. This Australian document must never be joined to K4R10's
Baku weather/drivers replay or treated as an inferred OpenF1 event mapping.

The FIA index and PDF details above were supplied by the authorized work order.
No provider research, index crawl or PDF download was repeated here.

## Manual-only workflow and network boundary

`.github/workflows/dr002-fia-final-grid-capture-shadow.yml` has only a
`workflow_dispatch` trigger and a job-level `refs/heads/main` gate before the
capture step. It has only `contents: read`, `id-token: write` and
`attestations: write` permissions. Checkout disables persisted credentials.

At a separately authorized future dispatch, the script can make exactly one
HTTPS GET to the fixed PDF URI. There are no URL, season or event inputs, no
retry, no range request, no cookies, no credentials, no index request and no
third-party mirror. Redirects and final-URL changes fail closed. The response
must be HTTP 200, complete, no larger than 8 MiB, `application/pdf`, consistent
with any declared content length, and acceptable to the unchanged K4R11 PDF
envelope candidate assessment.

`first_observed_utc` is sampled only after the one complete response body has
arrived. It is an actual future runner observation time—not FIA publication
time and not a historical Australian race forecast cutoff. The separately
labelled `shadow_review_cutoff_utc` is the post-event receipt-creation time used
only to exercise K4R11's consistency checks.

## Exact-byte custody and receipt boundary

Each attempt derives one fresh `gha-<run_id>-<attempt>` runtime directory and
uses exclusive writes. Construction occurs in an attempt-specific staging
directory before atomic publication, preventing overwrite of an earlier
attempt. The capture records:

- repository, immutable checkout SHA, workflow ref, run ID and attempt;
- request start and response completion;
- actual first observation, ingestion and receipt-creation times;
- fixed FIA URI, index URI, document number/title/type and claimed publication;
- exact raw PDF byte length, SHA-256 and independent filesystem readback;
- unchanged K4R11 candidate status and deterministic candidate/source/version
  identities;
- one canonical, parentless Gate 2B-1 `source_capture` receipt using the
  existing receipt schema and temporal verifier;
- exact canonical receipt bytes, receipt ID and SHA-256;
- `binding_status=UNBOUND` and all authority, grid, availability, production,
  activation and promotion claims false.

The source receipt's claimed source identity comes from K4R11's canonical PDF
URI identity. Its deterministic receipt identity binds that source ID, the
explicit FIA-local scope, exact raw byte hash and actual first observation. It
does not derive identity from the document number or source-index publication
metadata alone.

On `HOLD`, no successful receipt path, receipt ID or candidate identity is
published. Diagnostic metadata can still be retained by the workflow's
`if: always()` artifact step, without a retry.

## GitHub attestation boundary

Only a successful `source_capture_receipt.json` reaches the single
`actions/attest` step. The action is pinned to the same accepted immutable
release used by the existing capture-provenance pilot. The packaging step
requires exactly one attestation subject named `source_capture_receipt.json`
whose SHA-256 equals the exact canonical receipt file bytes, then preserves the
returned bundle and bounded factual metadata.

This is packaging consistency, not independent Sigstore verification. A future
separately authorized evidence review must verify the bundle through the
accepted verifier boundary before any GitHub provenance binding is projected.
Even successfully verified GitHub provenance would establish only that the
workflow created the receipt bytes no later than a verified transparency-log
time. It would not cryptographically authenticate FIA as PDF author, establish
pre-race availability, prove index completeness or verify grid positions.

The runtime artifact includes the exact raw PDF only for short-lived operator
inspection and attestation audit, with 14-day retention. The bytes are never
committed to Git, `latest/**`, `history/**`, PR text or documentation. Any later
operator must honor FIA copyright and reuse limitations; this capability is not
a public-republication mechanism.

## Offline verification in this work order

Focused tests use injected transport, clock and filesystem seams with small
synthetic bytes explicitly marked `MOCK`. They do not contact FIA or any other
network service. Coverage includes the exact fixed target, single-call
behavior, raw/readback hashes, canonical receipt identity, K4R11 claim ceiling,
post-event timestamp semantics, HTTP/redirect/PDF/size/truncation/content-type
failures, chronology failures, persistence/readback failures, exclusive runtime
directories, attestation gating, workflow permissions/action pinning and the
seven immutable dependency fingerprints.

## Explicit non-effects and future authority

No FIA PDF was downloaded and this workflow was not dispatched. K4R12 does not
parse or OCR a PDF, extract a grid, emit `starting_grid.csv`, create verified
receipt bindings, infer FIA-to-OpenF1 mappings, run a producer/model/stable
engine, replace K4R9's synthetic grid, modify scheduled workflows, or write
`latest/**` or `history/**`.

A real one-shot capture needs a new explicit dispatch authorization. Downloaded
evidence and its GitHub attestation then require independent review before any
later grid extraction, version reconciliation or three-real-source producer
experiment can be considered.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion
**NOT ALLOWED**.
