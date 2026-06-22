# v26R2 Test and Simulation Report

## Unit tests

- Tests run: 14
- Failures: 0
- Errors: 0
- Result: PASS

## Simulation

- Trials per model: 200,000
- Seed: 20260622

| Model | Duplicate sends | Oversize attempts | Receiver failures after send | Evidence overclaims | Unsafe merge risk | First-try reliable |
|---|---:|---:|---:|---:|---:|---:|
| v25 | 28,128 | 29,863 | 113,971 | 35,941 | 9,885 | 40,203 |
| v26_initial | 0 | 29,863 | 85,843 | 0 | 9,885 | 104,272 |
| v26R1 | 0 | 0 | 55,980 | 0 | 9,885 | 134,135 |
| v26R2 | 0 | 0 | 0 | 0 | 0 | 200,000 |

## Interpretation

v26R2 is the first tested design in this sequence that blocks every observed transport/receiver/evidence/merge failure class before dispatch in the simulation model. It does not prove live success; it proves the rebuilt compiler is better aligned with observed contracts than v25, v26 initial, and v26R1.

## R3 receiver-test finding

Uploaded receiver logs for R2 showed `validate_command` PASS and `apply_assistant_patch` PASS, followed by `run_requested_tests` exit code 1 before PR creation.
Current receiver code reads `payload.tests` as allowlisted names. The R2 command used a raw Python command string, so R3 blocks that pattern locally.
