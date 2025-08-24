# Orchestration — Scheduler (Google Sheets → DB)

Goal
- Periodically ingest LinkedIn links from configured Google Sheets, upsert into Postgres (idempotent), and classify+queue downstream work.

Stages per run
1) Ingest: fetch tab(s) for month (e.g., "aug"), extract LinkedIn URLs, dedupe (preserve first-seen)
2) Upsert: ON CONFLICT (url_canonical) into public.linkedin_links; set provenance columns when available
3) Classify + Queue: set classification job|post|unknown and status='queued'; emit idempotent events

Schedule
- Default: every 10–15 minutes (configurable via env) using Celery Beat
- Cadence controlled via interval or crontab; URLs resolved from env or config file

Message shapes (conceptual)
- Not using an external message bus at this stage; Celery task args encapsulate:
  - urls: list[str]
  - month_filter: str
  - minutes_for_backup: int

Idempotency
- Unique key: linkedin_links.url_canonical (generated from lower(url))
- Re-running a pipeline does not duplicate rows; provenance may update

Retry policy
- Transient failures (network, API) retried with exponential backoff within Celery
- DB constraint violations are expected no-ops (idempotent upsert)

Back-pressure & limits
- Low concurrency by default (2–4 workers)
- Respect Google API quotas; consider simple rate-limits if needed (later)

Observability (initial)
- Logs per task with key inputs/outputs and durations
- Add metrics/tracing later; keep code structured for easy insertion

Config (env)
- DATABASE_URL=postgresql://user:pass@localhost:5432/db
- CELERY_BROKER_URL=redis://localhost:6379/0
- CELERY_RESULT_BACKEND=redis://localhost:6379/1
- SCHEDULER_INTERVAL_SECS=900 (or CELERY_CRON="*/15 * * * *")
- MONTH_FILTER=aug
- GOOGLE_SHEETS_URLS="url1,url2,..." (optional)
- SHEETS_CONFIG=./config/sheets.yaml (optional; merges with env)

Acceptance (per run)
- At least one of: new rows inserted OR existing rows updated (extracted_at advanced)
- Classification transitions 'new' → 'queued' when applicable
- No duplicate rows for the same canonical URL

Open items (to confirm at implementation time)
- Whether to skip writing transient CSVs entirely (direct DB upsert from rows)
- Whether to persist Celery results or disable backend for lower overhead

