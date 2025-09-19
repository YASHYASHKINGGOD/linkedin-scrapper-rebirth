# README — Scheduler (Google Sheets → DB)

This app schedules periodic ingestion of LinkedIn links from Google Sheets and upserts them into Postgres using Celery (worker + beat) with Redis as the broker.

Status
- Docs-only scaffold. No Celery code added yet. Review and approve docs before implementation.

Quickstart (once code is added)
1) Ensure Python deps are installed at repo root: `make setup`
2) Start Redis:
   - Docker: `docker run --rm -p 6379:6379 redis:7`
   - Or Homebrew: `brew services start redis`
3) Export env (example):
   - `export DATABASE_URL=postgresql://user:pass@localhost:5432/data_lake`
   - `export CELERY_BROKER_URL=redis://localhost:6379/0`
   - `export CELERY_RESULT_BACKEND=redis://localhost:6379/1`
   - `export GOOGLE_SHEETS_URLS="https://docs.google.com/spreadsheets/d/AAA/edit#gid=111,https://docs.google.com/spreadsheets/d/BBB/edit#gid=222"`
   - `export MONTH_FILTER=aug`
   - `export SCHEDULER_INTERVAL_SECS=900`
4) Start services:
   - Terminal A: `make celery.worker`
   - Terminal B: `make celery.beat`

What will run per schedule
- Ingest links for configured sheets/tabs (month filter)
- Upsert into public.linkedin_links via ON CONFLICT (url_canonical)
- Classify and set status='queued'
- Optionally write a backup CSV under ./storage/backups/

Idempotency & safety
- Unique canonical URL; re-runs are safe
- Low concurrency by default

Docs
- WARP.md — app-specific rules
- Orchestration.md — schedule, stages, idempotency, retries
- OperatingManual.md — how to run and troubleshoot locally
- Tasks.md — backlog for the scheduler
- CLAUDE.md — handover notes

