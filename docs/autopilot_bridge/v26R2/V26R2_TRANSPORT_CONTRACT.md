# v26R2 Transport Contract

## Evidence-backed chain

Gmail inline body -> Pipedream envelope parser -> GitHub repository_dispatch -> GitHub Actions receiver -> create/update PR.

## Prohibited transport

- local `/mnt/data/...` as `body_file`
- oversized all-in-one assistant_patch
- same-gate duplicate sends
- generic repo inventory used as proof of PR state

## Required measurements

The compiler measures:

- compact command JSON bytes
- repository_dispatch client_payload bytes, modeled as `{command: <command>}`
- pretty email body bytes
- file count and content hashes

## Payload budget

The v26R2 compiler uses 60,000 bytes as the hard budget. This is deliberately below GitHub's documented under-64KB payload limit to preserve margin.

## Receiver test allowlist contract

The receiver `run_requested_tests.mjs` does not execute raw shell strings from `tests`.
It interprets `tests` as named entries in `config/autopilot_allowed_tests.json`.
Raw values such as `python scripts/...` fail with `test_not_whitelisted` before PR creation.
Until a dedicated allowlisted `v26r2_python_tests` entry exists, v26R2 landing commands should use an empty `tests` array and include local test evidence as committed sandbox evidence.
