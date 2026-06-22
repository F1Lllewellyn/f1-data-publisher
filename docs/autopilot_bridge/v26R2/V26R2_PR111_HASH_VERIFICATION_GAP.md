
# PR #111 Hash Verification Gap

PR #111 landed the v26R2-R3 transport-safe compiler/latch package. Bridge evidence confirmed:

- `DISPATCH_ACCEPTED`
- branch commit validated
- `PR_STATUS_READY`j- approved merge gate returned `MERGED`
- main branch merge commit validated
- post-merge repo inventory found all 14 expected paths present on `main`

The remaining gap is byte-for-byte validation. The deployed `assistant_repo_inventory` lane can confirm branch tip and path presence, but it did not return per-file SHA-256 comparisons from the R2 hash request.

## Failed hash attempt lesson

The first hash attempt used the merge commit SHA as `ref`. The deployed Pipedream handler treated `ref` as a branch name and returned `Branch not found`. Correct pattern for the current handler is:

```json
{
  "ref": "main",
  "expected_commit_sha": "<merge_commit_sha>"
}
```

Even with the corrected pattern, the handler returned inventory fields, not content hashes.

## Closure language

Allowed:

`PR #111 = LANDED / MERGED / POST-MERGE PATH-VALIDATED

Not allowed yet:

`PR #111 = CONTENT-HASH VALIDATED`

until the bridge or an authenticated file-fetch lane returns per-file SHA-256 results.
