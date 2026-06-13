# F1 1B Consumer Context Publisher + Trigger Governor v25

## Scope

v25 combines four read-only output layers after the existing Control Room -> Output Contract -> Downstream Consumer chain:

1. Consumer Context Publisher
2. Trigger Governor
3. Material-change notification routing, decision-only
4. Read-only Race/Fantasy/Reports consumer bootstrap

## Outputs

- `latest/chat_context/race_predictions_context.md`
- `latest/chat_context/fantasy_predictions_context.md`
- `latest/chat_context/race_reports_context.md`
- `latest/chat_context/combined_context_index.json`
- `latest/consumer_trigger_governor/trigger_decision.json`
- `latest/consumer_trigger_governor/consumer_trigger_report.json`
- `latest/consumer_trigger_governor/consumer_context_publisher_report.json`
- `latest/notification_routing/notification_decision.json`
- `latest/notification_routing/notification_summary.md`
- `latest/downstream_consumers/*/consumer_bootstrap.json`

History snapshots are written under matching `history/` folders.

## Safety locks

- Forecast gate remains off.
- Promotion remains false.
- Stable engine is not modified.
- Canonical workbook is not overwritten.
- No external notification is sent. The notification layer is decision-only.
- Consumer bootstraps are read-only.

## Operational role

After v25, the downstream chats should have clean, human-readable context packs and machine-readable trigger decisions. This still does not run forecasts or reports automatically; it only tells each lane whether it is ready, blocked, quiet, or worth notifying on material change.
