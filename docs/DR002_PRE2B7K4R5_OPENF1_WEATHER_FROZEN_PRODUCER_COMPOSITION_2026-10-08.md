# DR-002 pre-2B-7K4R5 — provenance weather frozen-producer composition

Date: 2026-10-08

Work order: `F1-WO-DR002-PRE2B7K4R5-001` / Issue #219

Status: mixed-input composition/mechanics capability only — **NOT A PREDICTION**

## Result

K4R5 adds one bounded offline wrapper that composes the accepted K4R4 OpenF1 weather adapter into the accepted real current producer frozen-input CLI.

The wrapper accepts only explicit in-memory raw-weather evidence and scope plus a 40-character implementation Git SHA used as execution-context metadata. It calls the unchanged K4R4 adapter, requires `OPENF1_WEATHER_PRODUCER_ADAPTER_VALIDATED`, creates deterministic synthetic drivers and starting-grid mechanics fixtures for the same event/meeting/session scope, and invokes `scripts/forecasts/produce_actual_forecast_rows_v1.py` once inside a disposable temporary repository root.

The producer runs with:

- frozen input manifest mode and `--strict-source`;
- explicit event, meeting, and session identifiers;
- gate `post_event`;
- lane `experimental_challenger`; and
- race name `Mixed-input provenance weather mechanics shadow - NOT A PREDICTION`.

This avoids representing the mixed real-weather/synthetic-driver run as a prospective blind forecast or protected stable-engine execution.

## Evidence and identity boundaries

The exact K4R4-validated OpenF1 raw response and its parentless `source_capture` receipt remain the only scientific source evidence.

The derived `weather.csv` is a runtime representation and receives the deterministic non-scientific identity:

`derived:openf1-weather-csv:<exact-derived-csv-sha256>`

That identity is deliberately different from the raw OpenF1 publisher/source identity because the bytes differ. The result preserves the raw receipt ID, raw source ID and SHA-256, K4R4 frozen-evidence manifest SHA-256, and derived CSV SHA-256 as separate facts.

The deterministic companion inputs contain two synthetic drivers and two synthetic grid positions. Their source IDs begin with `synthetic:` and bind their exact CSV hashes. They are mechanics fixtures only and are not F1 source evidence or historical truth.

No new scientific receipt, `producer_execution` receipt, or `verified_receipt_bindings` object is created.

## Containment and verification

The wrapper pins the real producer Git blob to `af27586668c767de126af829c1131c6bae4634ad` and materializes exactly `drivers.csv`, `starting_grid.csv`, `weather.csv`, and the existing frozen-manifest schema inside a temporary sandbox. Exact readback is required before the single subprocess attempt.

Successful validation requires the real producer evidence to show:

- `input_mode=frozen_manifest` and `broad_discovery_used=false`;
- exact event/meeting/session scope;
- exactly the three declared source identities, hashes, paths, and row counts;
- the derived weather identity/hash and exact K4R4 weather-row count;
- two generated synthetic-driver rows and source readiness `0.48` from drivers, starting grid, and weather;
- gate `post_event` and lane `experimental_challenger`;
- byte-identical latest/history copies and compatibility mirrors within the sandbox; and
- no unsupported authentication, historical-availability, stable-engine, activation, or promotion claim.

The wrapper reads and hashes the producer audit, source snapshot, forecast rows, and metadata into its in-memory result before sandbox disposal. It checks the sandbox file set exactly, verifies the checked-out repository `latest/**` and `history/**` metadata fingerprints did not change, and confirms the producer blob is unchanged after execution. It never persists producer output to the checked-out repository.

Any adapter HOLD, scope or implementation-context error, input/readback/hash/manifest mismatch, producer-pin change, producer failure, unexpected source or sandbox file, broad discovery, missing rows, evidence mismatch, checkout-output mutation, or sandbox-disposal failure returns `HOLD`. There is no retry loop and no success evidence is returned on failure.

## Focused verification

The focused offline suite covers the valid real-producer composition, unchanged K4R4 adapter call, raw-versus-derived identity separation, deterministic hash-bound derived and synthetic identities, exact frozen manifest, scope-bearing CSV fields, exact CLI arguments, producer pin, discovery bypass, source snapshot bindings, weather-row propagation, generated rows/readiness, checked-out-output preservation, sandbox-only writes and disposal, selected evidence hash recomputation, K4R4 HOLD short-circuiting, tampered inputs/manifest, single-attempt producer failure, absence of new receipts/bindings, false claim-ceiling flags, absence of network/API/secret access, and all named dependency blobs.

Only the focused K4R5 tests and cheap Python syntax/import checks are required. No workflow or live source call is part of K4R5.

## Claim ceiling

Success status is:

`MIXED_INPUT_FROZEN_PRODUCER_COMPOSITION_VALIDATED_NOT_A_PREDICTION`

K4R5 proves only that the accepted raw-weather provenance adapter composes mechanically into the accepted real producer frozen-input CLI, that the exact derived weather bytes/hash are the weather input consumed in the contained run, and that the producer generated rows from the explicit mixed input set with broad discovery bypassed.

It does **not** prove a real full-evidence F1 forecast, trustworthy driver/grid evidence, protected stable-engine execution, blind predictive eligibility, production source rollout, authenticated producer execution, forecast-lock/outcome/revision enforcement, DR-002 activation, model promotion, or accuracy improvement. The generated probabilities are not scientifically meaningful because drivers and starting grid are synthetic.

OpenF1 remains an unofficial source and does not outrank official FIA/F1/team/Pirelli evidence.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate **OFF**. Promotion **NOT ALLOWED**.
