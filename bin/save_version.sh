#!/usr/bin/env bash
set -euo pipefail
APP="${1:-}"; VER="${2:-}"; MSG="${3:-"save: $APP $VER"}"
if [[ -z "$APP" || -z "$VER" ]]; then echo "Usage: $0 <app-name> <version> [message]"; exit 1; fi
git rev-parse --git-dir >/dev/null 2>&1 || { echo "Not a git repo"; exit 1; }
if [[ -n "$(git status --porcelain)" ]]; then echo "Working tree is dirty. Commit/stash first."; exit 1; fi
[[ -d "apps/$APP" ]] || { echo "apps/$APP not found"; exit 1; }
TAG="${APP}-v${VER}"
git tag -a "$TAG" -m "$MSG"
OUT_DIR="${HOME}/.app_versions"; mkdir -p "$OUT_DIR"
git archive --format=tar.gz --prefix="${APP}/" -o "${OUT_DIR}/${TAG}.tar.gz" "$TAG"
echo "✅ Saved tag: $TAG | 📦 ${OUT_DIR}/${TAG}.tar.gz"
