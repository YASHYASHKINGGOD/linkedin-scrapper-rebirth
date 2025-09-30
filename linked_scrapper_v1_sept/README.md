LinkedIn Pipeline Handover (Login-Enabled, End-to-End)

Overall Goal

- Build a robust pipeline that ingests LinkedIn URLs from Google Sheets, classifies each link as a post or job, scrapes them using a login-enabled browser, and stores raw artifacts and extracted metadata in an existing Postgres database (data_lake).
- Scope explicitly excludes scheduling. All steps run manually. We never modify original .py files in-place; when needed, we duplicate and create new versions to avoid regressions.

Outcomes

- Ingests URLs + sheet metadata into public.linkedin_links.
- Classifies links and queues them with status flags.
- Scrapes posts (async, session-persistent) into public.linkedin_posts_raw.
- Scrapes jobs (login-enabled Selenium) into public.linkedin_jobs_raw.
- Updates public.linkedin_links.status and records error/backoff for reliability.

Repository Layout (Key Files To Use)

- Project root: linkedin scrapper rebirth
- Ingest CLI: linkedin scrapper rebirth/linkedin_ingestor_cli.py
- Classify & queue CLI: linkedin scrapper rebirth/src/app.py (subcommand classify-and-queue)
- Posts router: linkedin scrapper rebirth/src/routers/posts_router.py
- Posts worker (async): linkedin scrapper rebirth/src/workers/posts_worker.py
- Jobs batch runner (new): linkedin scrapper rebirth/src/workers/jobs_batch.py
- Jobs scraper task (login-enabled): linkedin scrapper rebirth/apps/orchestration/scrapers.py (task scrape_job)
- Login-enabled scrapers for reference and testing:
    - linkedin scrapper rebirth/selenium_scraper.py
    - linkedin scrapper rebirth/linkedin_scraper_xpath_v1.py
- Migration for posts raw (reference): linkedin scrapper rebirth/src/db/migrations/001_create_linkedin_posts_raw.sql

Never Edit Existing .py Files In-Place

- Do not modify original files directly.
- If you need to adjust behavior:
    - Copy the file and append a version suffix, e.g., posts_worker_v2.py, jobs_batch_v1.py, posts_router_v2.py.
    - Wire your tests and runs to the new version file only.
    - Keep original files as stable references.
- The included jobs batch runner is additive (src/workers/jobs_batch.py). For any local edits, create a copy (src/workers/jobs_batch_v2.py) instead of changing the original.

Environment & Setup

- Python: 3.8+ recommended
- Postgres database: data_lake running locally
- Google Sheets API credentials:
    - client_secret_*.json in project root
    - .secrets/google_token.json (created on first run)
- LinkedIn credentials: store in config.json
- Suggested first-run approach:
    - Set headless to false and provide chrome_options.user_data_dir for persistent login session
    - Complete any CAPTCHA/2FA once, then reuse profile (subsequent runs can be headless)

Commands

- cd "linkedin scrapper rebirth"
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/data_lake

Configuration (config.json Example)

```
{
  "linkedin_credentials": {
    "email": "your.email@domain.com",
    "password": "your_password"
  },
  "chrome_options": {
    "disable_automation_flags": [
      "--disable-blink-features=AutomationControlled",
      "--disable-infobars",
      "--disable-dev-shm-usage",
      "--no-sandbox"
    ],
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "window_size": [1366, 900],
    "user_data_dir": "chrome_profile"
  },
  "scraping_settings": {
    "headless": true,
    "implicit_wait_timeout": 5,
    "page_load_timeout": 45,
    "explicit_wait_timeout": 20
  },
  "output_settings": {
    "output_directory": "outputs",
    "timestamp_format": "%Y%m%d_%H%M%S"
  }
}
```

Database Schemas (What Fields We Need At Each Stage)

A) public.linkedin_links (links catalog + orchestration)

- url (TEXT): The LinkedIn URL from Google Sheets.
- url_canonical (TEXT GENERATED ALWAYS AS lower(url) STORED): Canonical lowercase version of URL. Unique index on (url_canonical).
- category (TEXT): Inferred at ingest: 'posts' if URL starts with https://www.linkedin.com/posts, 'jobs' if https://www.linkedin.com/jobs, 'other' if another LinkedIn path, 'external' if non-LinkedIn.
- source (TEXT): Provenance, e.g., 'google_sheet:Job Dashboard - The Growth Desk'.
- sheet_name (TEXT): Google Sheet name (from the sheet metadata).
- tab (TEXT): Tab title (e.g., 'September (2025)').
- row_number (INT): Row in the sheet where the URL was found.
- date_in_source (TEXT): Date string from the sheet (if present).
- extracted_at (TIMESTAMPTZ): Ingest timestamp.
- classification (TEXT: 'job'|'post'|'unknown'): Set by classify-and-queue.
- status (TEXT: 'new'|'queued'|'scraping'|'scraped'|'staged'|'extracted'|'error'|'dead'): Orchestration status; transitions handled by router/workers/tasks.
- attempt_count (INT): Number of attempts for scraping.
- next_attempt_at (TIMESTAMPTZ): When to retry on failure.
- last_error (TEXT): Last error message from scraping or routing.
- Optional columns observed in some flows:
    - last_scraped_at (TIMESTAMPTZ): Set by some scrapers when scraping finishes.

B) public.events (idempotent event audit)

- id (BIGSERIAL) PK
- kind (TEXT): 'link.new', 'link.classified', etc.
- link_id (BIGINT) FK -> public.linkedin_links(id)
- payload (JSONB): Metadata snapshot for auditing
- created_at (TIMESTAMPTZ)
- Unique (kind, link_id)

C) public.link_provenance (optional provenance table created by importer)

- id (BIGSERIAL) PK
- link_url (TEXT) REFERENCES public.linkedin_links(url) ON DELETE CASCADE
- sheet_name (TEXT)
- tab (TEXT)
- row_number (INT)
- discovered_at (TIMESTAMPTZ)
- Index on (link_url)

D) public.linkedin_posts_raw (raw posts storage and metadata)

- id (BIGSERIAL) PK
- link_id (BIGINT) FK -> public.linkedin_links(id) ON DELETE CASCADE UNIQUE
- url (TEXT) NOT NULL
- canonical_url (TEXT GENERATED ALWAYS AS lower(url) STORED)
- raw_html_path (TEXT): Path relative to storage root
- screenshot_path (TEXT): Path to screenshot
- metadata_json_path (TEXT): Path to metadata JSON (if used)
- status (TEXT: 'pending'|'scraping'|'completed'|'failed'|'retry') DEFAULT 'pending'
- scraped_at (TIMESTAMPTZ)
- created_at (TIMESTAMPTZ) DEFAULT now()
- updated_at (TIMESTAMPTZ) DEFAULT now() (kept via trigger)
- scrape_metadata (JSONB DEFAULT '{}'): Browser/session/timing info
- extracted_data (JSONB DEFAULT '{}'): Parsed post content, author, comments, links, images, etc.
- error_message (TEXT)
- attempt_count (INT DEFAULT 0)
- max_attempts (INT DEFAULT 3)
- next_retry_at (TIMESTAMPTZ)
- trace_id (TEXT)
- scraper_version (TEXT)
- Indexes: link_id, status, scraped_at, next_retry_at (partial), trace_id (partial), GIN index on extracted_data

Recommended extracted_data JSON structure for posts:

- post_url (string)
- post_author (string)
- author_profile_url (string)
- author_title (string)
- date_posted (string, relative or ISO)
- post_text (string)
- external_links (array of strings)
- images (array of {url, alt_text})
- comments (array of {commentor, comment_text}) with optional comment_count

E) public.linkedin_jobs_raw (raw jobs storage and metadata)

- id (BIGSERIAL) PK
- link_id (BIGINT) FK -> public.linkedin_links(id) ON DELETE CASCADE UNIQUE
- job_url (TEXT)
- html_object_key (TEXT) — path for HTML or future object storage key
- snapshot_object_key (TEXT) — path for screenshot or future object storage key
- raw_json (JSONB) — optional raw payload dump
- scraped_at (TIMESTAMPTZ) DEFAULT now()
- scrape_status (TEXT DEFAULT 'done')
- Denormalized fields from the scraper:
    - url (TEXT) — same as job_url
    - role_title (TEXT)
    - company_name (TEXT)
    - location (TEXT)
    - posted_time (TEXT)
    - status (TEXT) — e.g., “No longer accepting applications”
    - description_text (TEXT)
    - html_path (TEXT) — local file path used
    - screenshot_path (TEXT) — local file path used
- Unique index on (link_id)

Google Sheets Extraction — What Fields to Read and How They Map

- Expected columns from Google Sheets (as per importer staging):
    - date (TEXT): The date shown in the sheet (e.g., posting date, data date)
    - company (TEXT): Company name (if present)
    - role (TEXT): Role title (if present)
    - location (TEXT): Location field (if present)
    - url (TEXT): The LinkedIn URL (REQUIRED)
    - sheet_name (TEXT): Name of the sheet (e.g., Job Dashboard - The Growth Desk)
    - tab_title (TEXT): Tab name (e.g., September (2025))
    - row_number (INT): Row index in the sheet
- Mapping to public.linkedin_links during import:
    - url -> url (TEXT)
    - sheet_name -> sheet_name (TEXT)
    - tab_title -> tab (TEXT)
    - row_number -> row_number (INT)
    - date -> date_in_source (TEXT)
    - extracted_at -> now()
    - source -> CONCAT('google_sheet:', COALESCE(sheet_name,''))
    - category -> CASE by URL pattern:
      https://www.linkedin.com/posts% -> 'posts'
      https://www.linkedin.com/jobs%  -> 'jobs'
      https://www.linkedin.com/%      -> 'other'
      else                           -> 'external'
- url_canonical generated automatically (lower(url)); unique index enforces dedupe.
- Dedupe: INSERT ON CONFLICT (url_canonical) DO UPDATE sets latest sheet metadata.

End-to-End Flow (No Scheduling)

Step 1: Ingest From Google Sheets → public.linkedin_links

- Commands:
    - python3 linkedin_ingestor_cli.py init
    - python3 linkedin_ingestor_cli.py run
    - python3 linkedin_ingestor_cli.py status
- Verifications (pick one):
    - psql $DATABASE_URL -c "SELECT COUNT(*) FROM public.linkedin_links;"
    - psql $DATABASE_URL -c "SELECT sheet_name, COUNT(*) FROM public.linkedin_links GROUP BY 1 ORDER BY 1;"

Step 2: Classify & Queue Links

- Command:
    - python3 -m src.app classify-and-queue
- What happens:
    - Adds orchestration columns to linkedin_links (classification, status, attempt_count, next_attempt_at, last_error)
    - Emits idempotent events in public.events for 'link.new' and 'link.classified'
    - Sets status='queued' for newly observed links
- Verification:
    - psql $DATABASE_URL -c "SELECT classification, status, COUNT(*) FROM public.linkedin_links GROUP BY 1,2 ORDER BY 1,2;"

Step 3: Scrape Posts (Login-Enabled Async Worker)

- Start worker (continuous loop):
    - python3 -m src.workers.posts_worker run-worker --batch-size 5 --sleep 15
- Single post test:
    - python3 -m src.workers.posts_worker scrape-single --url "https://www.linkedin.com/posts/..."
- Behavior:
    - Worker pulls queued 'post' links via router (src/routers/posts_router.py)
    - Creates/updates raw entry in public.linkedin_posts_raw (link_id, trace_id, url)
    - Maintains a single authenticated browser session (persisted profile) across batch
    - Saves raw_html_path and screenshot_path under ./storage
    - Writes extracted_data JSON (post text, author, links, images, comments) into linkedin_posts_raw
    - Updates linkedin_links.status to 'scraped' on success; otherwise 'error' with next_attempt_at and incremented attempt_count
- Recommended extracted_data fields for posts:
    - post_url, post_author, author_profile_url, author_title, date_posted, post_text, external_links, images [{url, alt_text}], comments [{commentor, comment_text}], comment_count

Step 4: Scrape Jobs (Login-Enabled, Batch Runner)

- New runner (do not edit originals; we added an additive runner):
    - File: src/workers/jobs_batch.py
    - Commands:
    - Process a batch of queued jobs:
      - python3 -m src.workers.jobs_batch run-batch --batch-size 5
    - Scrape a single job by link_id:
      - python3 -m src.workers.jobs_batch scrape-single --link-id 123
    - Scrape a single job by URL (creates link if missing):
      - python3 -m src/workers/jobs_batch scrape-single --url "https://www.linkedin.com/jobs/view/..."
- Behavior:
    - Fetches queued job links (status='queued' or eligible 'error' with backoff window passed)
    - Calls existing task apps/orchestration/scrapers.py::scrape_job directly via .run()
    - Task:
    - Uses Selenium to login (config.json)
    - Extracts denormalized fields: role_title, company_name, location, posted_time, status, description_text
    - Saves raw_html_path, screenshot_path
    - Upserts into public.linkedin_jobs_raw (unique per link_id)
    - Updates linkedin_links.status='scraped' or sets 'error' with backoff fields

Validation Queries

- Link status distribution:
    - psql $DATABASE_URL -c "SELECT classification, status, COUNT(*) FROM public.linkedin_links GROUP BY 1,2 ORDER BY 1,2;"
- Posts raw summary:
    - psql $DATABASE_URL -c "SELECT success, COUNT(*) FROM public.linkedin_posts_raw GROUP BY 1;"
    - psql $DATABASE_URL -c "SELECT id, link_id, success, scraped_at FROM public.linkedin_posts_raw ORDER BY id DESC LIMIT 10;"
- Jobs raw summary:
    - psql $DATABASE_URL -c "SELECT COUNT(*) FROM public.linkedin_jobs_raw;"
    - psql $DATABASE_URL -c "SELECT id, link_id, scraped_at FROM public.linkedin_jobs_raw ORDER BY id DESC LIMIT 10;"
- Files on disk:
    - ls -R storage | head -200

Login & Anti-Detection Notes

- First-time login:
    - Set "headless": false in config.json
    - Set "user_data_dir": "chrome_profile" to persist the session
    - Manually complete any CAPTCHA/2FA once, then re-run headless later
- Posts worker:
    - Reuses the same logged-in context across a batch to minimize detection
- Jobs task:
    - Removes navigator.webdriver, sets realistic user-agent and window size
- If login fails:
    - Verify config.json credentials; try a headed run to solve challenges
    - Ensure chrome_profile is writable and persists across runs

Error Handling & Retries

- linkedin_links:
    - On failures, we set status='error', attempt_count=attempt_count+1, last_error=<message>, next_attempt_at=now()+30 minutes (adjustable)
    - Re-running batches/processors will skip until next_attempt_at
- linkedin_posts_raw:
    - status field tracks 'pending'|'scraping'|'completed'|'failed'|'retry'
    - attempt_count, max_attempts, next_retry_at control reprocessing
- linkedin_jobs_raw:
    - Upsert by link_id; scrape_status='done' and scraped_at updated on success

What Not To Do

- Do NOT edit .py files in place. Always duplicate to a new *_v2.py or *_v1.py copy for changes.
- Do NOT change existing schemas unless discussed; the tables are already present and used across the pipeline.
- Do NOT commit credentials; keep config.json private and local.

Runbook (Cheat Sheet)

- Setup:
    - cd "linkedin scrapper rebirth"
    - python3 -m venv .venv && source .venv/bin/activate
    - pip install -r requirements.txt
    - export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/data_lake
    - Ensure config.json has LinkedIn creds and chrome_profile configured
- Ingest:
    - python3 linkedin_ingestor_cli.py init
    - python3 linkedin_ingestor_cli.py run
    - python3 linkedin_ingestor_cli.py status
- Classify:
    - python3 -m src.app classify-and-queue
- Posts:
    - python3 -m src.workers.posts_worker run-worker --batch-size 5 --sleep 15
- Jobs:
    - python3 -m src.workers.jobs_batch run-batch --batch-size 5

Junior Developer Short Goals

- Ingest: Run init and run; verify linkedin_links populated (counts per sheet).
- Classify & queue: Run classify-and-queue; confirm queued counts for posts and jobs.
- Posts scraping: Run posts worker with a small batch; verify new rows in linkedin_posts_raw, link status -> scraped.
- Jobs scraping: Run jobs_batch with a small batch; verify rows in linkedin_jobs_raw, link status updates.
- Sanity & artifacts: Inspect ./storage for HTML + screenshots; check DB last_error on failures.

Appendix — Example extracted_data JSON for Posts

```
{
  "post_url": "https://www.linkedin.com/posts/....",
  "post_author": "Jane Doe",
  "author_profile_url": "https://www.linkedin.com/in/jane-doe/",
  "author_title": "Head of Product at ACME",
  "date_posted": "2w",
  "post_text": "We’re hiring a Product Manager for our growth team...",
  "external_links": [
    "https://acme.com/careers/pm"
  ],
  "images": [
    { "url": "https://media.licdn.com/.../image.jpg", "alt_text": "Team photo" }
  ],
  "comment_count": 3,
  "comments": [
    {"commentor": "John Smith", "comment_text": "Congrats!"},
    {"commentor": "Mary Jones", "comment_text": "Is this remote?"},
    {"commentor": "Arun", "comment_text": "Applied!"}
  ]
}
```

Appendix — Example Row Mapping From Google Sheets

- date -> linkedin_links.date_in_source
- company -> not persisted to linkedin_links (optional column; we keep sheet_name, tab, row_number)
- role -> not persisted to linkedin_links
- location -> not persisted to linkedin_links
- url -> linkedin_links.url
- sheet_name -> linkedin_links.sheet_name
- tab_title -> linkedin_links.tab
- row_number -> linkedin_links.row_number
- category -> inferred (posts / jobs / other / external)

Appendix — How To Safely Create New Versions Of Code

- Need to tweak the posts worker? Copy:
    - cp src/workers/posts_worker.py src/workers/posts_worker_v2.py
    - Run with: python3 -m src/workers/posts_worker_v2 run-worker --batch-size 5 --sleep 15
- Need to edit jobs batch logic? Copy:
    - cp src/workers/jobs_batch.py src/workers/jobs_batch_v2.py
    - Run with: python3 -m src/workers/jobs_batch_v2 run-batch --batch-size 5
- Keep both versions until the new one is validated. Never alter the originals in-place.

Optional: One-Click Run (No Scheduling)

- We can add a new script (src/pipeline/run_once_v1.py) that:
  - Runs classify-and-queue
  - Routes posts and starts a one-batch scrape
  - Runs jobs_batch for a one-batch scrape
- This would be a new file only (no edits to existing modules).

