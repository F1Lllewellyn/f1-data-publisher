# 1C Gmail Autopilot Bridge Receiver

Installed by the v6 native CMD one-click installer.

Flow:

ChatGPT-approved command email → dedicated Gmail inbox → Pipedream bridge → GitHub `repository_dispatch` → GitHub Action → validate scope → apply patch → whitelisted tests → PR.

Safety:

- Production automation remains `OFF`.
- Forecast gate remains `OFF`.
- Promotion remains `false`.
- Stable engine and canonical workbook are blocked.
- Secrets/tokens/password paths are blocked.
- Deletes are blocked.
- Code/workflow/config changes happen by PR only.
