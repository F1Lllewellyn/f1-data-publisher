#!/usr/bin/env bash
set -euo pipefail

BRANCH="${GITHUB_REF_NAME:-main}"
MAX_ATTEMPTS="${F1_SAFE_PUSH_MAX_ATTEMPTS:-3}"
SLEEP_SECONDS="${F1_SAFE_PUSH_SLEEP_SECONDS:-3}"

echo "[f1-safe-push] branch=${BRANCH}"

git config pull.rebase true

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  echo "[f1-safe-push] push attempt ${attempt}/${MAX_ATTEMPTS}"
  if git push origin HEAD:"${BRANCH}"; then
    echo "[f1-safe-push] push succeeded"
    exit 0
  fi

  echo "[f1-safe-push] push rejected or failed; fetching/rebasing then retrying"
  git fetch origin "${BRANCH}" --depth=20 || git fetch origin "${BRANCH}"
  if ! git rebase "origin/${BRANCH}"; then
    echo "[f1-safe-push] rebase conflict; aborting safely"
    git rebase --abort || true
    exit 20
  fi
  sleep "$SLEEP_SECONDS"
done

echo "[f1-safe-push] failed after ${MAX_ATTEMPTS} attempts"
exit 21
