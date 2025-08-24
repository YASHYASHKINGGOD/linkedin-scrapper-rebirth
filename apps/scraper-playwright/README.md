# README — Scraper (Playwright)

This app scrapes LinkedIn job and post pages using Playwright and persists raw artifacts to ./storage and Postgres *_raw tables.

Quickstart
1) Install deps
   - make setup
   - python -m pip install -r requirements.txt
   - python -m playwright install
2) Env
   - export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/data_lake
3) Run
   - make scraper.dev URL="https://www.linkedin.com/jobs/view/..."   # single URL, headed
   - make scraper.worker                                          # consumes scrape.job, scrape.post

Docs
- WARP.md — app rules
- Orchestration.md — queues, messages, state transitions
- OperatingManual.md — runbooks
- Tasks.md — backlog
- CLAUDE.md — notes

