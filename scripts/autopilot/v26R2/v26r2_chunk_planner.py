"""Payload-budgeted sequential chunk planner for assistant_patch commands."""
from __future__ import annotations
from typing import Any, Dict, List
import copy, base64, hashlib, json
from v26r2_contracts import validate_patch_command, dispatch_payload_size

class ChunkingError(Exception):
    pass


def clone_base_command(command: Dict[str, Any]) -> Dict[str, Any]:
    c = copy.deepcopy(command)
    c["files"] = []
    c["expected_changed_files"] = []
    c["expected_changed_file_count"] = 0
    return c


def file_record_size(base: Dict[str, Any], f: Dict[str, Any]) -> int:
    tmp = clone_base_command(base)
    tmp["files"] = [f]
    tmp["expected_changed_files"] = [f["path"]]
    tmp["expected_changed_file_count"] = 1
    return dispatch_payload_size(tmp)


def plan_sequential_chunks(base_command: Dict[str, Any], threshold: int = 60000, branch_prefix: str | None = None) -> List[Dict[str, Any]]:
    files = base_command.get("files") or []
    if not files:
        raise ChunkingError("no_files")
    for f in files:
        tmp = clone_base_command(base_command)
        tmp["files"] = [f]
        tmp["expected_changed_files"] = [f["path"]]
        tmp["expected_changed_file_count"] = 1
        if dispatch_payload_size(tmp) > threshold:
            raise ChunkingError(f"single_file_exceeds_threshold:{f.get('path')}")
    chunks = []
    current = clone_base_command(base_command)
    idx = 1
    for f in files:
        candidate = copy.deepcopy(current)
        candidate["files"].append(f)
        candidate["expected_changed_files"].append(f["path"])
        candidate["expected_changed_file_count"] = len(candidate["files"])
        candidate["title"] = f"{base_command.get('title')} [{idx:02d}]"
        candidate["summary"] = f"Sequential v26R2 chunk {idx}; PR-only, payload-budgeted. " + base_command.get("summary", "")
        candidate["target_branch"] = f"{branch_prefix or base_command.get('target_branch')}-chunk-{idx:02d}"
        candidate["checkpoint"] = f"{base_command.get('checkpoint','V26R2')}-CHUNK-{idx:02d}"
        candidate["command_id"] = f"{base_command.get('command_id','V26R2')}-chunk-{idx:02d}"
        if dispatch_payload_size(candidate) <= threshold:
            current = candidate
        else:
            if not current["files"]:
                raise ChunkingError("cannot_place_file")
            chunks.append(current)
            idx += 1
            current = clone_base_command(base_command)
            current["files"] = [f]
            current["expected_changed_files"] = [f["path"]]
            current["expected_changed_file_count"] = 1
            current["title"] = f"{base_command.get('title')} [{idx:02d}]"
            current["summary"] = f"Sequential v26R2 chunk {idx}; PR-only, payload-budgeted. " + base_command.get("summary", "")
            current["target_branch"] = f"{branch_prefix or base_command.get('target_branch')}-chunk-{idx:02d}"
            current["checkpoint"] = f"{base_command.get('checkpoint','V26R2')}-CHUNK-{idx:02d}"
            current["command_id"] = f"{base_command.get('command_id','V26R2')}-chunk-{idx:02d}"
    if current["files"]:
        chunks.append(current)
    for c in chunks:
        result = validate_patch_command(c)
        if not result.ok:
            raise ChunkingError(f"chunk_validation_failed:{result.errors}")
    return chunks
