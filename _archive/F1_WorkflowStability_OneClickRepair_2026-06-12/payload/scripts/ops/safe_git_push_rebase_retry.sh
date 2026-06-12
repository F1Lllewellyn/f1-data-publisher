#!/usr/bin/env bash
# F1 safe git push helper: serializes/pulls/retries commit-producing GitHub Actions safely.
set -euo pipefail

BRANCH="${GITHUB_REF_NAME:-main}"
MAX_ATTEMPTS="${F1_SAFE_PUSH_ATTEMPTS:-3}"

echo "[f1-safe-push] branch=${BRANCH}"
git status --short || true

# If there is nothing to push, exit cleanly.
if git diff --quiet HEAD origin/"${BRANCH}" 2>/dev/null; then
  echo "[f1-safe-push] local HEAD already matches origin/${BRANCH}; nothing to push."
  exit 0
fi

for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
  echo "[f1-safe-push] push attempt ${attempt}/${MAX_ATTEMPTS}"
  if git push origin "HEAD:${BRANCH}"; then
    echo "[f1-safe-push] push succeeded"
    exit 0
  fi

  echo "[f1-safe-push] push failed; fetching and rebasing onto origin/${BRANCH}"
  git fetch origin "${BRANCH}"

  if git rebase "origin/${BRANCH}"; then
    echo "[f1-safe-push] rebase succeeded; retrying"
  else
    echo "[f1-safe-push] rebase failed. Aborting rebase and refusing unsafe push."
    git rebase --abort || true
    exit 1
  fi

  sleep $((attempt * 2))
done

echo "[f1-safe-push] failed after ${MAX_ATTEMPTS} attempts"
exit 1
