# v26R2 Bridge Recommendations

These are recommended bridge changes, not active changes in this sandbox package.

1. Add pre-dispatch payload-size guard in Pipedream before `repository_dispatch`.
2. Add `command_id` idempotency ledger in Pipedream.
3. Add optional signed manifest/pointer command type to avoid large Gmail bodies.
4. Require explicit `files[].action` before dispatch, not just receiver normalization.
5. Add `expected_head_sha` to `assistant_merge_pr` and pass it as `sha` to GitHub's merge endpoint.
6. Make repo inventory target-bound: PR number, head, base, expected paths, optional content hash.

## Recommended bridge enhancement: allowlisted v26R2 Python test

Add a named test such as `v26r2_python_tests` to `config/autopilot_allowed_tests.json` only through a separate PR-only receiver-contract checkpoint.
Do not send raw shell test commands in assistant patches.
