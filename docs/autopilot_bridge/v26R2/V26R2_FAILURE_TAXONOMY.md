# v26R2 Failure Taxonomy

Observed receiver failure classes:

1. `VALIDATE_COMMAND_FAILED`
   - missing `project`
   - missing `summary`
   - invalid target branch prefix

2. `APPLY_COMMAND_FILES_FAILED`
   - missing or undefined `files[].action`
   - invalid base64 or content path problems

3. `RUN_REQUESTED_TESTS_FAILED`
   - command applied, but requested tests failed

4. `TRANSPORT_FAILED_NO_MESSAGE_ID`
   - Gmail connector rejects route before send

5. `OVERSIZE_BLOCKED_PRE_SEND`
   - command would exceed repository_dispatch budget

6. `EVIDENCE_OVERCLAIM_BLOCKED`
   - attempted upward claim without evidence state

## RUN_REQUESTED_TESTS_FAILED / test_not_whitelisted

If `validate_command` and `apply_assistant_patch` pass but `run_requested_tests` exits with code 1 and the command supplied a raw shell string in `tests`, classify as `RUN_REQUESTED_TESTS_FAILED:test_not_whitelisted`.
Corrective action: use only allowlisted test names or an empty tests array with separately committed local evidence.
