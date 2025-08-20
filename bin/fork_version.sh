#!/usr/bin/env bash
set -euo pipefail
APP="${1:-}"; FROM_VER="${2:-}"; NEW_BRANCH="${3:-}"
if [[ -z "$APP" || -z "$FROM_VER" || -z "$NEW_BRANCH" ]]; then
  echo "Usage: $0 <app-name> <from-version> <new-branch>"; exit 1; fi
TAG="${APP}-v${FROM_VER}"
git rev-parse "refs/tags/${TAG}" >/dev/null 2>&1 || { echo "Tag ${TAG} not found"; exit 1; }
git branch -f "$NEW_BRANCH" "refs/tags/${TAG}"
mkdir -p .worktrees
git worktree add ".worktrees/${NEW_BRANCH}" "$NEW_BRANCH"
echo "🌱 Forked ${TAG} -> branch ${NEW_BRANCH} @ .worktrees/${NEW_BRANCH}"
