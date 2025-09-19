# Operating Manual — Scraper (Playwright)

Overview
- Scrapes LinkedIn job and post pages with Playwright. Writes HTML + screenshot to ./storage and metadata to Postgres *_raw tables.

Prereqs
- make setup; python -m pip install -r requirements.txt
- python -m playwright install (download Chromium)
- Redis and Postgres available; .env configured

Environment
- DATABASE_URL=postgresql://user:pass@localhost:5432/data_lake
- SCRAPER_CONCURRENCY=1
- SCRAPER_HEADLESS=true
- SCRAPER_RATE_QPS=0.2
- SCRAPER_OUT_DIR=./storage/scrape
- QUEUES=scrape.job,scrape.post

Start
- Worker: make scraper.worker
- Dev (single URL, headed): make scraper.dev URL="https://www.linkedin.com/jobs/view/..."

Manual run (no queue, MVP)
- Select a queued row or supply a single URL to the dev command and write outputs

Runbooks
- Captcha or 429: reduce concurrency; increase jitter; back off retries; use cached HTML if present
- Stuck in scraping: after 30m, reset to queued and increment attempt_count
- Failures: set status='error' and compute next_attempt_at via exponential backoff
- Playwright errors: rerun with headed mode; check browser install and sandbox flags

Acceptance checks
- Artifacts written under SCRAPER_OUT_DIR
- *_raw row upserted with link_id and paths
- Metrics counters increment; Flower shows task history

