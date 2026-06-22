# v26R2 Rebuild Design

## Design principle

Small, modular, direct, precise — enforced by code, not remembered by the assistant.

## Rebuild reason

The v26 prototype fixed some symptoms, but the evidence showed it missed core downstream contracts: Gmail route limitations, Pipedream parser shape, GitHub repository_dispatch payload budget, receiver validate/apply requirements, fixed-branch PR update behavior, and merge head-SHA protection.

## Hard compiler gates

Before any assistant_patch may be sent, v26R2 requires:

- `project`
- `summary`
- `files[].action == "upsert"`
- valid target branch prefix
- `base_branch == "main"`
- stable/protected surfaces blocked
- production automation OFF
- forecast gate OFF
- promotion NOT_PROMOTED
- activation NOT_ACTIVATED
- compact repository_dispatch payload <= 60,000 bytes

## Transport rule

Inline Gmail body is the only currently approved route. Local body_file path transport is disabled because it failed connector validation in this environment.

## Landing rule

Large packages must be split into sequential chunks. Chunk 1 lands and merges before chunk 2 is dispatched, so no non-cumulative same-branch overwrite risk is introduced.

## R3 correction

R3 adds the receiver test allowlist contract. The compiler now blocks raw shell commands in `tests`.
This reflects the live receiver behavior where `payload.tests` contains names from `config/autopilot_allowed_tests.json`, not arbitrary commands.
