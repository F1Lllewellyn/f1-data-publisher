#!/usr/bin/env python3
"""F1 v33D advisory AI PR and failed-log reviewer.

This script is deliberately advisory by default:
- It never calls GitHub's merge endpoint.
- It never writes repository contents.
- It posts PR comments only when GitHub supplies a PR context.
- It exits non-zero only when AI_REVIEW_ENFORCEMENT=blocking and the verdict is BLOCK.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.request
import zipfile
from typing import Any


VERSION = "v33D"
COMMENT_MARKER = "<!-- f1-ai-pr-log-advisory-reviewer-v33d -->"
MAX_DIFF_CHARS = 60000
MAX_LOG_CHARS = 12000

PROTECTED_MARKERS = [
    "Engine_2026-06-07_STABLE",
    "canonical",
    "backups/",
    "source archives/",
    "source_archives/",
    "stable model",
    "stable_engine",
    "secrets/",
    "tokens/",
    ".env",
    "password",
    "private_key",
]

ALLOWED_PATCH_ROOTS = [
    ".github/workflows/",
    "config/",
    "docs/",
    "processor/",
    "schemas/",
    "scripts/",
    "health/",
    "logs/",
]


def env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def load_event() -> dict[str, Any]:
    manual = env("MANUAL_EVENT_JSON").strip()
    raw = manual or env("EVENT_CONTEXT").strip() or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"_decode_error": str(exc), "_raw_prefix": raw[:500]}


def github_headers() -> dict[str, str]:
    token = env("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "f1-ai-pr-log-advisory-reviewer-v33d",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def request_text(url: str, *, accept: str | None = None) -> str:
    headers = github_headers()
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = github_headers()
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else {}


def request_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def extract_changed_paths_from_diff(diff_text: str) -> list[str]:
    paths: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            match = re.search(r" b/(.+)$", line)
            if match:
                paths.append(match.group(1))
    return sorted(set(paths))


def governance_findings(paths: list[str]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/").lstrip("./")
        low = normalized.lower()
        if not any(normalized.startswith(root) for root in ALLOWED_PATCH_ROOTS):
            findings.append(f"path_outside_pr_only_roots:{normalized}")
        for marker in PROTECTED_MARKERS:
            if marker.lower() in low:
                findings.append(f"protected_marker:{marker}:{normalized}")
        if normalized.startswith(".github/workflows/"):
            findings.append(f"workflow_change_requires_operator_review:{normalized}")
    return sorted(set(findings))


def call_openai(system_prompt: str, user_prompt: str) -> str:
    api_key = env("OPENAI_API_KEY")
    if not api_key:
        return "VERDICT: REVIEW_REQUIRED\n\n- AI review skipped: OPENAI_API_KEY is not configured."

    model = env("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "f1-ai-pr-log-advisory-reviewer-v33d",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001 - advisory reviewer must not hide transport failures.
        return f"VERDICT: REVIEW_REQUIRED\n\n- AI review transport failed: {type(exc).__name__}: {exc}"


def verdict_from_text(text: str) -> str:
    first = text.strip().splitlines()[0].strip().upper() if text.strip() else ""
    if first == "VERDICT: PASS":
        return "PASS"
    if first == "VERDICT: BLOCK":
        return "BLOCK"
    return "REVIEW_REQUIRED"


def pr_system_prompt() -> str:
    return textwrap.dedent(
        """
        You are the F1 Prediction Engine advisory PR reviewer.

        First line must be exactly one of:
        VERDICT: PASS
        VERDICT: REVIEW_REQUIRED
        VERDICT: BLOCK

        Rules:
        - Advisory only: do not suggest or perform merging.
        - BLOCK only for likely breakage, protected-path touch, secret exposure, destructive behavior, production activation, workbook/canonical overwrite, model promotion, or unsafe automation escalation.
        - REVIEW_REQUIRED for workflow/config/governance changes, unclear behavior, missing tests, or non-trivial risk.
        - PASS only when changes are low-risk and consistent with F1 governance.
        - Do not claim predictive accuracy improvement.
        - Treat Engine_2026-06-07_STABLE and canonical workbook paths as protected.
        """
    ).strip()


def log_system_prompt() -> str:
    return textwrap.dedent(
        """
        You are the F1 Prediction Engine advisory CI log verifier.

        First line must be exactly one of:
        VERDICT: PASS
        VERDICT: REVIEW_REQUIRED
        VERDICT: BLOCK

        Provide concise RCA:
        - failing component
        - most likely root cause
        - minimal safe fix
        - whether this blocks merge/retry
        """
    ).strip()


def post_or_update_pr_comment(repo: str, pr_number: int, body: str) -> None:
    if not env("GITHUB_TOKEN"):
        return
    owner_repo = repo.strip("/")
    comments_url = f"https://api.github.com/repos/{owner_repo}/issues/{pr_number}/comments"
    try:
        comments = request_json(comments_url)
        for comment in comments:
            if COMMENT_MARKER in str(comment.get("body", "")):
                request_json(comment["url"], method="PATCH", payload={"body": body})
                return
        request_json(comments_url, method="POST", payload={"body": body})
    except Exception as exc:  # noqa: BLE001
        append_summary(f"Comment post/update failed: {type(exc).__name__}: {exc}\n")


def append_summary(markdown: str) -> None:
    summary_path = env("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(markdown)
    else:
        print(markdown)


def handle_pull_request(event: dict[str, Any]) -> str:
    pr = event.get("pull_request") or {}
    repo = (event.get("repository") or {}).get("full_name") or env("GITHUB_REPOSITORY")
    number = int(pr.get("number") or 0)
    diff_url = pr.get("diff_url")
    title = pr.get("title", "")

    if not diff_url:
        result = "VERDICT: REVIEW_REQUIRED\n\n- Missing pull_request.diff_url; unable to inspect diff."
    else:
        try:
            diff_text = request_text(diff_url, accept="application/vnd.github.v3.diff")
        except Exception as exc:  # noqa: BLE001
            diff_text = ""
            result = f"VERDICT: REVIEW_REQUIRED\n\n- Failed to fetch PR diff: {type(exc).__name__}: {exc}"
        else:
            changed_paths = extract_changed_paths_from_diff(diff_text)
            findings = governance_findings(changed_paths)
            prompt = textwrap.dedent(
                f"""
                PR title: {title}
                PR number: {number}
                Changed paths:
                {json.dumps(changed_paths, indent=2)}

                Deterministic governance findings:
                {json.dumps(findings, indent=2)}

                Diff, truncated to {MAX_DIFF_CHARS} chars:
                {diff_text[:MAX_DIFF_CHARS]}
                """
            ).strip()
            result = call_openai(pr_system_prompt(), prompt)
            if findings and verdict_from_text(result) == "PASS":
                result = "VERDICT: REVIEW_REQUIRED\n\n- Deterministic governance findings require operator review:\n" + "\n".join(
                    f"  - {item}" for item in findings
                ) + "\n\nAI review body:\n" + result

    verdict = verdict_from_text(result)
    body = f"{COMMENT_MARKER}\n### F1 Advisory AI PR Review ({VERSION})\n\n{result}\n\nAdvisory mode: no merge authority."
    append_summary(body + "\n")
    if repo and number:
        post_or_update_pr_comment(repo, number, body)
    return verdict


def collect_failure_log_summary(event: dict[str, Any]) -> tuple[str, list[int]]:
    run = event.get("workflow_run") or {}
    repo = (run.get("repository") or event.get("repository") or {}).get("full_name") or env("GITHUB_REPOSITORY")
    run_id = run.get("id")
    pr_numbers = [int(item.get("number")) for item in run.get("pull_requests", []) if item.get("number")]
    if not repo or not run_id:
        return "missing repository or workflow_run.id", pr_numbers
    logs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/logs"
    try:
        blob = request_bytes(logs_url)
    except Exception as exc:  # noqa: BLE001
        return f"failed to download logs: {type(exc).__name__}: {exc}", pr_numbers

    snippets: list[str] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            if not name.endswith(".txt"):
                continue
            text = zf.read(name).decode("utf-8", errors="replace")
            error_lines = [
                line
                for line in text.splitlines()
                if any(token in line.lower() for token in ["error", "exception", "failed", "fatal", "traceback"])
            ]
            if error_lines:
                snippets.append(f"--- {name} ---\n" + "\n".join(error_lines[-40:]))
    return ("\n\n".join(snippets) or "No explicit error/exception/failed lines found.")[:MAX_LOG_CHARS], pr_numbers


def handle_workflow_run(event: dict[str, Any]) -> str:
    run = event.get("workflow_run") or {}
    repo = (run.get("repository") or event.get("repository") or {}).get("full_name") or env("GITHUB_REPOSITORY")
    conclusion = run.get("conclusion")
    if conclusion != "failure":
        result = f"VERDICT: PASS\n\n- Workflow conclusion was {conclusion}; no failed-log RCA needed."
        append_summary(result + "\n")
        return "PASS"

    summary, pr_numbers = collect_failure_log_summary(event)
    prompt = textwrap.dedent(
        f"""
        Workflow: {run.get('name')}
        Run id: {run.get('id')}
        Conclusion: {conclusion}
        Head branch: {run.get('head_branch')}
        Head sha: {run.get('head_sha')}

        Failure log summary:
        {summary}
        """
    ).strip()
    result = call_openai(log_system_prompt(), prompt)
    verdict = verdict_from_text(result)
    body = f"{COMMENT_MARKER}\n### F1 Advisory Failed-Log RCA ({VERSION})\n\n{result}\n\nAdvisory mode: no merge authority."
    append_summary(body + "\n")
    if repo:
        for number in pr_numbers:
            post_or_update_pr_comment(repo, number, body)
    return verdict


def main() -> int:
    event = load_event()
    event_name = env("GITHUB_EVENT_NAME")
    if event.get("_decode_error"):
        append_summary(f"VERDICT: REVIEW_REQUIRED\n\n- Event JSON decode error: {event['_decode_error']}\n")
        return 0

    if event_name == "pull_request" or "pull_request" in event:
        verdict = handle_pull_request(event)
    elif event_name == "workflow_run" or "workflow_run" in event:
        verdict = handle_workflow_run(event)
    else:
        append_summary("VERDICT: REVIEW_REQUIRED\n\n- Unsupported event for advisory AI review.\n")
        verdict = "REVIEW_REQUIRED"

    if env("AI_REVIEW_ENFORCEMENT", "advisory").lower() == "blocking" and verdict == "BLOCK":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
