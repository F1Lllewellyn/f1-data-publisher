# Ledger Seed — v26R2-R6 No Automations for Bridge Gates

Add this state to the Continuity Specialist Engine ledger:

- PR-only checkpoint: `CONTINUITY-V26R2-R6: add no-automations bridge gate rule [01]`
- Purpose: formalize the rule that scheduled automations must not be used for Gmail/Pipedream/GitHub bridge gates unless explicitly requested by the user.
- Reason: automations open in another chat and break continuity, state discipline, send ledger context, screenshot reconciliation, and mutation-boundary control.
- Scope: docs/governance only.
- Required qualifiers:
  - no production activation
  - forecast gate off
  - no stable-engine change
  - no canonical workbook overwrite
  - no model promotion
  - no prediction generation

Operational rule text:

`Bridge follow-up checks must remain in the active chat. Use newest-email checks after meaningful lag. Do not use scheduled automations for bridge gates unless explicitly requested by the user.`
