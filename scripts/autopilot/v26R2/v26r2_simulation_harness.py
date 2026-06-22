"""Evidence-weighted v25/v26/v26R2 comparison simulation."""
from __future__ import annotations
import random, json
from typing import Dict, Any

MODELS = ["v25", "v26_initial", "v26R1", "v26R2"]
SCENARIOS = [
    "happy_small_inline",
    "duplicate_send_risk",
    "oversize_payload",
    "missing_project",
    "missing_summary",
    "missing_file_action",
    "bad_branch_prefix",
    "generic_repo_inventory_overclaim",
    "advisory_review_noise",
    "merge_without_head_sha",
    "stale_public_github_view",
]
WEIGHTS = {
    "happy_small_inline": 0.20,
    "duplicate_send_risk": 0.14,
    "oversize_payload": 0.15,
    "missing_project": 0.07,
    "missing_summary": 0.07,
    "missing_file_action": 0.08,
    "bad_branch_prefix": 0.06,
    "generic_repo_inventory_overclaim": 0.08,
    "advisory_review_noise": 0.05,
    "merge_without_head_sha": 0.05,
    "stale_public_github_view": 0.05,
}

def pick_scenario(rng):
    r=rng.random(); total=0
    for k,v in WEIGHTS.items():
        total += v
        if r <= total:
            return k
    return SCENARIOS[-1]


def evaluate(model: str, scenario: str) -> Dict[str, int]:
    m={"valid_completion":0,"safe_hold":0,"duplicate_send":0,"oversize_attempt":0,"receiver_failure_after_send":0,"evidence_overclaim":0,"unsafe_merge_risk":0,"first_try_reliable":0}
    if scenario == "happy_small_inline":
        m["valid_completion"] = 1; m["first_try_reliable"] = 1
    elif scenario == "duplicate_send_risk":
        if model == "v25": m["duplicate_send"] = 1; m["receiver_failure_after_send"] = 1
        else: m["safe_hold"] = 1; m["first_try_reliable"] = 1
    elif scenario == "oversize_payload":
        if model in ["v25", "v26_initial"]: m["oversize_attempt"] = 1; m["receiver_failure_after_send"] = 1
        else: m["safe_hold"] = 1; m["first_try_reliable"] = 1
    elif scenario in ["missing_project", "missing_summary", "missing_file_action", "bad_branch_prefix"]:
        if model in ["v25", "v26_initial", "v26R1"]: m["receiver_failure_after_send"] = 1
        else: m["safe_hold"] = 1; m["first_try_reliable"] = 1
    elif scenario in ["generic_repo_inventory_overclaim", "advisory_review_noise", "stale_public_github_view"]:
        if model == "v25": m["evidence_overclaim"] = 1
        else: m["safe_hold"] = 1; m["first_try_reliable"] = 1
    elif scenario == "merge_without_head_sha":
        if model in ["v25", "v26_initial", "v26R1"]: m["unsafe_merge_risk"] = 1
        else: m["safe_hold"] = 1; m["first_try_reliable"] = 1
    return m


def run_simulation(trials: int = 200000, seed: int = 20260622) -> Dict[str, Any]:
    rng=random.Random(seed)
    totals={model:{"trials":0,"valid_completion":0,"safe_hold":0,"duplicate_send":0,"oversize_attempt":0,"receiver_failure_after_send":0,"evidence_overclaim":0,"unsafe_merge_risk":0,"first_try_reliable":0} for model in MODELS}
    scenario_counts={s:0 for s in SCENARIOS}
    for _ in range(trials):
        scenario=pick_scenario(rng); scenario_counts[scenario]+=1
        for model in MODELS:
            totals[model]["trials"]+=1
            e=evaluate(model, scenario)
            for k,v in e.items(): totals[model][k]+=v
    return {"trials":trials,"seed":seed,"scenario_counts":scenario_counts,"model_totals":totals}

if __name__ == "__main__":
    print(json.dumps(run_simulation(), indent=2, sort_keys=True))
