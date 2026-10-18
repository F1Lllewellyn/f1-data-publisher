# F1 2026 event-scoped forecast input provenance — Work Result

Date: 2026-10-18

Branch: `audit/2026-10-18-event-input-provenance-01`

Base: `a986c0560b8b4fbc1ce01ad3299d349f74970713` (`main`)

Independent checkpoint: `2185efb64` (`Validate event-scoped forecast input evidence`)

## Result

The new offline bridge closes the structural link between the existing frozen-input producer and the existing DR-002 Gate 2B-4 lock constructor. It does not alter either accepted dependency.

For one explicitly supplied prediction package, the bridge now:

- binds exact event, meeting, target session, allowed source sessions, prediction gate, lane, cutoff, generation, lock and deadline;
- validates the exact source and source-capture receipt bytes and SHA-256 values;
- reuses `produce_actual_forecast_rows_v1.frozen_sources` for CSV structure and scope validation;
- enforces source observation, ingestion and receipt-creation times at or before the declared cutoff;
- requires an exact target-session `drivers` participant universe and rejects every driver-bearing source containing a driver outside it;
- verifies the unchanged producer bytes against the declared Git commit before the single offline invocation;
- checks that the producer output contains exactly the verified participant universe and requested event/gate/lane/timestamp;
- builds the existing DR-002 input-manifest hash, producer-execution receipt and forecast-lock receipt; and
- atomically retains the exact request, input bytes, capture-receipt bytes, output bytes, producer diagnostics and lock evidence in one read-back-verified package.

No source discovery, provider request, workflow dispatch, stable-engine execution, publication, production write, trust upgrade or DR-002 activation is performed.

## Synthetic producer-to-lock proof

The committed fixture is deliberately synthetic, manual-validation-only and unapproved. Two repeated position observations per driver prove that legitimate row-level repetition is retained while the event participant set remains exactly drivers 1 and 2.

Two independent executions produced identical evidence hashes:

| Evidence | SHA-256 / value |
|---|---|
| Forecast rows | `cd5484041dd81fee4758689ae5a620899920166f05eedf6458a0ab61f8b9ce56` |
| DR-002 input manifest | `9c00d6186301b0f8e01eef452197f077cbf250837d44e5307be39c670a9583fe` |
| Producer receipt | `422e48241a271864d61bcc89123afb09822a0abb5e26081f2fca94719a32f6c8` |
| Forecast-lock receipt | `4d261d4cae23b68a85635f9a2e44ac3af224a52b8c406dacb980a454f6d261f1` |
| Bundle evidence manifest | `c03789d73340ba02631736351d640c9c10b0de6747bc111d527e5015a7bf1a25` |
| Forecast rows / participants | `2 / [1, 2]` |
| Terminal status | `LOCKED_OUTPUT_WITH_RETAINED_INPUT_EVIDENCE` |

The bundle manifest records every retained file's relative path, byte count and SHA-256, and all files are read back before the staging directory is atomically promoted.

## Focused validation

Command:

```text
python -m unittest -v tests.test_event_scoped_forecast_input_lock_v1
```

Result: **7 passed**.

Covered behavior:

1. valid exact-byte package and repeated driver observations;
2. mutated source rejection;
3. cross-event receipt rejection;
4. post-cutoff source rejection;
5. extra participant rejection;
6. exact producer output, retained evidence and lock binding; and
7. no output package left after validation failure.

Syntax compilation passed for the implementation and test module. `git diff --check` passed.

## Reused dependency pins

All are unchanged from `main`:

| Dependency | Git blob | SHA-256 |
|---|---|---|
| `scripts/forecasts/produce_actual_forecast_rows_v1.py` | `af27586668c767de126af829c1131c6bae4634ad` | `8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564` |
| `scripts/forecast_bundles/verify_forecast_integrity_receipts_v1.py` | `ccd17a28744f0e7c6706c3be9562d57b7dcea0ae` | `16f688604f11c12893e515eb30a7b0d2de5e585405cb2750571e4c8e005a6bf1` |
| `scripts/forecast_bundles/dr002_lock_boundary_revision_v1.py` | `064d93ee5ae30354590a3fb95be598c5fe8b3b9a` | `a3ab208b7c446424953c54948a180deaa7e27e2c00eafcb81b27d5fc7946e7f7` |
| `scripts/forecast_bundles/forecast_integrity_contract_v1.py` | `9f5a3585814f4e5eb7a1f95ecdada90a33090857` | `889d1c2b27dba8c441a0406c0647031a924981aaf337dee7c99e8dcd9148a3ff` |

## Scientific eligibility limits

- The synthetic proof is not a real forecast, does not authenticate a provider or execution environment, and makes no accuracy or prospective-readiness claim.
- The bridge verifies the declared receipt-binding hash and retains its external verification reference; it does not authenticate that external verifier. A future operational run still requires independently authenticated source-capture bindings.
- `contract_approved` remains false in the fixture. A prospective run requires a separately approved product contract and authorized capture/operation.
- The lock package intentionally has no post-event outcome boundary. That boundary can only be added after a genuine outcome becomes available under the existing contract.
- Nothing here supplies missing historical availability evidence. PR #311's historical cutoffs remain ineligible and are not reclassified.
- The unchanged producer is exercised without the protected stable engine. No model, energy coefficient, fantasy consumer or prediction logic changed.

## Protected scope

Issue #309, PRs #310–#312, Austin controls, DR-002 activation state, `Engine_2026-06-07_STABLE`, the canonical workbook, production forecasts, workflows and `latest/` / `history/` production data were untouched.
