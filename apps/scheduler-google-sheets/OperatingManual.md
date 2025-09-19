# Operating Manual — Scheduler (Google Sheets → DB)

Overview
- This app runs a Celery Beat scheduler and a Celery worker to periodically ingest links from Google Sheets and upsert them into Postgres.
- DB writes are idempotent (unique on canonical URL). CSV backups are optional.

Prereqs
- Python deps installed (root make setup)
- Redis running locally (broker + optional result backend)
- Postgres reachable via DATABASE_URL

Environment variables (local)
- DATABASE_URL=postgresql://user:pass@localhost:5432/your_db
- CELERY_BROKER_URL=redis://localhost:6379/0
- CELERY_RESULT_BACKEND=redis://localhost:6379/1
- SCHEDULER_INTERVAL_SECS=900  # or CELERY_CRON like "*/15 * * * *"
- MONTH_FILTER=aug
- GOOGLE_SHEETS_URLS="url1,url2"
- SHEETS_CONFIG=./config/sheets.yaml  # optional

Start (dev)
1) Start Redis
   - Docker: docker run --rm -p 6379:6379 redis:7
   - Or Homebrew: brew services start redis
2) Start worker (terminal A)
   - make celery.worker
3) Start beat (terminal B)
   - make celery.beat
4) Verify: logs show periodic pipeline runs

Operational notes
- Concurrency: keep small (2–4). Increase only after verifying rate limits.
- Failures: transient errors should auto-retry (Celery). Permanent DB constraints are no-ops.
- Backups: if enabled, CSVs stored under ./storage/backups/ (timestamped).

Runbooks
- Pipeline stuck or failing repeatedly
  - Check Redis connectivity
  - Verify Google OAuth token exists and not expired
  - Check DATABASE_URL creds and connectivity
  - Inspect Celery logs for tracebacks
- Clean retry
  - Restart worker and beat; ensure Redis is clean if necessary
- Adjust schedule
  - Update SCHEDULER_INTERVAL_SECS or CELERY_CRON and restart beat

Security & compliance
- Do not commit real secrets; use .env locally
- Respect Google API quotas; keep concurrency low
- Mask any sensitive values in logs

Acceptance checks (manual)
- After one scheduled run, verify rows exist or updated in public.linkedin_links
- Status transitioned to 'queued' when applicable
- No duplicate entries for same canonical URL

