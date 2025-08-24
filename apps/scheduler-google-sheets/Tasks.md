# Tasks.md — Scheduler (Google Sheets → DB)

Backlog
- [ ] Add Celery app (src/scheduler_gs/celery_app.py) wired to env for broker/backend/timezone
- [ ] Implement tasks (src/scheduler_gs/tasks.py): ingest links, DB upsert (idempotent), classify+queue, pipeline
- [ ] Beat schedule: interval or CRON-based; env-configurable; defaults to 15m
- [ ] Makefile targets: celery.worker, celery.beat, scheduler.start
- [ ] .env.example additions: DB URL, broker/backend, schedule vars; README examples
- [ ] Optional: docker-compose.dev.yml for Redis
- [ ] Logging: structured logging in tasks and pipeline
- [ ] Tests: unit tests for pipeline orchestration; mocks for IO/DB; optional smoke
- [ ] Docs: update acceptance criteria after first working run; add troubleshooting

In Progress
- [ ] Docs scaffold created; pending approval before implementation

Done
- [ ] Create apps/scheduler-google-sheets/ (WARP.md, Orchestration.md, OperatingManual.md, README.md, CLAUDE.md, Tasks.md)

