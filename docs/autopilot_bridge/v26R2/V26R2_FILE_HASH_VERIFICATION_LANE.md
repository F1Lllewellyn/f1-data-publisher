
# V26R2-R4 File Hash Verification Lane

Status: sandbox/documentation/helper only. This checkpoint does **not** activate production automation, modify the stable engine, overwrite the canonical workbook, promote a model, or generate predictions.

## Purpose

PR #111 landed v26R2-R3 and post-merge inventory proved the expected files were present on `main`, but the deployed `assistant_repo_inventory` bridge lane did not return per-file SHA-256 comparisons. The attempted hash command also exposed an important contract detail: `assistant_repo_inventory.ref` is interpreted as a branch name by the current Pipedream handler, not as an arbitrary commit SHA.

This R4 checkpoint records the missing read-only capability and adds a dormant local helper that can be used by a future bridge/runtime implementation to verify file contents without mutation.

## Required future bridge behavior

A future read-only bridge lane, tentatively named `assistant_file_hash_verification`, should:

1. Accept a branch/ref name such as `main` and an optional `expected_commit_sha`.
2. Resolve the branch tip and fail closed if the tip does not match `expected_commit_sha` when provided.
3. Fetch each expected file at that resolved commit.
4. Compute SHA-256 over the exact UTF-8 bytes returned for each file.
5. Return one entry per file with `path`, `present`, `byte_length`, `sha256`, `expected_sha256`, and `match`.
6. Return aggregate fields: `all_present`, `all_hashes_match`, `missing_paths`, `mismatched_paths`, and `read_only: true`.
7. Never patch, merge, close, dispatch workflows, alter branch state, activate production automation, promote model logic, alter the stable engine, overwrite workbook data, or generate predictions.

## Required interpretation rule

Path validation is not content validation. A closeout may say `POST-MERGE PATH-VALIDATED` after `missing_expected_paths: []`, but may say `CONTENT-HASH vALIDATED` only after per-file hashes are returned and all expected hashes match.

## Lag-aware bridge rule

Every Gmail-to-bridge command must be treated as asynchronous. Do not declare missing status until a meaningful lag window has passed or a terminal status such as `PIPEDREAM_ERROR`, `MERGE_BLOCKED`, or a receiver failure is returned.

## Current PR #111 status

`PR #111 = LANDED / MERGED / POST-MERGE PATH-VALIDATED / CONTENT-HASH vALIDATION NOT PROVEN BY DEPLOYED BRIDGE`.
