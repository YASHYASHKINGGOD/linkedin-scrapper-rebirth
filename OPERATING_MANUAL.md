# Operating Manual (Operators + AI Interns)

This repo is structured so both Claude Code and Warp can work independently and everything is reproducible from the repo.

## Files of interest
- CLAUDE.md — project memory & rules
- WARP.md — first-read rules, daily loop, versioning quick tour
- DESIGN.md — architecture, DDL, queues, SLOs
- planning.md — milestones and acceptance criteria
- tasks.md — living backlog
- SESSION_TEMPLATE.md — per-session log (copy into sessions/)
- CONTRIBUTING.md — Definition of Done and PR checklist
- Makefile — canonical commands (setup, dev, start, fmt, lint, typecheck, test, check)
- bin/*.sh — versioning helpers: save, fork, run

## Required daily loop
1) Start: read CLAUDE.md, WARP.md, DESIGN.md, planning.md, tasks.md, README.md; restate next task
2) Implement: small commits; tests updated; make check is green
3) Handover: update tasks.md; save sessions/SESSION-YYYY-MM-DD.md; append note to CLAUDE.md
4) Verify: make setup && make check && make start; log exact repro

## Running the pipeline locally
- Prereqs: Postgres 14+, Python 3.10+, Node 18+, Docker optional
- Storage: local filesystem at ./storage (created on demand)
- Setup: make setup \u0026\u0026 cp .env.example .env
- Start: make start (or service-specific commands per app once they exist)
- Check: make check

## Orchestration \u0026 Scheduling
- Local default: simple process manager or Celery with local Redis; optional Temporal dev server if desired
- Retries: exponential backoff; DLQ (local queue) on permanent failure
- Heartbeats for long-running scrapes; idempotent activity keys
- Schedules: ingestion 5–10m (cron/apscheduler); hot-link recrawl 12–24h; invalidate stale jobs after N days

## Runbooks
- Queue backlog: verify producer/consumer rates; scale workers; check DLQ; alert if backlog_age > SLO
- Scraper bans/captchas: keep concurrency very low; no proxies in local; enqueue captcha job if needed; use stored HTML where possible
- LLM timeouts/drift: fall back to smaller model; enforce JSON schema; rollback prompt_version; circuit-break on high invalid rate
- Schema drift (DB): apply migrations; keep LLM schema and DB schema in sync; reject writes on validation errors
- Rate limits: Redis-based token buckets; per-ASN and per-account caps
- Reprocessing: re-enqueue from *_raw; preserve LLM IO for audit

## Observability
- Tracing: OTel traces across services; propagate trace_id in messages
- Metrics: queue depth, p95 latencies per step, scrape success %, extraction validity %, primary route success %
- Dashboards: Grafana boards for ingest/classify/scrape/extract/route
- Alerts: backlog thresholds, error spikes, invalid extraction rate > 5%, cost budget ceiling

## Compliance & Security
- Respect site terms; use paid residential/mobile proxies; throttle aggressively
- Secrets in Vault/KMS/Secrets Manager; .env only for local dev
- PII masked in logs; encryption at rest (S3/GCS) and in transit (HTTPS)
- Model safety: DeepSeek V3 by default; versioned prompts; JSON schema validation; audit LLM IO in llm_extractions

## SLOs
- p95 ingest→job available < 10 minutes
- 95%+ extraction valid per day (schema-validated)
- Zero duplicate jobs in 24h window

## Incident Response
- On-call rotation documented in pager config (TBD)
- Severity matrix: Sev1 (pipeline down), Sev2 (scrape failure spike), Sev3 (minor degradation)
- Postmortems required for Sev1/Sev2 within 48h
