# Immutable Forecast Ledger Validator Prototype

Validator behavior checkpoint for Enhancement 01C.

Checks: required fields present, entry_hash is 64 hex, revision hash is null or 64 hex, stable and experimental context remain separate, source readiness is present, and production/canonical/notification/promotion/stable-engine flags are not true without separate activation evidence.

Status: specification only. No live validation hook is activated.
