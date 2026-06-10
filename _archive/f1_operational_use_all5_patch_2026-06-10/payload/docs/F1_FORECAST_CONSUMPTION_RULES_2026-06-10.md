# F1 Forecast Consumption Rules

## Core rule

Automation outputs inform confidence, risk, fantasy context, and review priority. They do not automatically reorder stable predictions.

## Consumption map

| Board | Use | Automatic reorder? |
|---|---|---:|
| Source readiness | Input eligibility | No |
| Reliability warnings | Risk/confidence flags | No |
| DNF_ALL precursor board | Advisory precursor search | No |
| Fantasy risk board | Avoid/hold/monitor flags | No |
| Model disagreement board | Review priority | No |
| Promotion gate | Blocks automatic changes | No |

## Standing guardrails

- Public/proxy OpenF1 data only.
- No private/internal sensor assumptions.
- DNF_ALL remains broad.
- Visible DNF labels are metadata, not exclusion gates.
- 2026 no-DRS rule preserved.
