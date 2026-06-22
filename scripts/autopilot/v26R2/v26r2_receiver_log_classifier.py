"""Classify GitHub receiver log failures by pipeline stage."""
from __future__ import annotations
from typing import Dict, Any

STAGE_PATTERNS = {
    "VALIDATE_COMMAND_FAILED": ["missing_required_field", "validate_command", "Command validation failed", "invalid_target_branch_prefix"],
    "APPLY_COMMAND_FILES_FAILED": ["unsupported_action", "apply_assistant_patch", "Apply command files", "missing_content_base64"],
    "RUN_REQUESTED_TESTS_FAILED": ["Run requested tests", "run_requested_tests", "test failed", "exit code 1"],
    "WRITE_STATUS_LEDGER_FAILED": ["write_status_ledger", "status ledger"],
    "CREATE_OR_UPDATE_PR_FAILED": ["create-pull-request", "Error: GitHub", "pull request"],
}


def classify_log_text(text: str) -> Dict[str, Any]:
    hits=[]
    for stage, patterns in STAGE_PATTERNS.items():
        if any(p in text for p in patterns):
            hits.append(stage)
    if "missing_required_field:summary" in text:
        primary="VALIDATE_COMMAND_FAILED"; detail="missing_required_field:summary"
    elif "missing_required_field:project" in text:
        primary="VALIDATE_COMMAND_FAILED"; detail="missing_required_field:project"
    elif "unsupported_action:undefined" in text:
        primary="APPLY_COMMAND_FILES_FAILED"; detail="files[].action missing or undefined"
    elif hits:
        primary=hits[0]; detail="pattern_match"
    else:
        primary="UNKNOWN"; detail="no_known_pattern"
    return {"primary_stage": primary, "detail": detail, "all_hits": hits}
