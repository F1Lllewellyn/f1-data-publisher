# DR-002 pre-2B-7K4R11 — offline FIA grid-document candidate contract

**Date:** 2026-10-09

**Work order:** `F1-WO-DR002-PRE2B7K4R11-001` / Issue #237

**Status:** PURE OFFLINE CANDIDATE CONTRACT ONLY

## Purpose and source boundary

FIA event decision-document indexes can list `Provisional Starting Grid` and
`Final Starting Grid` as separately numbered and separately published official
document categories. The supplied research identified the FIA 2026 championship
decision-document index and an Australian Grand Prix example where document 49
was provisional and document 55 was final. K4R11 does not repeat that research,
contact those pages, or download either PDF.

This change creates the smallest fail-closed contract for assessing an exact
caller-supplied raw PDF byte object together with caller-claimed FIA URI,
publication, observation, ingestion, receipt-creation, cutoff, document and
scope metadata. A successful result is deliberately named:

`FIA_GRID_DOCUMENT_CANDIDATE_METADATA_VALIDATED_UNAUTHENTICATED`

That status means only that the supplied values satisfy this contract's
offline syntax, identity, chronology and cutoff checks. It does not prove that
the bytes were retrieved from FIA, that FIA authored them, that their internal
content is correct, or that they were historically available at the claimed
time.

## Accepted pinned context

Implementation began only after the six work-order dependency blobs matched on
the observed `main` baseline:

| Dependency | Required Git blob |
|---|---|
| K4R10 checkpoint | `b9d57a68ac7eef39e71a6a19ca9de407a68fb09d` |
| K4R9 composition | `f69a5ac49b6e3055cd13472037f8b49e8ea41265` |
| Gate 2B-1 verifier | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` |
| Gate 2B-4 contract | `064d93ee5ae30354590a3fb95be598c5fe8b3b9a` |
| Current real producer | `af27586668c767de126af829c1131c6bae4634ad` |
| Handoff contract | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

No dependency is modified.

## Candidate input and validation

`assess_fia_grid_document_candidate(...)` is keyword-only and requires every
input explicitly. It accepts only the two document categories below:

- `provisional_starting_grid` with title `Provisional Starting Grid`;
- `final_starting_grid` with title `Final Starting Grid`.

Title comparison normalizes case and whitespace only. Qualifying
classifications, Sprint grids, practice classifications, race results, OpenF1
driver records and metadata-only substitutes do not qualify.

The document number must be a positive integer and not a Boolean. Event,
meeting and session identifiers must be exact nonempty caller-supplied strings.
They remain claimed FIA document scope: the contract does not infer or create
an FIA-to-OpenF1 event, meeting or session mapping merely because identifiers
appear similar. If both supplied URLs explicitly contain an `/event/...` route,
their event names must agree; otherwise the candidate is held.

The raw object must be exact nonempty `bytes`, no larger than 32 MiB, begin
with `%PDF-`, and end plausibly with a PDF `%%EOF` marker. These are envelope
checks, not PDF parsing or content verification. No OCR, text extraction,
driver row extraction or PDF library is used.

Both caller-supplied URLs must already be canonical strict HTTPS URLs on one of
`fia.com`, `www.fia.com`, `api.fia.com` or `admin.fia.com`. User information,
ports, queries, fragments, look-alike hosts, HTTP, ambiguous escaping, path
traversal and malformed URLs are rejected. The document URL must have a `.pdf`
path; the distinct index URL must use the `/documents` route. Percent-encoded
path text such as `%20` is accepted only in its canonical form. The contract
does not connect to the URL and therefore does not follow or bless redirects.

## Temporal boundary

All five timestamps must be strict UTC ISO 8601 values ending in `Z`:

1. `published_utc` — claimed FIA publisher metadata;
2. `first_observed_utc` — claimed first observation of the exact bytes;
3. `ingested_utc` — claimed ingestion time;
4. `receipt_created_utc` — claimed candidate-record creation time;
5. `forecast_cutoff_utc` — the cutoff against which the claim is assessed.

The first four must satisfy:

`published <= first_observed <= ingested <= receipt_created`

Both publication and first observation must be at or before the forecast
cutoff. A post-cutoff publication or first observation returns a complete
`HOLD`, with no candidate identity or usable source/row output. Passing these
comparisons does not transform publisher metadata into proof of historical
availability. In particular, a pre-cutoff `published_utc` combined with a
post-cutoff `first_observed_utc` is a `HOLD`.

## Deterministic identity and same-URI revisions

For a validated candidate, the contract deterministically derives separate,
domain-separated values:

- raw-document SHA-256 from the exact caller-supplied bytes;
- claimed source identity from the canonical PDF URI bytes;
- content-version identity from the canonical PDF URI plus raw-content hash;
- candidate identity from document type, positive document number, exact
  supplied title, both URIs, all three scope identifiers, all five timestamps,
  claimed source identity and content-version identity.

The URI identity and content-version identity are intentionally different. If
the bytes behind one URI change, the claimed source identity remains the same
but the content version and candidate identity change. A document number alone
can never define or collapse source, version or candidate identity.

## Fail-closed output and proof ceiling

Invalid input returns deterministic `HOLD` reason codes, all claim flags false,
and no raw bytes, parsed rows, CSV, source receipt, verified binding or document
identity. Missing required keywords remain programming errors rather than being
masked as successful `HOLD` results.

Even a validated candidate keeps every material claim false:

- official source authenticated;
- official starting grid verified;
- grid positions extracted;
- source captured by an attested observer;
- historical availability verified;
- verified receipt bindings created;
- production authenticated;
- blind validation eligible;
- DR-002 activated;
- promotion allowed.

The full Gate 2B-1 evidence chain remains `NOT_ESTABLISHED`. This module does
not create a `source_capture` receipt and does not claim a verified binding.

## Explicit non-effects

K4R11 does not parse an original FIA PDF, emit `starting_grid.csv`, or replace
K4R9's synthetic starting grid. It performs no HTTP, source discovery,
credential access, workflow dispatch, filesystem write, producer invocation,
stable-engine invocation, model execution, or mutation of `latest/**` or
`history/**`.

Future independently authorized stages may establish actual FIA source custody
through an approved observer and raw-byte attestation; extract and reconcile
positions including pit-lane starts, vacancies and withdrawals; select explicit
versions under cutoff-aware provenance; and only then attempt a contained
three-real-source producer replay. None of those future stages is implemented
here.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion
**NOT ALLOWED**.
