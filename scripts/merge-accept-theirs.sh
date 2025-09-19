#!/bin/bash
# Helper script to accept "theirs" for specific file patterns
# Usage: ./merge-accept-theirs.sh <branch_name>

set -euo pipefail

BRANCH=${1:-"unknown"}

case "$BRANCH" in
  "extractor-google-sheets")
    echo "📁 Accepting theirs for extractor-google-sheets files..."
    git checkout --theirs -- src/extractor/google_sheets/ 2>/dev/null || true
    git checkout --theirs -- src/clients/google_sheets.py 2>/dev/null || true
    git checkout --theirs -- src/ingest/ 2>/dev/null || true
    git checkout --theirs -- src/db/import_and_backup.py 2>/dev/null || true
    git checkout --theirs -- src/db/classify_and_queue.py 2>/dev/null || true
    git checkout --theirs -- tests/test_google_sheets* 2>/dev/null || true
    git checkout --theirs -- tests/test_io_write_csv.py 2>/dev/null || true
    git checkout --theirs -- tests/test_dedupe.py 2>/dev/null || true
    ;;
  "pipeline-linkedin-posts")
    echo "📁 Accepting theirs for pipeline-linkedin-posts files..."
    git checkout --theirs -- src/routers/posts_router.py 2>/dev/null || true
    git checkout --theirs -- src/workers/posts_worker.py 2>/dev/null || true
    git checkout --theirs -- src/pipeline/orchestrator.py 2>/dev/null || true
    git checkout --theirs -- src/db/migrations/create_posts_table.py 2>/dev/null || true
    git checkout --theirs -- apps/scraper-playwright/posts/ 2>/dev/null || true
    git checkout --theirs -- async_database_scraper.py 2>/dev/null || true
    git checkout --theirs -- src/db/import_and_backup.py 2>/dev/null || true
    git checkout --theirs -- src/db/classify_and_queue.py 2>/dev/null || true
    ;;
  "scraper-jobs-integrate")
    echo "📁 Accepting theirs for scraper-jobs-integrate files..."
    git checkout --theirs -- src/router/route.py 2>/dev/null || true
    git checkout --theirs -- src/scraper/tasks.py 2>/dev/null || true
    git checkout --theirs -- apps/scraper-playwright/jobs/ 2>/dev/null || true
    ;;
  "scheduler-gooogle-sheets")
    echo "📁 Accepting theirs for scheduler-gooogle-sheets files..."
    git checkout --theirs -- src/scheduler_gs/ 2>/dev/null || true
    ;;
  *)
    echo "❌ Unknown branch: $BRANCH"
    echo "Usage: $0 <branch_name>"
    echo "Supported branches: extractor-google-sheets, pipeline-linkedin-posts, scraper-jobs-integrate, scheduler-gooogle-sheets"
    exit 1
    ;;
esac

echo "✅ Completed accepting theirs for $BRANCH"