# WARP.md — First Read Rules and Workflow

Purpose
- This is the first document AI agents and contributors should read. It encodes project rules, daily loop, versioning, safety, and verification.

Rule precedence
- Project rules in this repo override personal rules
- Subdirectory rules override parent directory rules
- External rules referenced by the user: UI-INSTRUCTIONS.md (UI guidance) and neo-notes-handover.md (project instructions)

Daily loop
1) Start: read WARP.md, DESIGN.md, planning.md, tasks.md, README.md
2) Restate the next task and plan micro-steps
3) Implement with small commits; keep `make check` green
4) Update docs: tasks.md, sessions/SESSION-YYYY-MM-DD.md (from SESSION_TEMPLATE.md), and append a short note in CLAUDE.md
5) Verify reproducibility: `make setup && make check && make start`

Makefile contract
- Required targets: setup, dev, start, fmt, lint, typecheck, test, check
- `make check` runs fmt + lint + typecheck + tests and gates commits

Architecture (summary)
- Ingestor pulls Notion/Sheets/Manual → linkedin_links
- Classifier labels link as job/post → enqueues scrape:job or scrape:post
- Scrapers (Playwright/Puppeteer, no proxies in local) store HTML/screenshots to ./storage and metadata to *_raw
- Staging normalizes timestamps and canonical URLs
- Extractor-LLM (DeepSeek V3) converts messy text into normalized jobs and companies with JSON Schema validation and full audit logging
- Router builds application_routes and logs application_attempts
- Orchestrator (local Celery/cron; Temporal optional) runs per-link workflows with retries and DLQ
- Observer provides OTel traces, Prom metrics, Grafana dashboards, Sentry errors (local-friendly)

Safety \u0026 compliance
- Respect site terms \u0026 rate limits; no proxies in local; keep concurrency low
- Secrets via .env for local only (never commit real secrets)
- PII masked in logs; local ./storage used for artifacts
- LLM extraction is schema-validated (DeepSeek V3); prompt_version and IO stored for audit

SLOs
- p95 ingest→job < 10 minutes
- ≥95% extractions pass schema per day
- Zero duplicate jobs within 24h

Queues
- ingest.links, scrape.job, scrape.post, extract.llm, route.build, dead.letter
- Messages include trace_id for cross-service tracing

Versioning (short)
- Tags are immutable releases: `<app>-<semver>` (e.g., `notes-v1.3`)
- Branches for dev: `<app>-<semver>-dev`
- Helper scripts:
  - bin/save_version.sh <app> <version> [msg]
  - bin/fork_version.sh <app> <from-version> <new-branch>
  - bin/run_version.sh <app> <version> [-- <cmd>]
- See versioning-guide.md for details

Open decisions (set defaults if not specified)
- Orchestrator: local-first (Celery/cron); Temporal optional
- Cloud: none for now; local-only development and storage under ./storage
- Proxy: none in local mode
- Primary LLM: DeepSeek V3

Verification checklist (Warp)
- `make setup` completes without error
- `make check` passes
- `make start` boots the minimal services
- Links in README, WARP, DESIGN, OPERATING_MANUAL, orchestration.md resolve
- Session log created for today under sessions/

