# DR-002 pre-2B-7D1 — GitHub-attested synthetic shadow capability

Work order: **F1-WO-DR002-PRE2B7D1-001**, Issue #144. Implementation proposal; independent Adviser review required.
DR-002 remains **PROPOSED — NOT ACTIVATED**. This installs capability only; it provides no new live attestation evidence.

## Baseline and bounded scope

Accepted predecessor PR #143, reviewed head `bf8b10e9cee1421a9daf42fa9a5be27c6ad397a8`, merged unchanged as `94e5fda257b61e976216670ab4c36efce852c441`. Its sole checkpoint blob is `f033e4601443b85096a6ef07695de5462d2e2909`.
Fresh starting main: `94e5fda257b61e976216670ab4c36efce852c441`.
Branch: `dr002-pre2b7d1-github-attested-shadow-20261003`.
All ten declared dependency fingerprints matched after the merge. Production config blobs additionally matched the existing accepted baseline. PR commit/history identifies the final head; no self-referential head hash is inserted here.

Exactly three paths:
- MODIFY `.github/workflows/dr002-frozen-producer-shadow-pilot.yml`
- ADD `tests/test_dr002_frozen_producer_attestation_v1.py`
- ADD this checkpoint.

No wrapper, producer, production/scheduled workflow, orchestrator, config, receipt/schema or workbook changes. Prior test/live work was not rerun merely as ceremony.

## First-party architecture and selected release

First-party sources consulted on 2026-10-04 UTC:
- [GitHub artifact-attestation documentation](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- [actions/attest immutable v4.2.2 release](https://github.com/actions/attest/releases/tag/v4.2.2)
- [pinned action definition](https://github.com/actions/attest/blob/1e69f48acb82d1966a394da916b4c1698aa569d6/action.yml)
- [pinned signing/storage implementation](https://github.com/actions/attest/blob/1e69f48acb82d1966a394da916b4c1698aa569d6/src/attest.ts)

GitHub's API reports v4.2.2 as its current immutable release, published 2026-08-04. The workflow pins commit `1e69f48acb82d1966a394da916b4c1698aa569d6` with a v4.2.2 comment, not a floating major. It uses default SLSA build provenance, not custom predicates or a custom signing scheme.

Permissions are exactly `contents: read`, `id-token: write`, `attestations: write`.
The selected file-subject mode explicitly disables registry push and storage records. The pinned implementation enters storage-record creation only for a registry push; therefore `artifact-metadata: write` is omitted. No contents/actions/packages/deployments write or write-all permission is granted. OIDC and attestation permission apply only to this manual synthetic shadow job.

## Subject and publication sequence

Existing workflow_dispatch-only trigger and main-only job restriction remain. The accepted wrapper invocation is unchanged and occurs exactly once.

After successful wrapper completion, `attest_shadow` attests the exact existing file:
`_runtime/dr002_pre2b7c_frozen_producer_shadow/gha-${{ github.run_id }}-${{ github.run_attempt }}/execution_manifest.json`.

No reconstructed JSON or caller-supplied subject digest is attested. No subsequent step writes the subject.
On success, the auxiliary step reads the action's `bundle-path` output and preserves its bytes unchanged as `github_attestation.bundle.json`. It writes `github_attestation_metadata.json` from explicit action outputs and GitHub context, including attestation ID/URL, subject relative path, independently recomputed exact-byte subject SHA-256, repository, workflow path/name/ref, head SHA, run ID and attempt.

Auxiliary consistency checks reject missing/malformed action outputs, a non-success manifest, run-head mismatch, altered subject digest, unexpected trust claims, or bundle/metadata readback failure. The decoded bundle's sole subject digest must match the exact manifest bytes. **This check does not verify a signature or establish authentication**; it guards against packaging inconsistent evidence. A later independent GitHub/Sigstore verification must verify signature, trusted identity/provenance claims and expected repository/workflow/commit, as well as exact subject bytes.

No raw OIDC token, signing credential or GitHub token is persisted or logged by auxiliary code. Metadata is not a DR-002 receipt or verified binding.

The unchanged always-upload step then uploads the runtime shadow directory, including the two new auxiliary files. Attestation/auxiliary steps use default success-only execution with no continue-on-error. If signing fails, the job fails; diagnostic upload cannot turn it into success. Partial files from a failed run must not be represented as successfully attested.

## Trust ceiling and future verification

If a separately authorized future live run passes independent verification, a GitHub/Sigstore attestation can cryptographically bind exact execution_manifest bytes to the GitHub provenance claims in the verified attestation. The manifest's evidence_sha256 entries then bind the listed artifact evidence bytes. This is a transitive **hash relationship**, not F1 source truth.

Wrapper and manifest flags are unchanged:
`production_authenticated=false`, `historical_availability_proven=false`,
`stable_engine_execution_proven=false`, `blind_validation_eligible=false`,
`dr002_activated=false`. Auxiliary metadata preserves the same false ceiling.

Synthetic bundle fixtures in offline tests contain no cryptographically valid signature. They prove packaging/consistency behavior only. No scientific receipt, producer_execution receipt or verified_receipt_bindings is created. Existing inner producer labels do not prove protected-engine execution or blind eligibility.

## Required conclusions

| Question | Answer |
|---|---|
| GitHub attestation capability installed on the manual synthetic shadow in this proposed change? | YES |
| Subject exactly this run's execution_manifest.json? | YES |
| Exact action bundle and factual metadata preserved? | YES, after successful attestation |
| Manual-only and production-inactive? | YES |
| New attested live run in this work order? | NO |
| F1/OpenF1 source authenticity proven? | NO |
| Historical availability proven? | NO |
| Protected stable-engine execution proven? | NO |
| Blind eligibility or live lock/outcome/revision proven? | NO |
| DR-002 or Gate 2B-7 activated? | NO |
| Next step if accepted? | Separately authorize exactly one manual attested synthetic shadow run and independent attestation/artifact verification |

Observation completeness and active production-path enforcement also remain unproven.

## Validation

Command:
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_dr002_frozen_producer_attestation_v1.py' -v`

**25 focused offline tests PASS, zero failures/errors.** Static workflow checks cover trigger, main restriction, least permissions, unchanged single invocation, ordering, exact subject, pinned release, failure propagation, output bindings, immutable subject, diagnostic upload, no tokens, no source API/production invocation, no scientific receipts and byte-identical accepted wrapper/producer/production workflows/orchestrator/configs. Synthetic auxiliary tests exercise exact bundle copy, metadata hash/context and false flags, missing files/outputs, changed subject, wrong digest/head, HOLD status, trust-upgrade rejection and invalid run identity.

YAML syntax and parsed six-step structure checked with PyYAML BaseLoader; inline Python and test source parsed with ast. No network-dependent tests; no cryptographic/live verification claimed. No full repository suites, workflow dispatch, source capture or production producer execution occurred.

## Controls and rollback

Engine_2026-06-07_STABLE untouched; canonical workbook untouched; forecast gate OFF; promotion NOT ALLOWED. No production forecast generated, latest/history/ledgers output committed, or Pipedream/Gmail used. Gate 2B-7 enforcement has not begun.

Rollback: revert this isolated three-file PR; this removes the proposed workflow capability and auxiliary tests/documentation without production/data migration. Previously recorded live evidence remains historical and unchanged. Do not merge or dispatch until separately authorized after Adviser review.
