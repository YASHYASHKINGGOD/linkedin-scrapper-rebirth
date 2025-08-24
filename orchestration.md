# orchestration.md

A production-ready, **event-driven, staged, idempotent** pipeline to ingest links from Google Sheets/Notion, classify them, scrape, stage, and LLM-extract into clean `jobs` / `companies` tables — all on Postgres (no S3).

---

## 1) goals

- Run 24×7 safely with retries, back-pressure, and clear visibility.  
- Each stage persists its own output and **never blocks** downstream.  
- Crash/restart safe via **idempotency** and **state transitions**.  
- Easy ops: one page to see backlogs, errors, and SLAs.

---

## 2) system components

**Workers (separate processes / containers):**
- **Ingestion**: polls Sheets/Notion every 3–4h, normalizes, dedupes, inserts into `linkedin_links`, emits `link.new`.
- **Classifier**: labels link as `job|post|unknown`, sets `status='queued'`, emits `link.classified`.
- **Router**: sends to the correct scrape queue (`scrape.job` or `scrape.post`).
- **Scraper—Job**: fetches job pages; persists **raw (bronze)** to Postgres raw table; emits `raw.persisted`.
- **Scraper—Post**: fetches posts; same as above for posts.
- **Staging**: light normalization (**silver**); emits `staged.persisted`.
- **LLM Extractor**: converts silver → **gold** (`jobs`, `companies`), marks `extracted`.
- **Sweeper**: periodic; retries `error`, unblocks “stuck” items, enforces back-pressure.
- **Metrics/Alerts**: exports counters/timers; raises alerts on SLO breaches.

**Queues (logical):**
- `ingest`, `classify`, `route`, `scrape.job`, `scrape.post`, `stage`, `extract`.

---

## 3) data model (conceptual on Postgres)

- **`linkedin_links`** (queue head):
  - `id`, `raw_url`, **`canonical_url (unique)`**, `source`, `classification`, `status`, `attempt_count`, `next_attempt_at`, `last_error`, timestamps.
- **Raw (bronze):**
  - `linkedin_jobs_raw`: `link_id (unique)`, `fetched_at`, `http_status`, `raw_html (bytea or text)`, `raw_json (jsonb)`, `fingerprint_hash`, `notes`.
  - `linkedin_posts_raw`: same columns for posts.
- **Staging (silver):**
  - `linkedin_jobs_stage`: `link_id (unique)`, `title`, `company`, `location`, `description`, `salary`, `extras(jsonb)`, `processed_at`.
  - `linkedin_posts_stage`: `link_id (unique)`, `author`, `text`, `language`, `extras`, `processed_at`.
- **Gold:**
  - `companies`: canonical company facts (name unique, website, linkedin_url, size, sector, etc.).
  - `jobs`: normalized job record with `company_id`, `link_id (unique)`, title, location, salary, jd, application_url, timestamps.

**Idempotency keys**
- `linkedin_links.canonical_url`  
- `*_raw.link_id`  
- `*_stage.link_id`  
- `jobs.link_id`  
These guarantee safe replays/duplicates.

---

## 4) state machine (per link)

```
new
 → classified (job|post)
 → queued (routed to scrape)
 → scraping
 → scraped (raw persisted)     → emits raw.persisted
 → staged  (silver persisted)  → emits staged.persisted
 → extracted (gold upserted)   [terminal success]
 → error (any step; retry window via next_attempt_at)
 → dead (exceeded attempts or permanent failure)
```

**Retry policy:** exponential backoff per stage (e.g., 5m → 30m → 2h → 6h → 24h), max 5 attempts, then `dead`.

**Timeouts:**  
- Scrape: 45–60s task budget.  
- LLM: 20–40s budget (or token cap).  
On timeout → `error` with reason; scheduled retry.

---

## 5) scheduling & triggers

- **Pollers (every 3–4h):** pull rows, normalize URLs, upsert into `linkedin_links` (idempotent), set `status='new'`.
- **Classifier:** consumes `new`, sets `classification`, transitions to `queued`.
- **Router:** reads classification → enqueues to `scrape.job` or `scrape.post`.
- **Scrapers:** consume from their queues, set `status='scraping'`, persist **raw**, set `status='scraped'`, emit `raw.persisted`.
- **Stager:** on `raw.persisted`, normalize → **stage** tables, `status='staged'`, emit `staged.persisted`.
- **LLM:** on `staged.persisted`, extract → **gold**, `status='extracted'`.

**Sweeper (periodic, e.g., every 5–10 min):**
- Requeue `error` where `now() >= next_attempt_at`.
- Detect **stuck** rows (`scraping` or `staged` older than threshold, e.g., 30 min); reset to previous safe state and re-enqueue.
- Enforce back-pressure (see §7).

---

## 6) readiness & locking

Workers **only** pick rows where:
- `status` is in the eligible set for that stage, **and**
- `now() >= next_attempt_at`.

Upon claim:
- Transition to the in-progress status (`scraping` / etc.).
- Hold a short-lived lock (row-level) while updating status to prevent double work.
- If the worker sees the row already advanced (another worker won), **no-op**.

---

## 7) concurrency, rate-limits, back-pressure

- **Global scrape rate**: cap total new scrapes per minute.  
- **Per-kind queues**: `scrape.job` and `scrape.post` isolated to avoid starvation.  
- **Basic hygiene** (v1): realistic UA/viewport, small random delays, limited parallelism.

**Back-pressure controller (router rules):**
- If `scrape.*` backlog > threshold (e.g., 300), temporarily throttle new enqueue from `queued`.
- If LLM backlog high, temporarily slow `staged → extract`.

---

## 8) observability

**Metrics per stage:**
- `enqueued`, `started`, `succeeded`, `failed`, `retries`, `dead`.  
- Latency: link **time in stage**, and **end-to-end** (`new → extracted`).  
- Cost counters (LLM tokens/rows).  
- Backlog sizes per queue.  

**Dashboards:**
- Live **backlog** by queue.  
- Success rate / error reason distribution.  
- p50/p95 **scrape time** and **LLM time**.  
- Daily throughput and token spend.

**Tracing:**
- One trace id per `link_id`; propagate across all stages.

**Alerts (suggested):**
- p95 end-to-end latency > SLA (e.g., > 2h) for 15 min.  
- Error rate for any stage > 10% over 10 min.  
- Backlog > threshold for 15 min.  
- Repeated `dead` growth > N/hour.

---

## 9) operations playbooks

**A) Reprocessing a specific link**
1. Look up by `canonical_url` or `id`.  
2. If `status='error'` with `attempt_count < max`: set `next_attempt_at = now()` to trigger retry.  
3. If `dead`: reset to last safe state (`queued` for scrape; `staged` for extract) and clear `last_error` (document reason).

**B) Stuck in `scraping` or `staged`**
- If older than threshold: move back one state (`queued` or `scraped`) and increment `attempt_count`; let sweeper retry.

**C) Permanent failures**
- 404/removed content or invalid URL: mark `dead` with cause; optionally suppress future re-ingest of same `canonical_url`.

**D) Hotfix throttling**
- Temporarily lower router throughput if LinkedIn rate-limits increase or captcha incidence spikes.

**E) Data retention**
- Keep raw and stage in Postgres for 30–60 days (configurable); gold indefinitely.

---

## 10) SLAs & policies

- **SLA:** median `new → extracted` < 20 min; p95 < 2h.  
- **Retries:** max 5 per stage with exponential backoff; then `dead`.  
- **Idempotency:** all writes are upserts guarded by unique keys.  
- **Change detection:** optional later — compare new raw `fingerprint_hash`; if unchanged, skip LLM to save tokens.

---

## 11) acceptance tests (non-code checklist)

- Ingest duplicates of the same URL from Sheets → only one `linkedin_links` row exists; others are ignored.  
- Crash the scraper mid-run → on restart, item resumes without duplicate raw rows.  
- Inject transient 429 → item moves to `error`, backs off, later succeeds.  
- Force router overload → classifier still runs but router throttles new scrapes.  
- End-to-end sample: `new → extracted` path exercised for both `job` and `post`.  
- Observability: dashboards show non-zero throughput; alerts fire on synthetic failure.

---

## 12) environment & rollout (no code)

- **Separate queues** for ingestion, scraping, staging, extraction.  
- **Distinct worker pools** with tuned concurrency (e.g., fewer for LLM, more for scraping).  
- Start with conservative limits; raise after success rate stabilizes.  
- Blue/green deploy workers by queue; avoid draining entire system at once.  
- Maintain a **feature flag** to bypass LLM extraction if token budget exhausted.

---

## 13) things deferred to “later” (pull when needed)

- Rotating proxies & advanced fingerprinting.  
- Content hashing & LLM cache to cut costs.  
- Admin UI for DLQ, manual edits, requeues.  
- Autoscaling of workers.  
- External warehouse export.  
- Company resolver/enrichment.

---

## 14) glossary

- **Bronze/Raw**: what we scraped (noisy, full-fidelity).  
- **Silver/Stage**: minimally cleaned/normalized fields for extraction.  
- **Gold**: finalized records used by the product.  
- **Dead-letter**: exhausted retries; requires manual action.  
- **Back-pressure**: deliberate throttling to keep the pipeline healthy.

---

### summary

This orchestration makes every step **async, durable, and observable**. By gating progress with **statuses**, **unique keys**, and **per-stage outputs**, the system absorbs failures, retries safely, and scales in clean slices (`ingest`, `scrape`, `stage`, `extract`). Add defensive extras (proxies, hashing, admin UI) once data signals you need them.
