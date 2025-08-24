# planning.md

Milestones derived from the quick build order.

## Milestone 1 — MVP (ingest → jobs)
Scope
- Tables + S3 bucket + skeleton services
- Notion/Sheets ingestor → linkedin_links
- Classifier + job scraper → linkedin_jobs_raw
- Extractor-LLM → companies, jobs
- Route builder → application_routes
Acceptance
- make check green; local pipeline runs on a small seed
- >90% extraction passes schema locally
- Basic dashboards show queue depth and error rate

## Milestone 2 — Posts + Comments and Routing
Scope
- Post scraper; visible comments captured
- Comment-link routing added; outcomes logged
Acceptance
- Comment link built where applicable; application_attempts recorded

## Milestone 3 — Reliability & Observability
Scope
- Retries, exponential backoff, DLQ; Temporal/Airflow wiring
- Captcha queue; proxy rotation; session pools
- Alerts & dashboards; data-quality checks
Acceptance
- p95 ingest→job <10m; alerting in place; audit trails complete

## Milestone 4 — Orchestration & Queues
Scope
- Introduce queue-backed workers for ingest, classify, route, scrape.job, scrape.post, stage, extract
- Implement status state machine in linkedin_links and *_raw/*_stage
- Idempotent upserts via ON CONFLICT (url_canonical)
- Backoff retries and DLQ
Acceptance
- End-to-end new → extracted under back-pressure; dashboards show queue depths and latencies

## Test Plan
- Unit: URL validation, classifiers, schema validators, routers
- Integration: scraper to storage stubs; LLM extraction with mocked models
- E2E: happy path pipeline on a small fixture set

## Risks & Guardrails
- Anti-bot blocking → rotate proxies; low ASN concurrency; cache HTML to avoid re-scrapes
- LLM drift → version prompts; lock prompt_version; enforce JSON Schema
