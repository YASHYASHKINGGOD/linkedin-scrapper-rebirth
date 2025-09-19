# WARP.md — Scraper (Playwright)

Purpose
- App-level rules and workflow for scraping LinkedIn job and post pages using Playwright.
- Persist raw artifacts (HTML, screenshots, JSON) to ./storage and metadata into *_raw tables. DB is the source of truth.

Rule precedence
- Inherits root WARP.md rules (daily loop, make check, versioning, safety). These app rules complement, not override.

Daily loop (this app)
1) Start: read root WARP.md, DESIGN.md, orchestration.md, then this app’s docs (WARP, Orchestration, OperatingManual).
2) Pick the next task from apps/scraper-playwright/Tasks.md; define micro-steps.
3) Implement with small commits; keep `make check` green.
4) Update docs: Tasks.md and CLAUDE.md; add sessions/SESSION-YYYY-MM-DD.md at repo root if applicable.
5) Verify reproducibility locally: Playwright installed; scraper.dev works; scraper.worker processes at least one message; artifacts and *_raw rows present.

Makefile alignment (local)
- New targets (added at root):
  - scraper.worker — start worker for queues scrape.job and scrape.post with low concurrency
  - scraper.dev — headful one-off scrape for a single URL for debugging
  - scraper.test — run scraper tests (unit/integration)

Scope
- Job and post page scraping under low concurrency (1–2) in local mode; no proxies in local.
- Respect site terms & rate limits; random jitter; realistic UA.

Safety & compliance
- No real secrets in repo; use .env for local only.
- PII masked in logs; redact tokens/cookies; store artifacts locally under ./storage.

Verification checklist
- Playwright browsers installed (`python -m playwright install`).
- `make scraper.dev URL=...` saves HTML+PNG under ./storage/scrape/ and inserts row into *_raw.
- `make scraper.worker` consumes a task and transitions status queued → scraping → scraped.
- Metrics counters increment; Flower shows tasks in scrape queues.

