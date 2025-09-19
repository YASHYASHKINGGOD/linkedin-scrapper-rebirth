# Project memory & rules (Claude + Warp)

## LinkedIn Scrapper Rebirth — Production-Ready Pipeline

This is a comprehensive LinkedIn job scraping and application automation system designed for 24×7 reliability with enterprise-grade observability, compliance, and data quality controls.

### Read order (MANDATORY)
WARP.md → DESIGN.md → planning.md → tasks.md → README.md → OPERATING_MANUAL.md

## Project Understanding (Updated 2025-08-22)

### Core Mission
Transform LinkedIn job/post links into actionable application routes through a fully automated, schema-validated pipeline with anti-bot protection and LLM-powered data normalization.

### Architecture Overview
**End-to-End Flow:** Ingest → Classify → Scrape (bronze) → Stage (silver) → LLM Extract (gold) → Route → Apply

**Key Components:**
1. **Ingestor** - Multi-source ingestion (Notion, Google Sheets, Manual API) → `linkedin_links`
2. **Classifier** - Fast rules/heuristics to identify job vs post links
3. **Scrapers** - Playwright/Puppeteer with stealth mode, session pools, human-like delays
4. **LLM Extractor** - DeepSeek V3 with versioned prompts, JSON Schema validation, full audit trails
5. **Router** - Builds application routes (email, DM, job links, comment links, external forms)
6. **Orchestrator** - Temporal/Celery workflows with retries, exponential backoff, DLQ
7. **Observer** - OpenTelemetry traces, Prometheus metrics, Grafana dashboards, Sentry errors

### Data Model & Storage
- **PostgreSQL 14+** as system of record with comprehensive schema
- **Local storage** under `./storage` for HTML artifacts, screenshots, LLM I/O
- **Redis** for rate limits, locks, and queue management
- **Schema validation** enforced at every LLM extraction with audit logging

### Key Tables
- `linkedin_links` - Ingestion queue with canonical URL deduplication
- `linkedin_jobs_raw` / `linkedin_posts_raw` - Bronze layer (raw scraped data)
- `companies` / `jobs` - Gold layer (LLM-normalized, schema-validated)
- `application_routes` / `application_attempts` - Routing and outcome tracking
- `llm_extractions` - Full audit trail of LLM operations with prompt versioning

### Compliance & Safety
- **Anti-bot protection** with stealth scraping, low concurrency, no proxies in local mode
- **Rate limiting** with per-ASN caps and respectful site terms compliance
- **PII masking** in logs, HTTPS enforcement, encryption at rest
- **Schema drift protection** with versioned prompts and validation rollback
- **Secrets management** via .env for local dev (no real secrets committed)

### Quality Standards
- **SLOs**: p95 ingest→job <10min, ≥95% valid extractions daily, zero duplicates/24h
- **Idempotency** via canonical URLs and content hashing
- **Deduplication** at multiple layers (URL, content, job similarity)
- **Observability** with full trace propagation and alerting on SLO violations

## Goals
- One-command bootstrap & test on any machine
- Small design before implementation; acceptance criteria defined
- Every change updates tests and docs
- Maintain `make check` green at all times

## Code standards
- Runtimes pinned by .tool-versions / .nvmrc
- Style: Prettier/ESLint (JS), Black/Ruff (Py); types via tsc/mypy/pyright
- Branches: feat/<slug>, fix/<slug>, chore/<slug>
- Commits: Conventional Commits

## Commands (Makefile Contract)
- Bootstrap: `make setup`
- Dev: `make dev`
- Run: `make start`
- Format: `make fmt` | Lint: `make lint` | Types: `make typecheck`
- Tests: `make test`
- Gate: `make check` (fmt + lint + typecheck + test)

## Work protocol (each session)
1) Read docs above and restate the next task
2) Implement in small commits; keep `make check` green
3) Update tasks.md; copy SESSION_TEMPLATE.md → sessions/SESSION-YYYY-MM-DD.md with exact commands run
4) Append a "Session YYYY-MM-DD" note here

## Project specifics
- **Architecture**: Ingest → Classify → Scrape (bronze) → Stage (silver) → Extract LLM (gold) → Route
- **Data model**: see DESIGN.md (Postgres 14+ DDL provided)
- **Queues**: ingest.links, scrape.job, scrape.post, extract.llm, route.build, dead.letter
- **SLOs**: p95 ingest→job <10m; 95%+ valid extraction daily; zero dupes/24h
- **Local-first**: No cloud dependencies, everything runs locally with ./storage
- **Primary LLM**: DeepSeek V3 with budget guardrails

## Current Status
- Project in early planning/setup phase
- MVP target: Milestone 1 (ingest → jobs pipeline)
- Focus: Tables + skeleton services + basic scraper + LLM extraction

## Versioning
- Tags: `<app>-<semver>` (immutable releases)
- Branches: `<app>-<semver>-dev`
- Helper scripts: bin/save_version.sh, bin/fork_version.sh, bin/run_version.sh

## Do not
- Rely on chat memory; treat repo as the source of truth
- Add hidden manual steps; everything via scripts/Make targets
- Commit real secrets (use .env for local dev only)
- Break anti-bot protections or exceed rate limits
- Skip schema validation or audit logging

## Session Notes

### Session 2025-08-26 (Selenium Implementation)
**Major Milestone**: Successfully migrated from Playwright to Selenium WebDriver

**Completed:**
- ✅ Replaced Playwright scraping approach with Selenium WebDriver
- ✅ Created robust LinkedIn login flow with anti-automation hardening:
  - Chrome options: --disable-blink-features=AutomationControlled, --no-sandbox, --disable-dev-shm-usage
  - Custom user agent and navigator.webdriver removal
  - Human-like random delays (1.0-2.5 seconds configurable)
  - 2FA/CAPTCHA detection and handling
- ✅ Implemented comprehensive configuration system (config.json)
- ✅ Built verification system with detailed logging and error handling
- ✅ Created complete documentation ecosystem:
  - docs/CLAUDE.md - Environment setup and usage guide  
  - docs/WARP.md - One-liner commands and AI prompts
  - docs/Designs.md - Architecture and design patterns
  - docs/Operatingmanual.md - Production runbook
  - docs/orchestration.md - Batch processing pipeline
  - docs/tasks.md - Prioritized feature backlog
  - docs/TROUBLESHOOTING.md - Issue resolution guide
- ✅ Successful login verification with real LinkedIn credentials

**Technical Implementation:**
- Environment: Python 3.13 + venv with selenium, webdriver-manager, pandas, openpyxl
- Chrome WebDriver: Auto-managed via webdriver-manager with version compatibility
- Configuration: JSON-based with credential management and tunable scraping parameters
- Logging: Structured logging with file rotation and multiple log levels
- Error Handling: Comprehensive exception handling with actionable error messages

**Login Verification Results:**
- ✅ Driver initialization: 8.4 seconds (including ChromeDriver download)
- ✅ LinkedIn navigation: 3.7 seconds to login page
- ✅ Form interaction: Successfully found and filled username/password fields
- ✅ Authentication: 14 second login process (including LinkedIn server processing)
- ✅ Validation: Correctly identified successful login via URL pattern (linkedin.com/feed/)
- ✅ Cleanup: Proper resource disposal and browser closure
- **Total execution time**: ~23 seconds end-to-end

**Next Priority Tasks:**
1. **P0**: Implement post content scraping (DOM selectors, content expansion)
2. **P0**: Add cookie/session persistence to skip repeated logins  
3. **P1**: Build comment extraction with nested reply handling
4. **P1**: Create data export pipeline (JSON, CSV, Excel formats)

**Branch Status**: `scraper-selenium-posts-v1.0-dev` - Successfully created and pushed
**Previous Branch**: `scraper-playwright-posts-v0.2-dev-claude` - Cleaned up and deleted
**Stashed Work**: Previous Playwright improvements preserved in stash for potential reference
