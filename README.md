# LinkedIn Ingest → Scrape → LLM Extract → Apply

Production-ready pipeline to ingest LinkedIn job/post links from multiple sources, scrape at scale, extract normalized jobs/companies via LLMs, and build actionable application routes (email, DM, links, forms) with 24×7 reliability.

Key docs to read next:
- WARP.md — project rules, daily loop, versioning shortcuts
- DESIGN.md — architecture, data model (DDL), queues, SLOs, safety
- OPERATING_MANUAL.md — runbooks, reliability, on-call, compliance
- planning.md — milestones and acceptance criteria
- CONTRIBUTING.md — Definition of Done, PR checklist

## Quickstart
```bash
make setup
python -m pip install -r requirements.txt  # install Google APIs
cp .env.example .env
# Fill GOOGLE_OAUTH_CLIENT_JSON by downloading OAuth client JSON
# Then run and authorize once in browser:
GOOGLE_SHEETS_URLS="https://docs.google.com/spreadsheets/d/14OmQuYyreTa_ehui2vGXbydNpMsJCrCTArolMozuPG0/edit?gid=1790709853" python -m src.app
GOOGLE_SHEETS_URLS="https://docs.google.com/spreadsheets/d/14OmQuYyreTa_ehui2vGXbydNpMsJCrCTArolMozuPG0/edit?gid=1790709853" OUTPUT_JSONL=./storage/linkedin_links.jsonl python -m src.app

# or via YAML config for many sheets
cp config/sheets.yaml.sample config/sheets.yaml
# edit config/sheets.yaml and then run
SHEETS_CONFIG=./config/sheets.yaml OUTPUT_JSONL=./storage/linkedin_links.jsonl python -m src.app
```
```bash
# clone or unzip this project, then:
make setup
cp .env.example .env   # fill placeholders (no real secrets)
make start             # or: make dev
make check             # fmt + lint + types + tests
```

## What this does
- Ingest links from Notion, Google Sheets, and manual API into linkedin_links
- Classify links (job | post) and enqueue scrape tasks
- Scrape raw HTML/JSON artifacts to ./storage and *_raw tables
- LLM extract (DeepSeek V3) to normalized jobs and companies with strict JSON Schema
- Build application_routes and log application_attempts

## Compliance & ethics
- Respect legal constraints; secrets are never committed
- PII masked in logs; audit trails preserved

See OPERATING_MANUAL.md for runbooks and DESIGN.md for full schemas.

---

## Production orchestration overview
- Read orchestration.md for the target production design: staged persistence (bronze/silver/gold), idempotent upserts, per-stage queues, retries, and observability.
- Local CLI commands here produce reproducible artifacts (CSV under ./storage) and can load into Postgres.

## Schema migration: canonical URL and unique index
To align with orchestration.md, adopt TEXT url and a canonical_url unique index (lower(url)):
```sql
ALTER TABLE public.linkedin_links ALTER COLUMN url TYPE text;
ALTER TABLE public.linkedin_links
  ADD COLUMN IF NOT EXISTS url_canonical text GENERATED ALWAYS AS (lower(url)) STORED;
CREATE UNIQUE INDEX IF NOT EXISTS ux_linkedin_links_canonical ON public.linkedin_links (url_canonical);
-- Optional supporting columns used by the local ingestors
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS category text;          -- posts|jobs|other|external
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS source text;            -- e.g., google_sheet:SheetName
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS sheet_name text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS tab text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS row_number int;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS date_in_source text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS extracted_at timestamptz DEFAULT now();
```

## Combined CSV → DB import with backup
Generate one CSV from all three sheets (adjust URLs/month as needed):
```bash
"$PWD/.venv/bin/python" -m src.app ingest-combined-csv \
  --urls "URL1,URL2,URL3" \
  --month-filter aug \
  --output-csv ./storage/ingest/google_sheets/combined_august.csv
```
Load into DB and export backup of newly-inserted rows (requires psql and DATABASE_URL):
```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/data_lake
ts=$(date -u +"%Y%m%d-%H%M%S")
backup="./storage/backups/links_inserted_${ts}.csv"
mkdir -p "$(dirname "$backup")"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<SQL
-- ensure columns (idempotent)
ALTER TABLE public.linkedin_links ALTER COLUMN url TYPE text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS url_canonical text GENERATED ALWAYS AS (lower(url)) STORED;
CREATE UNIQUE INDEX IF NOT EXISTS ux_linkedin_links_canonical ON public.linkedin_links (url_canonical);
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS category text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS source text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS sheet_name text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS tab text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS row_number int;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS date_in_source text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS extracted_at timestamptz DEFAULT now();

-- staging load
DROP TABLE IF EXISTS tmp_links; 
CREATE TEMP TABLE tmp_links (
  date text, company text, role text, location text, url text, sheet_name text, tab_title text, row_number int
);
\copy tmp_links (date,company,role,location,url,sheet_name,tab_title,row_number) 
  FROM './storage/ingest/google_sheets/combined_august.csv' WITH (FORMAT csv, HEADER true);

-- upsert using canonical key
WITH upsert AS (
  INSERT INTO public.linkedin_links (url, sheet_name, row_number, extracted_at, source, tab, date_in_source, category)
  SELECT url, sheet_name, row_number, now(), CONCAT('google_sheet:',COALESCE(sheet_name,'')), tab_title, date,
         CASE WHEN url LIKE 'https://www.linkedin.com/posts%' THEN 'posts'
              WHEN url LIKE 'https://www.linkedin.com/jobs%'  THEN 'jobs'
              WHEN url LIKE 'https://www.linkedin.com/%'      THEN 'other'
              ELSE 'external' END
  FROM tmp_links t
  ON CONFLICT (url_canonical) DO UPDATE
    SET sheet_name=EXCLUDED.sheet_name,
        row_number=EXCLUDED.row_number,
        extracted_at=now(),
        source=EXCLUDED.source,
        tab=EXCLUDED.tab,
        date_in_source=EXCLUDED.date_in_source,
        category=EXCLUDED.category
  RETURNING *
)
SELECT 1;

-- backup just the rows inserted in this run (by comparing created_at ~ now())
\copy (
  SELECT id,url,sheet_name,row_number,extracted_at,source,tab,date_in_source,category
  FROM public.linkedin_links
  WHERE extracted_at > now() - interval '5 minutes'  -- coarse window for this run
  ORDER BY id
) TO :'backup' WITH (FORMAT csv, HEADER true);
SQL
echo "Backup written to: $backup"
```
