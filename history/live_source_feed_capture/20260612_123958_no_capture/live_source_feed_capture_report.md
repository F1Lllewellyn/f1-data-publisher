# F1 Live Source Feed Capture Report

Generated UTC: 2026-06-12T12:39:58.597514Z

## Verdict

Pass with warnings

## Capture status

- should_capture: False
- reason: schedule_lookup_failed: 401 Client Error: Unauthorized for url: https://api.openf1.org/v1/sessions?year=2026
- session_label: 
- duration_minutes: 
- recording_status: no_active_capture_window
- raw_size_bytes: 0
- line_count: 0

## Guardrails

- do_not_promote_to_stable: True
- do_not_change_canonical_workbook: True
- do_not_claim_accuracy_gain: True
- do_not_mix_live_capture_with_post_session_api_without_source_labels: True
- no_drs_2026_assumption: True
- github_is_archive_and_orchestrator_not_truth_without_reconciliation: True

## Notes

This is an experimental live source-feed capture layer. It records source feed evidence for post-session replay and reconciliation. It does not update stable predictions or canonical workbooks.