# DR-002 pre-2B-7K4R19 OpenF1 shadow non-200 diagnostics

**Status:** offline diagnostic hardening only

**DR-002:** PROPOSED — NOT ACTIVATED

**Forecast gate:** OFF

**Promotion:** NOT ALLOWED

## Original K4R18 evidence

The one authorized Baku attempt was GitHub Actions run `38044379416`, attempt 1,
job `114190831555`, at head `c603e3328ad7b80437369c233acdd7f5fa7a922f`.
It reached terminal `FAILURE` at the initial exact OpenF1
`sessions?year=2026` request, before any starting-grid request. The recorded
failure reason was `session_discovery_http_status_not_200` at
`2026-10-10T10:18:34.1292151Z`.

The original diagnostic artifact was GitHub artifact `11667406581`, named
`dr002-pre2b7k4r15-openf1-starting-grid-historical-shadow`, with ZIP SHA-256
`def5a9673719b42465a0e856545d0943fdfc389d85137efefb22e3bd71b67340`.
Independent inspection found exactly three diagnostic files and no accepted
sessions response, starting-grid response, source receipt, producer output or
model execution.

The original implementation did not preserve the numeric HTTP status. The
actual K4R18 status code is therefore **unknown**. A separate earlier request
that received HTTP 429 does not establish the status of the K4R18 request.

## Interpretation boundary

OpenF1 maintainer guidance says public historical queries may be restricted
during live F1 sessions:
<https://github.com/br-g/openf1/discussions/328>. K4R18 occurred during a live
race-weekend access-risk window. That timing is a plausible hypothesis only;
it is not evidence that the response was 429, 403, or caused by any particular
provider policy. An HTTP status identifies the response class, not the access
reason.

Generic GitHub Actions success or failure is not proof of source availability,
source identity, temporal eligibility, or scientific validity.

## K4R19 diagnostic refinement

For the explicit manual `starting_grid` provenance shadow only, the runtime
manifest now records:

- whether session discovery was attempted and its bounded numeric HTTP status;
- whether the starting-grid request was attempted and, if reached, its bounded
  numeric HTTP status; and
- `null` plus a fail-closed `status_unavailable` reason when a response exposes
  no real integer status in the HTTP range 100–599.

The diagnostic fields are additive. They do not alter the exact one-discovery,
at-most-one-grid request boundary, the no-retry rule, request URI, timeout,
redirect/final-URL/JSON/8-MiB gates, accepted raw bytes, source-receipt identity,
frozen evidence, first-observed chronology, derived CSV identity, or trust
ceilings. Error bodies and unallowlisted headers are not persisted. No retry is
scheduled or performed from `Retry-After`.

HOLD artifacts report only evidence actually accepted. A discovery non-200
retains the original three diagnostic members and explicitly states that no raw
session-discovery data or source-to-Race link was accepted. A later grid
non-200 may retain accepted discovery evidence, but it creates no grid raw
capture, source receipt, or derived CSV.

## Execution limits

K4R19 performs mock/offline verification only. It makes no live OpenF1 or FIA
request, dispatches no workflow, retries no Baku capture, runs no producer or
model, changes no stable engine, and makes no availability or accuracy claim.
