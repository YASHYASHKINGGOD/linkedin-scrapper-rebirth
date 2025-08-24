# DESIGN — Scraper (Playwright)

Goals
- Reliable scraping of LinkedIn job and post pages with low local concurrency
- Persist full-fidelity raw artifacts and metadata
- Integrate cleanly with router, scheduler, and downstream extractor

Non-goals
- General-purpose crawling; proxy rotation in local mode

Architecture
- Workers: job scraper and post scraper (separate queues)
- Storage: HTML/PNG to ./storage; metadata to *_raw tables
- Orchestration: queue-first via Celery; router feeds scrape.job and scrape.post
- Observability: counters, durations, Flower; later add tracing/Prom metrics

Key flows
1) Dev single URL (scraper.dev) → Playwright → write artifacts → upsert *_raw
2) Queue path: router → scrape.* → worker claims row → Playwright → artifacts → *_raw → status transitions

Data model
- linkedin_jobs_raw(link_id, job_url, html_object_key, snapshot_object_key, raw_json, scraped_at, scrape_status, ...)
- linkedin_posts_raw(link_id, post_url, html_object_key, snapshot_object_key, raw_json, scraped_at, scrape_status, ...)

Idempotency
- Upsert *_raw by link_id; optional fingerprint hash to skip within TTL

Retries & backoff
- Exponential backoff; max attempts; move to dead on permanent errors

Acceptance
- Single URL scrape succeeds and persists
- Batch of 5 maintains ≥80% success, obeys rate limits
- Queue integration produces and consumes tasks with correct state transitions

