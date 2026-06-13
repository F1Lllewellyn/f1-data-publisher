# F1 1B v23 Control Room Output Contract Bridge Hardening

This patch replaces only `.github/workflows/f1-1b-output-contract-after-control-room-v22.yml`.

Purpose: remove inline Python heredocs from the bridge workflow because the repository meta-health checker treats the word `if` inside heredoc code as Bash control-flow and blocks the Control Room chain with a false Bash if/fi imbalance.

Safety:
- no stable engine modification
- no canonical workbook overwrite
- no forecast gate activation
- no promotion
- no cleanup or repository scanning
- no local `.git` access from the installer

Expected result after install and Control Room rerun:
1. Control Room static/meta validation passes.
2. Control Room full chain succeeds.
3. The bridge workflow runs automatically after the successful Control Room run.
4. Output-contract ledger, last-good state, material-change report, and readiness handoff are refreshed.
