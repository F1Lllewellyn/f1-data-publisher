"""Evidence state classifier that prevents upward claims."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List

ORDER = [
    "NO_EVIDENCE",
    "DISPATCH_ACCEPTED",
    "RECEIVER_VALIDATE_PASS",
    "APPLY_COMMAND_FILES_PASS",
    "RUN_REQUESTED_TESTS_PASS",
    "PR_STATUS_READY",
    "MERGED_BY_BRIDGE",
    "MAIN_PATH_VALIDATED",
    "CONTENT_HASH_READY",
]
RANK = {s:i for i,s in enumerate(ORDER)}

@dataclass
class EvidenceClassification:
    state: str
    notes: List[str]


def classify(event: Dict[str, Any]) -> EvidenceClassification:
    notes=[]
    subject = event.get("status_subject", "")
    status = event.get("status") or ""
    if status == "DISPATCH_ACCEPTED":
        return EvidenceClassification("DISPATCH_ACCEPTED", ["bridge accepted dispatch only"])
    if status == "PR_STATUS_READY":
        return EvidenceClassification("PR_STATUS_READY", ["bridge returned PR status"])
    if status == "MERGED":
        return EvidenceClassification("MERGED_BY_BRIDGE", ["bridge returned merged"])
    if event.get("main_branch") and event.get("changed_path_validated"):
        return EvidenceClassification("MAIN_PATH_VALIDATED", ["main branch path validated"])
    if event.get("content_hash_match") is True:
        return EvidenceClassification("CONTENT_HASH_READY", ["content hash verified"])
    if "REPO_INVENTORY_READY" in subject:
        return EvidenceClassification("NO_EVIDENCE", ["generic repo inventory is not a state promotion without target-bound proof"])
    return EvidenceClassification("NO_EVIDENCE", ["unrecognized or insufficient event"])


def can_claim(current_state: str, desired_state: str) -> bool:
    return RANK.get(current_state, -1) >= RANK.get(desired_state, 10**6)
