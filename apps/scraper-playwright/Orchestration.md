# Orchestration — Scraper (Playwright)

Queues & messages
- Input: scrape.job, scrape.post
- Message shape:
  {
    "link_id": 12345,
    "url": "https://www.linkedin.com/jobs/view/123/",
    "type": "job",        // or "post"
    "attempt": 1,
    "trace_id": "..."
  }
- Output events:
  - scrape.started {link_id, url, started_at}
  - scrape.succeeded {link_id, html_path, screenshot_path, http_status, duration_ms}
  - scrape.failed {link_id, reason, attempt, next_attempt_at}

State machine (per link)
- queued → scraping → scraped | error | dead
- On start: atomic claim (set status='scraping' if eligible; else skip)
- On success: set status='scraped'
- On failure: set status='error', set next_attempt_at with exponential backoff; after max attempts → dead

Idempotency & overwrite
- *_raw tables keyed by link_id; safe upsert
- Optional fingerprint hash to skip unchanged content within TTL

Concurrency & rate limits
- Local: concurrency 1–2 per queue
- Random jitter between steps; token-bucket QPS cap

Observability
- Counters: scrape_started, scrape_succeeded, scrape_failed
- Histogram: scrape_duration_ms
- Tracing: propagate trace_id

Data model alignment
- Use DESIGN.md *_raw schemas (jobs/posts)
- Persist artifact paths under ./storage and record in *_raw rows

