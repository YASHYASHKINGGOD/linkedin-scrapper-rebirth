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
