#!/bin/bash
# Helper script to accept "ours" (main/current) for specific files
# Usage: ./merge-accept-ours.sh <branch_name>

set -euo pipefail

BRANCH=${1:-"unknown"}

case "$BRANCH" in
  "extractor-google-sheets")
    echo "📁 Accepting ours for main/shared files during extractor-google-sheets merge..."
    git checkout --ours -- src/app.py 2>/dev/null || true
    git checkout --ours -- Makefile 2>/dev/null || true
    git checkout --ours -- .gitignore 2>/dev/null || true
    ;;
  "pipeline-linkedin-posts")
    echo "📁 Accepting ours for preserved files during pipeline-linkedin-posts merge..."
    git checkout --ours -- src/app.py 2>/dev/null || true  # Keep extractor's version
    git checkout --ours -- .gitignore 2>/dev/null || true
    ;;
  "scraper-jobs-integrate")
    echo "📁 Accepting ours for preserved files during scraper-jobs-integrate merge..."
    git checkout --ours -- src/routers/posts_router.py 2>/dev/null || true  # Keep pipeline's
    git checkout --ours -- src/workers/posts_worker.py 2>/dev/null || true   # Keep pipeline's
    git checkout --ours -- .gitignore 2>/dev/null || true
    ;;
  "scheduler-gooogle-sheets")
    echo "📁 Accepting ours for preserved files during scheduler-gooogle-sheets merge..."
    git checkout --ours -- src/router/route.py 2>/dev/null || true  # Keep scraper-jobs'
    git checkout --ours -- .gitignore 2>/dev/null || true
    ;;
  *)
    echo "❌ Unknown branch: $BRANCH"
    echo "Usage: $0 <branch_name>"
    echo "Supported branches: extractor-google-sheets, pipeline-linkedin-posts, scraper-jobs-integrate, scheduler-gooogle-sheets"
    exit 1
    ;;
esac

echo "✅ Completed accepting ours for shared files during $BRANCH merge"