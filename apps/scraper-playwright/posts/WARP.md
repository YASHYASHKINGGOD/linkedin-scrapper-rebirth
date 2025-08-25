# Posts Scraper (Playwright) — WARP.md

Purpose
- Extend the existing scraper app to support LinkedIn posts scraping with authentication, low concurrency, and strong rate limiting.
- Outputs CSV (single file with JSON columns) and artifacts (HTML, screenshot, downloaded images) under ./storage.

Rule precedence
- Inherits root WARP.md. These app-slice rules complement, not override.

Daily loop
1) Read root WARP.md, DESIGN.md, orchestration.md, and these posts docs.
2) Pick the next task from Tasks.md; define micro-steps.
3) Implement with small commits; keep `make check` green.
4) Update docs: Tasks.md and CLAUDE.md; add session log at repo root if applicable.
5) Verify: `make setup && make check && make start`.

Safety & compliance
- Respect site terms and rate limits; local-only, no proxies.
- Secrets not in repo. Use env vars for credentials; prefer user-data-dir sessions.
- PII masked in logs; artifacts under ./storage.

Verification checklist
- Playwright browsers installed (`python -m playwright install`).
- `make posts.dev URL=...` saves HTML+PNG+images and appends to CSV.
- `make posts.batch INPUT=./links.txt` processes first 5 links headless with comments cap=20.
- Default concurrency=1 and ~0.2 QPS; no 429s at defaults.

