# DESIGN.md

This document details the production-ready architecture for LinkedIn ingest → scrape → LLM extract → apply.

## Problem & Goals
Goals
- Reliably ingest LinkedIn job and post links from many sources (Notion, Google Sheets, manual)
- Scrape at scale with anti-bot care, classify, and persist raw artifacts
- Normalize via LLM extraction into clean jobs and companies tables
- Power application routes (email, dm, job link, comment link, external form)
- Be safe to run 24×7 with observability, retries, idempotency, and auditability

Non-Goals
- Building a general-purpose web crawler beyond LinkedIn scope
- UI frontend beyond simple operator views

## High-Level Architecture
Components
- Ingestor: connectors for Notion, Google Sheets, Manual API writing to linkedin_links
- Classifier: fast rules + heuristics classify job vs post; enqueue scrape tasks
- Scrapers: job and post workers using Playwright/Puppeteer with stealth (no proxy in local mode)
- Staging: “silver” cleanup and harmonization
- Extractor LLM: templated prompts to normalized jobs and companies with JSON Schema validation
- Router: builds application_routes and selects primary route; logs outcomes
- Orchestrator: Temporal/Airflow/Celery controlling per-link workflow with retries and DLQ
- Observer: OpenTelemetry traces, Prometheus metrics, Grafana dashboards, Sentry errors
- Storage: Postgres (system of record), S3/GCS (raw HTML, screenshots, LLM IO), Redis (rate limits/locks), Queue (SQS/RabbitMQ/Kafka)

End-to-end Flow
1) ingestion → 2) classification → 3) scraping (bronze) → 4) staging (silver) → 5) llm extraction (gold) → 6) routing → 7) audit & observe

## Services
- ingestor: POST /ingest/links, GET /ingest/links/pending?limit=100; validates URLs; dedupes; throttles
- classifier: labels type and enqueues scrape:job or scrape:post
- scraper-jobs / scraper-posts: Playwright stealth, proxies, session pools; artifacts to S3; metadata to *_raw
- extractor-llm: deterministic prompts + few-shot; jsonschema validation; upserts companies & jobs; stores full LLM IO
- router: builds application_routes and logs attempts
- orchestrator: Temporal/Airflow/Celery with retries, heartbeats, DLQ
- observer: OTel + Prom + Grafana + Sentry

## Storage \u0026 Infra
- Postgres 14+
- Local object storage: ./storage for raw html, screenshots, serialized llm io (filesystem paths stored in tables)
- Redis (optional) for local rate limits/locks; can be disabled in pure single-process mode
- Queue (local): prefer Redis or RabbitMQ running locally; simple in-process queue acceptable for MVP
- Secrets: .env for local only (no real secrets committed)
- Deployment: local processes via Make targets; Docker optional for services

## Data Model (DDL)
Dialect: Postgres 14+. All tables have created_at, updated_at with triggers.

### Common Types
```sql
CREATE TYPE source_kind AS ENUM ('google_sheet','notion','manual');
CREATE TYPE link_kind AS ENUM ('job','post','unknown');
CREATE TYPE process_status AS ENUM ('pending','in_progress','done','error');
CREATE TYPE route_type AS ENUM ('email','linkedin_dm','job_link','comment_link','external_form');
CREATE TYPE confidence AS ENUM ('low','medium','high');
```

### 1) Ingestion Queue
```sql
CREATE TABLE public.linkedin_links (
id BIGSERIAL PRIMARY KEY,
 url TEXT NOT NULL,
 url_canonical TEXT GENERATED ALWAYS AS (lower(url)) STORED,
 link_type link_kind DEFAULT 'unknown'::link_kind,
 source source_kind NOT NULL,
 -- local/ingestor-friendly fields for provenance and categorization
 category TEXT,                -- posts|jobs|other|external
 sheet_name TEXT,
 tab TEXT,
 row_number INT,
 date_in_source TEXT,
 extracted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 external_metadata JSONB,
 is_scraped BOOLEAN DEFAULT FALSE,
 is_processed BOOLEAN DEFAULT FALSE,
 is_error BOOLEAN DEFAULT FALSE,
 error_message TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_link_unique ON public.linkedin_links (url_canonical);
-- Practical ON CONFLICT guidance
-- INSERT ... ON CONFLICT (url_canonical) DO UPDATE SET ... ensures idempotency for ingest.
CREATE INDEX IF NOT EXISTS ix_links_status ON public.linkedin_links (is_scraped, is_processed, is_error);
```

### 2) Raw Job Pages
```sql
CREATE TABLE public.linkedin_jobs_raw (
 id BIGSERIAL PRIMARY KEY,
 link_id BIGINT NOT NULL REFERENCES public.linkedin_links(id) ON DELETE CASCADE,
 job_url TEXT NOT NULL,
 html_object_key TEXT,
 snapshot_object_key TEXT,
 raw_json JSONB,
 lang TEXT,
 scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 scrape_status process_status NOT NULL DEFAULT 'done',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_jobs_raw_link ON public.linkedin_jobs_raw (link_id);
```

### 3) Raw Post Pages
```sql
CREATE TABLE public.linkedin_posts_raw (
 id BIGSERIAL PRIMARY KEY,
 link_id BIGINT NOT NULL REFERENCES public.linkedin_links(id) ON DELETE CASCADE,
 post_url TEXT NOT NULL,
 html_object_key TEXT,
 snapshot_object_key TEXT,
 raw_json JSONB,
 lang TEXT,
 scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 scrape_status process_status NOT NULL DEFAULT 'done',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_posts_raw_link ON public.linkedin_posts_raw (link_id);
```

### 4) Companies (normalized)
```sql
CREATE TABLE public.companies (
 id BIGSERIAL PRIMARY KEY,
 name TEXT NOT NULL,
 name_norm TEXT GENERATED ALWAYS AS (lower(name)) STORED,
 website TEXT,
 linkedin_url TEXT,
 hq_city TEXT,
 hq_country TEXT,
 size_bucket TEXT,
 industry TEXT,
 funding_stage TEXT,
 last_funded_round TEXT,
 is_active BOOLEAN DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_company_name_norm ON public.companies(name_norm);
```

### 5) Jobs (normalized, llm-extracted)
```sql
CREATE TABLE public.jobs (
 id BIGSERIAL PRIMARY KEY,
 company_id BIGINT REFERENCES public.companies(id) ON DELETE SET NULL,
 source_link_id BIGINT NOT NULL REFERENCES public.linkedin_links(id) ON DELETE CASCADE,
 origin link_kind NOT NULL,
 role_title TEXT NOT NULL,
 seniority TEXT,
 location TEXT,
 location_type TEXT,
 employment_type TEXT,
 description_text TEXT,
 skills TEXT[],
 salary_min NUMERIC,
 salary_max NUMERIC,
 currency TEXT,
 application_deadline DATE,
 application_link TEXT,
 how_to_apply TEXT,
 extracted_confidence confidence DEFAULT 'medium',
 posted_at TIMESTAMPTZ,
 first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 is_active BOOLEAN DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_jobs_company ON public.jobs(company_id);
CREATE INDEX IF NOT EXISTS ix_jobs_title ON public.jobs(role_title);
CREATE INDEX IF NOT EXISTS ix_jobs_active ON public.jobs(is_active, last_seen_at DESC);
```

### 6) LLM Extraction Audit
```sql
CREATE TABLE public.llm_extractions (
 id BIGSERIAL PRIMARY KEY,
 source TEXT NOT NULL,
 source_id BIGINT NOT NULL,
 model_name TEXT NOT NULL,
 prompt_version TEXT NOT NULL,
 input_ref_object TEXT,
 output_json JSONB NOT NULL,
 validation_errors JSONB,
 status process_status NOT NULL DEFAULT 'done',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_llm_src ON public.llm_extractions(source, source_id);
```

### 7) Application Routes & Attempts
```sql
CREATE TABLE public.application_routes (
 id BIGSERIAL PRIMARY KEY,
 job_id BIGINT NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
 route route_type NOT NULL,
 target TEXT,
 display_text TEXT,
 priority INT DEFAULT 100,
 is_primary BOOLEAN DEFAULT FALSE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_routes_job ON public.application_routes(job_id, priority);

CREATE TABLE public.application_attempts (
 id BIGSERIAL PRIMARY KEY,
 route_id BIGINT NOT NULL REFERENCES public.application_routes(id) ON DELETE CASCADE,
 outcome TEXT NOT NULL,
 detail JSONB,
 attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 8) Pipeline Runs & Errors
```sql
CREATE TABLE public.pipeline_runs (
 id BIGSERIAL PRIMARY KEY,
 name TEXT NOT NULL,
 args JSONB,
 status process_status NOT NULL DEFAULT 'pending',
 started_at TIMESTAMPTZ,
 finished_at TIMESTAMPTZ,
 error_message TEXT
);

CREATE TABLE public.errors (
 id BIGSERIAL PRIMARY KEY,
 scope TEXT NOT NULL,
 ref_table TEXT,
 ref_id BIGINT,
 message TEXT NOT NULL,
 context JSONB,
 occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Processing Rules
- Idempotency: linkedin_links.url_canonical unique; scrapers upsert *_raw by link_id; jobs upsert by (source_link_id, role_title, company_id)
- Categorization: url LIKE 'https://www.linkedin.com/posts%' → posts; LIKE 'https://www.linkedin.com/jobs%' → jobs; LIKE 'https://www.linkedin.com/%' → other; else external
- Dedupe: md5(url_canonical); job duplicate hash of (company, role_title, location, application_link)
- Data quality: NOT NULL where possible, regex/url checks, salary sanity ranges
- Observability: spans across ingest→classify→scrape→extract→route; alert on queue backlog, error spikes, drift

## Scraping Hygiene
- Playwright stealth; no proxies in local mode; keep concurrency low to avoid bot triggers
- Session pools, randomized UA/locale/timezone; human-like scroll \u0026 delays
- Captcha queue (optional); store raw html \u0026 screenshots to avoid re-scrapes

## LLM Safety
- Default model: DeepSeek V3 for extraction
- Versioned prompts; JSON schema enforcement; rollback on validation drift
- Budget guardrails (local dev caps)

## Security
- Secrets in vault/kms; no secrets in code
- PII masked in logs; HTTPS enforced; S3/GCS encryption at rest

## Queues \u0026 Message Shapes
Queues (local): ingest.links, scrape.job, scrape.post, extract.llm, route.build, dead.letter

Message example — scrape
```json
{
  "link_id": 12345,
  "url": "https://www.linkedin.com/jobs/view/123/",
  "type": "job",
  "attempt": 1,
  "trace_id": "b6e8..."
}
```

Message example — extract
```json
{
  "raw_table": "linkedin_jobs_raw",
  "raw_id": 9876,
  "prompt_version": "jobs_v3",
  "trace_id": "c12a..."
}
```

## LLM Extraction Contracts — JSON Schema (jobs)
```json
{
 "type": "object",
 "required": ["role_title", "company", "how_to_apply"],
 "properties": {
  "role_title": {"type": "string"},
  "seniority": {"type": "string"},
  "company": {
   "type": "object",
   "required": ["name"],
   "properties": {
    "name": {"type": "string"},
    "website": {"type": "string"},
    "linkedin_url": {"type": "string"},
    "size_bucket": {"type": "string"},
    "industry": {"type": "string"},
    "hq_city": {"type": "string"},
    "hq_country": {"type": "string"}
   }
  },
  "location": {"type": "string"},
  "location_type": {"type": "string"},
  "employment_type": {"type": "string"},
  "skills": {"type": "array", "items": {"type": "string"}},
  "salary_min": {"type": "number"},
  "salary_max": {"type": "number"},
  "currency": {"type": "string"},
  "application_link": {"type": "string"},
  "how_to_apply": {"type": "string"},
  "posted_at": {"type": "string"}
 }
}
```

## Orchestration
Minimal workflow (suggested):
- Temporal workflows per link: ingestLink → classify → scrape (jobs|posts) → stage → extractLLM → upsertCompany → upsertJob → buildRoutes
- Activities are retryable with exponential backoff; heartbeats for long scrapes; DLQ on permanent failure

## Scheduling
- Ingestion every 5–10 min
- Re-crawl hot links every 12–24h with backoff
- Invalidate jobs older than N days unless still seen

## Success Criteria (SLOs)
- p95 ingest→job available < 10 minutes at steady state
- 95%+ extraction valid (schema-validated) per day
- Zero duplicate jobs in 24h window
- All actions audited in application_attempts

## Risks & Mitigations
- Anti-bot defenses → rotating residential proxies, session pools, low ASN concurrency
- LLM drift → versioned prompts, schema validation, rollback
- Data duplication → canonical URLs, unique constraints, hashes
- Compliance → robots/TOS policy, PII masking, secure secrets

## Observability
- Traces across services with OTel; propagate trace_id in messages
- Metrics: queue depth, success/error rates, latency per step, cost
- Dashboards: scrape success, extraction validity, routing attempts
- Alerts: backlog thresholds, error spikes, drift detection

## Open Decisions / Defaults
- Orchestrator: local-only. Start with simple process/cron or Celery with local Redis. Temporal optional.
- Cloud: none for now. Everything runs locally and saves artifacts under ./storage.
- Proxy: none in local mode.
- Primary LLM: DeepSeek V3.
