# DR-002 pre-2B-7C2 — Live frozen-producer shadow checkpoint

Work order: F1-WO-DR002-PRE2B7C2-001 (Issue #142).
Result: COMPLETED — single initial-attempt synthetic shadow succeeded; independently inspected artifact checks PASS. Coder completion is not Adviser acceptance.
Checkpoint filename retains the authorized 2026-10-03 Toronto date. Actual UTC run timestamps below are 2026-10-04; no timestamp was backdated.

## OBSERVED GITHUB FACT

Accepted predecessor PR #141, reviewed head `e4bbd95f336071f28bdbb9b38000ec2c2c4b17f9`, merged as `10a5dd7ae81028da6d1bf1c6bbd6b6de1f93e83d`. Exactly the four accepted additions landed. The 33 previously reviewed tests were not redundantly rerun.

The user dispatched the single manual run. Issue #142's execution-state comment confirms this handoff. Coder discovered the existing completed run and performed **zero additional dispatches**, zero reruns and zero failed-job reruns.

| Run field | Observed value |
|---|---|
| Workflow | DR-002 synthetic frozen producer shadow pilot |
| Path | .github/workflows/dr002-frozen-producer-shadow-pilot.yml |
| Run ID / number / attempt | 37166164887 / 1 / 1 |
| Event / branch / ref | workflow_dispatch / main / refs/heads/main |
| Head SHA | 10a5dd7ae81028da6d1bf1c6bbd6b6de1f93e83d |
| Started UTC | 2026-10-04T00:50:17Z |
| Job completed UTC | 2026-10-04T00:53:20Z |
| Run last updated UTC | 2026-10-04T00:53:21Z |
| Conclusion | success |
| Job ID / name / conclusion | 111329375929 / shadow / success |
| Observer | GitHub Actions ubuntu-latest runner; CPython 3.12.14 |
| Permissions observed in job log | Contents: read; Metadata: read |
| Checkout | Exact head SHA; persist-credentials: false |

Run: https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37166164887

GitHub exposes run last-updated rather than a separate run-completed field here; it is not substituted for the recorded job completion.

| Step | Conclusion |
|---|---|
| Set up job | success |
| Run actions/checkout@v4 | success |
| Run actions/setup-python@v5 | success |
| One synthetic frozen-mode producer CLI shadow | success |
| Run actions/upload-artifact@v4 | success |
| Post Run actions/setup-python@v5 | success |
| Post Run actions/checkout@v4 | success |
| Complete job | success |

| Artifact field | Observed value |
|---|---|
| ID | 11289234035 |
| Name | dr002-frozen-producer-shadow-37166164887-1 |
| ZIP size | 15246 bytes |
| GitHub ZIP digest | sha256:8c66fd6fcbb9436a87fef3defa8a9b16d3f95e576395d785502a1db62f8c5e21 |
| Created UTC | 2026-10-04T00:53:17Z |
| Expires UTC | 2027-01-02T00:50:19Z |
| Expired at inspection | false |

Artifact: https://github.com/F1Lllewellyn/f1-data-publisher/actions/runs/37166164887/artifacts/11289234035

Fresh main before the documentation branch remained `10a5dd7ae81028da6d1bf1c6bbd6b6de1f93e83d`, equal to the run head and predecessor merge. No provenance-workflow commit or push occurred. Workflow/log inspection shows only checkout, Python execution and runtime artifact upload, not a repository-write step. Runtime sandbox outputs were not committed to checkout latest/** or history/**; no workbook, ledgers, production workflow or downstream consumer was invoked.

### Relevant dependencies: PASS

All nine declared dependency Git blob SHA fingerprints matched on the exact run head. Blob identities were independently recomputed from fetched bytes with Git's blob header algorithm during the evidence review.

| Path | Expected and observed blob SHA |
|---|---|
| scripts/forecasts/produce_actual_forecast_rows_v1.py | af27586668c767de126af829c1131c6bae4634ad |
| .github/workflows/dr002-frozen-producer-shadow-pilot.yml | ba852c373c57d0277e80ccf815dcaff6e1898f15 |
| scripts/forecast_bundles/dr002_frozen_producer_shadow_pilot_v1.py | 1d3bfaf713807e799a6323875de670dc8d4e1a85 |
| .github/workflows/f1-actual-forecast-producer-v1.yml | e115718f2b7fed9f0e87a47b1138b3462b9b6cb1 |
| .github/workflows/f1-automated-forecast-gate-orchestrator-v1.yml | 32a1210a2f43065e9d65a9bd858c059b6166700f |
| scripts/forecast_bundles/orchestrate_forecast_gate_pipeline_v1.py | 1f95311dc6f3874e207fdc889a1a1b49c9acafab |
| configs/forecasts/actual_forecast_producer_policy_v1.json | 964f78f67a0e44de9304c10b0e7bf35ea7620694 |
| configs/forecast_bundles/forecast_gate_orchestrator_policy_v1.json | ebcd6d9d0a071b5cb14d62dbc9687e4d577af266 |
| docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md | 91dfffd80635f643a2f605f75422c6311e93a9c6 |

## OBSERVED ARTIFACT FACT

Downloaded ZIP: 15,246 bytes. Independent exact-byte ZIP SHA-256:
`8c66fd6fcbb9436a87fef3defa8a9b16d3f95e576395d785502a1db62f8c5e21`.
It matches GitHub's digest and job upload log.

Exactly eleven files under `gha-37166164887-1/`: execution_manifest.json, shadow_report.md, plus the nine evidence files below. No scientific receipt or verified binding exists. No raw runtime artifact is added to this repository.

| Evidence file under evidence/ | Independently recomputed SHA-256 |
|---|---|
| drivers.csv | a5225adcc4ab55f9ea33c11de7cef4fc06a30171c56a7d681fd4c4987b335ba0 |
| starting_grid.csv | 5562a093d45052ea2b1f6360b2b98d3960cf9671c9f3eb63e62a2edd52b77d76 |
| weather.csv | 9430d44f65329bdc68ba2afe20a577ace75f7643b90909805ba1a047f2631d52 |
| frozen_input_manifest.json | 6a4c7ba55884fbc989c7d19146d37b1470e85d78b75d5910935d8932d27fe6ec |
| producer_code.py | 8677b0b6a10833e2e2ce78053ec06f08b64d456ba834ee0e829de2faf5330564 |
| producer_audit.json | 913a665549a95abbd834b1e7db070291d4c79148d6308cf77fadef0a8f2e923f |
| source_snapshot_manifest.csv | 91dbed9ad7704d2f368934f416b96f770611e3b1526f4a33d1721e8a71a2bcb8 |
| forecast_rows.csv | 6087578a7b2dd92c17e916d6563678b0b47ce565c6a5132d377d794cbe06829a |
| forecast_metadata.json | 5eb057295cf0b3393789775ab17cbbcba1828a4f3e4f6b801021ef8221b31f64 |

Every entry equals execution_manifest.evidence_sha256. The frozen manifest's exact persisted-byte hash equals frozen_manifest_sha256. The copied producer code recomputes both accepted SHA-256 and Git blob SHA `af27586668c767de126af829c1131c6bae4634ad`.

Source identities and independently parsed counts: synthetic:dr002:drivers = 2; synthetic:dr002:starting_grid = 2; synthetic:dr002:weather = 1. Source snapshot, audit, metadata and frozen manifest agree on the declared identities and hashes. All omitted source counts are zero.

## EXECUTED LIVE SHADOW FACT

The job log records one real producer CLI shadow invocation, exit code 0, implementation_git_sha matching run head. Artifact status is `SHADOW_EXECUTION_ONLY_NOT_A_PRODUCTION_FORECAST`; execution_mode is `manual_github_synthetic_frozen_shadow`; synthetic_inputs=true.

Scope: event `synthetic_dr002_frozen_producer_v1`; meeting `synthetic-meeting`; session `synthetic-session`; gate `post_qualifying`; lane `stable_baseline`. These are synthetic mechanics identities, not historical race evidence or protected-engine execution proof.

Producer audit and metadata report input_mode=frozen_manifest, broad_discovery_used=false. Artifact reports producer_output_sandbox_disposed=true, checkout_production_outputs_written=false, production_forecast_generated=false. Source readiness is 0.48. Two copied synthetic rows were independently inspected:

| Driver | Name | Team | Grid |
|---|---|---|---|
| 10 | Synthetic Ten | Ferrari | 2 |
| 20 | Synthetic Twenty | McLaren | 1 |

Both rows have runtime forecast_generation_utc `2026-10-04T00:53:16Z`; producer_run_id `20261004T005316Z`. No CLI timestamp was supplied. Legacy inner row/metadata forecast labels and probability fields remain unchanged evidence of producer behavior; they are not publishable production forecasts or blind-eligibility proof.

## UNPROVEN / NOT CLAIMED

Live manual synthetic frozen-producer shadow executed through the real producer CLI; explicit frozen inputs, sandbox containment and broad-discovery bypass are evidenced by the inspected GitHub run/artifact. This is synthetic mechanics/execution evidence only; production authentication, historical availability, protected stable-engine execution, blind eligibility and live lock/outcome/revision remain unproven.

Manifest flags production_authenticated, historical_availability_proven, stable_engine_execution_proven, blind_validation_eligible and dr002_activated are all false. Audit and metadata preserve false authentication, historical, protected-engine, activation, promotion and stable-overwrite flags. Lane naming does not prove Engine_2026-06-07_STABLE execution. No scientific receipts/bindings were fabricated.

DR-002 remains **PROPOSED — NOT ACTIVATED**. Forecast gate OFF; promotion NOT ALLOWED; protected stable engine and canonical workbook untouched. No live F1/OpenF1 capture, production forecast, production orchestration or Pipedream/Gmail occurred. Gate 2B-7 enforcement has not begun.

## Validation and deviations

Independent offline artifact inspection used stdlib zipfile, hashlib, json and csv: exact ZIP/file hashes, Git blob identity, source counts/identities, two driver/grid rows, runtime timestamp, audit/metadata flags and package inventory all PASS. No implementation test suite was rerun; no producer was executed locally.

Coordination deviation only: the user completed the authorized dispatch during browser sign-in. The current Issue #142 comment explicitly directs continuation from that existing run. Coder dispatched no additional run. No scope deviation, implementation edit or retry was needed.

Only this new checkpoint is proposed. Suggested next decision (advisory, not authorization): Science / Architecture Adviser independently reviews this run/artifact and accepts or HOLDs the Work Result. This PR is not self-accepting and is not authorization for enforcement or a successor gate.
