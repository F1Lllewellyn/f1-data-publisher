"""
F1 Continuity Specialist Engine v26R2 contract layer.
Sandbox-only implementation. It compiles and validates bridge commands before any transport.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import json, hashlib, base64

MAX_GITHUB_DISPATCH_CLIENT_PAYLOAD_BYTES = 60000  # Conservative safety budget below GitHub's <64KB documented limit.
ALLOWED_TARGET_PREFIXES = ("autopilot/", "install/", "outputs/")
DEFAULT_REQUIRED_PATCH_FIELDS = (
    "schema_name", "schema_version", "command_type", "project", "repository", "safety_mode",
    "title", "base_branch", "target_branch", "summary", "files"
)
PATCH_ALLOWED_SAFETY_MODES = {"pr_only"}
PATCH_ALLOWED_ACTIONS = {"upsert"}

# Receiver run_requested_tests.mjs expects payload.tests to contain named allowlist entries,
# not raw shell commands. Observed repository allowlist at rebuild time:
#   node_syntax_autopilot_scripts
#   no_production_activation_flag
# Raw commands such as "python scripts/..." fail as test_not_whitelisted before PR creation.
ALLOWED_RECEIVER_TEST_NAMES = {"node_syntax_autopilot_scripts", "no_production_activation_flag"}
PROTECTED_PATH_PARTS = (
    "Engine_2026-06-07_STABLE", ".github/workflows/", ".git/", ".env",
    "canonical workbook", "Canonical Workbook"
)

@dataclass
class ContractResult:
    ok: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, Any]


def compact_json_bytes(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")


def repository_dispatch_payload(command: Dict[str, Any]) -> Dict[str, Any]:
    # Mirrors the observed Pipedream v60 pattern: client_payload: {command}
    return {"command": command}


def dispatch_payload_size(command: Dict[str, Any]) -> int:
    return len(compact_json_bytes(repository_dispatch_payload(command)))


def body_envelope(command: Dict[str, Any], pretty: bool = True) -> str:
    json_body = json.dumps(command, indent=2 if pretty else None, sort_keys=True)
    return f"BEGIN_F1_AUTOPILOT_COMMAND\n{json_body}\nEND_F1_AUTOPILOT_COMMAND\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_patch_command(command: Dict[str, Any]) -> ContractResult:
    errors: List[str] = []
    warnings: List[str] = []
    metrics: Dict[str, Any] = {}
    for field in DEFAULT_REQUIRED_PATCH_FIELDS:
        if field not in command or command.get(field) in (None, "", []):
            errors.append(f"missing_required_field:{field}")
    if command.get("command_type") != "assistant_patch":
        errors.append("command_type_not_assistant_patch")
    if command.get("safety_mode") not in PATCH_ALLOWED_SAFETY_MODES:
        errors.append(f"invalid_safety_mode:{command.get('safety_mode')}")
    target = command.get("target_branch", "")
    if not isinstance(target, str) or not target.startswith(ALLOWED_TARGET_PREFIXES):
        errors.append(f"invalid_target_branch_prefix:{target}")
    if command.get("base_branch") != "main":
        errors.append(f"invalid_base_branch:{command.get('base_branch')}")
    for flag in ["production_automation", "forecast_gate"]:
        if command.get(flag) != "OFF":
            errors.append(f"unsafe_{flag}:{command.get(flag)}")
    if command.get("promotion_status") != "NOT_PROMOTED":
        errors.append("promotion_status_not_not_promoted")
    if command.get("activation_status") != "NOT_ACTIVATED":
        errors.append("activation_status_not_not_activated")
    if command.get("stable_engine_modified") is True:
        errors.append("stable_engine_modified_true")
    if command.get("canonical_workbook_overwrite") is True:
        errors.append("canonical_workbook_overwrite_true")
    files = command.get("files") or []
    if not isinstance(files, list) or not files:
        errors.append("files_missing_or_not_list")
        files=[]
    expected_paths = command.get("expected_changed_files") or []
    actual_paths = []
    for i, f in enumerate(files):
        if not isinstance(f, dict):
            errors.append(f"files[{i}]_not_object")
            continue
        path = f.get("path")
        actual_paths.append(path)
        if not path:
            errors.append(f"files[{i}].missing_path")
        else:
            if any(part in path for part in PROTECTED_PATH_PARTS):
                errors.append(f"files[{i}].protected_path:{path}")
        if f.get("action") not in PATCH_ALLOWED_ACTIONS:
            errors.append(f"files[{i}].unsupported_or_missing_action:{f.get('action')}")
        c64 = f.get("content_base64")
        if not c64:
            errors.append(f"files[{i}].missing_content_base64")
        else:
            try:
                decoded = base64.b64decode(c64, validate=True)
            except Exception:
                errors.append(f"files[{i}].invalid_content_base64")
                decoded = b""
            if "content_sha256" in f and hashlib.sha256(decoded).hexdigest() != f.get("content_sha256"):
                errors.append(f"files[{i}].content_sha256_mismatch")
            if "content_byte_length" in f and len(decoded) != f.get("content_byte_length"):
                errors.append(f"files[{i}].content_byte_length_mismatch")
    if expected_paths and sorted(expected_paths) != sorted(actual_paths):
        errors.append("expected_changed_files_mismatch")
    if command.get("expected_changed_file_count") is not None and command.get("expected_changed_file_count") != len(files):
        errors.append("expected_changed_file_count_mismatch")
    tests = command.get("tests", [])
    if tests is None:
        tests = []
    if not isinstance(tests, list):
        errors.append("tests_not_list")
    else:
        for i, test_name in enumerate(tests):
            if not isinstance(test_name, str) or not test_name:
                errors.append(f"tests[{i}]_not_string")
            elif test_name not in ALLOWED_RECEIVER_TEST_NAMES:
                errors.append(f"tests[{i}].not_whitelisted:{test_name}")
        metrics["requested_test_count"] = len(tests)
        if not tests:
            warnings.append("no_receiver_tests_requested; local test evidence must be included for sandbox-only packages")
    payload_size = dispatch_payload_size(command)
    body_size = len(body_envelope(command, pretty=True).encode("utf-8"))
    compact_command_size = len(compact_json_bytes(command))
    metrics.update({
        "file_count": len(files),
        "compact_command_bytes": compact_command_size,
        "repository_dispatch_payload_bytes": payload_size,
        "pretty_email_body_bytes": body_size,
        "payload_budget_bytes": MAX_GITHUB_DISPATCH_CLIENT_PAYLOAD_BYTES,
    })
    if payload_size > MAX_GITHUB_DISPATCH_CLIENT_PAYLOAD_BYTES:
        errors.append(f"repository_dispatch_payload_oversize:{payload_size}>{MAX_GITHUB_DISPATCH_CLIENT_PAYLOAD_BYTES}")
    elif payload_size > 55000:
        warnings.append(f"repository_dispatch_payload_near_limit:{payload_size}")
    return ContractResult(ok=not errors, errors=errors, warnings=warnings, metrics=metrics)


def validate_merge_command(command: Dict[str, Any]) -> ContractResult:
    errors: List[str] = []
    warnings: List[str] = []
    metrics: Dict[str, Any] = {"compact_command_bytes": len(compact_json_bytes(command))}
    required = ["schema_name","schema_version","command_type","safety_mode","repository","pull_number","expected_base","expected_head_prefixes","allowed_author_logins","allowed_path_prefixes","merge_method"]
    for field in required:
        if field not in command or command.get(field) in (None, "", []):
            errors.append(f"missing_required_field:{field}")
    if command.get("command_type") != "assistant_merge_pr":
        errors.append("command_type_not_assistant_merge_pr")
    if command.get("safety_mode") != "approved_merge_gate":
        errors.append("invalid_merge_safety_mode")
    if command.get("expected_base") != "main":
        errors.append("invalid_expected_base")
    if command.get("merge_method") not in {"squash", "merge", "rebase"}:
        errors.append("invalid_merge_method")
    if command.get("production_automation") != "OFF" or command.get("forecast_gate") != "OFF":
        errors.append("unsafe_activation_flags")
    if command.get("promotion_status") != "NOT_PROMOTED" or command.get("activation_status") != "NOT_ACTIVATED":
        errors.append("unsafe_promotion_or_activation_status")
    if not command.get("expected_head_sha"):
        warnings.append("expected_head_sha_missing; v26R2 recommends bridge support for sha-locked merge")
    return ContractResult(ok=not errors, errors=errors, warnings=warnings, metrics=metrics)
