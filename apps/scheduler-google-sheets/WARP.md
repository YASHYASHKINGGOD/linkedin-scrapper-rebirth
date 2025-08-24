# WARP.md — Scheduler (Google Sheets → DB)

Purpose
- App-level rules and workflow for the Celery-based scheduler that periodically ingests Google Sheets links and upserts into Postgres. CSV is ancillary (optional backup). DB is the source of truth.

Rule precedence
- These app rules complement, but do not override, the root WARP.md.
- Follow root repo rules first (daily loop, safety, versioning), then apply specifics here.

Daily loop (for this app)
1) Start: read root WARP.md, DESIGN.md, orchestration.md (root), then this WARP.md, Orchestration.md, OperatingManual.md
2) Plan: pick next task from apps/scheduler-google-sheets/Tasks.md; define micro-steps
3) Implement with small commits on the scheduler branch; keep `make check` green at root
4) Update docs: apps/scheduler-google-sheets/Tasks.md and apps/scheduler-google-sheets/CLAUDE.md
5) Verify reproducibility (local): Redis up; Celery worker + Celery beat start; dry-run pipeline succeeds

Makefile alignment (local)
- Root Makefile remains the contract (setup, fmt, lint, typecheck, test, check)
- This app will introduce worker and beat targets when code lands (pending):
  - celery.worker — start worker with low concurrency (2–4)
  - celery.beat — start beat scheduler
  - scheduler.start — convenience (run both; developer runs in separate terminals)

Scope (this app)
- Schedule: every N minutes (default 10–15m; exact via env)
- Pipeline per run: ingest links → DB upsert → classify+queue; all idempotent
- Broker: Redis (local). Result backend: Redis or disabled

Safety & compliance
- Respect Google API quotas and rate limits; keep low concurrency
- Secrets via .env (local only); never commit real secrets
- PII: none expected for this stage; still sanitize logs

Verification checklist (docs stage)
- This directory exists with WARP.md, Orchestration.md, OperatingManual.md, README.md, CLAUDE.md, Tasks.md
- No code has been added yet; only docs

Verification checklist (once code is added)
- Redis reachable locally
- Celery worker starts without error
- Celery beat schedules the pipeline task at the desired interval
- One pipeline run upserts rows into Postgres (DATABASE_URL set), classification runs, no duplicates (unique on canonical URL)
- Optional: backup CSV artifact written under ./storage/backups

References
- Root WARP.md for project-wide rules
- “celery-setup-main” reference for celery app structure (to be mirrored when we implement code)

