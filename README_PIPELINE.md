# LinkedIn Scraper Pipeline

A comprehensive pipeline for extracting LinkedIn posts and job information from Google Sheets, storing data in PostgreSQL, and scraping LinkedIn content with Playwright.

## 🎯 Overview

This pipeline provides an end-to-end solution for:

1. **Google Sheets Ingestion**: Extract LinkedIn URLs from Google Sheets
2. **Link Classification**: Automatically classify links as jobs, posts, or other
3. **Queue Management**: Manage scraping queues with retry logic and error handling  
4. **LinkedIn Scraping**: Extract content from LinkedIn posts using Playwright
5. **Data Storage**: Store raw HTML, screenshots, and extracted data in PostgreSQL
6. **Monitoring**: Track pipeline progress and scraping statistics

## 🏗️ Architecture

```
Google Sheets → Link Extraction → Database Import → Classification → Scraping Queue
      ↓              ↓                   ↓               ↓              ↓
   CSV Files    linkedin_links    linkedin_links   linkedin_posts_raw  Storage
                                 (status=queued)     (raw content)    (HTML/images)
```

### Key Components

- **Pipeline Orchestrator** (`src/pipeline/orchestrator.py`): Coordinates end-to-end workflow
- **Posts Router** (`src/routers/posts_router.py`): Manages post link queues and state transitions  
- **LinkedIn Scraper** (`apps/scraper-playwright/posts/scraper.py`): Unified Playwright-based scraper
- **Posts Worker** (`src/workers/posts_worker.py`): Processes scraping queues with concurrency control
- **Main CLI** (`linkedin_pipeline.py`): Unified command-line interface

## 📋 Requirements

### Dependencies
- Python 3.9+
- PostgreSQL 12+
- Google Sheets API credentials

### Python Packages
```bash
pip install -r requirements.txt
```

Key packages:
- `playwright` - Browser automation
- `psycopg[binary]>=3.1.19` - PostgreSQL adapter  
- `google-api-python-client` - Google Sheets API
- `beautifulsoup4` - HTML parsing
- `PyYAML` - Configuration files

### Browser Setup
```bash
# Install Playwright browsers
playwright install chromium
```

## 🚀 Quick Start

### 1. Environment Setup

Create `.env` file:
```bash
# Required
DATABASE_URL=postgresql://user:password@localhost:5432/linkedin_scraper

# Optional - Google Sheets URLs
GOOGLE_SHEETS_URLS=https://docs.google.com/spreadsheets/d/...,https://docs.google.com/...

# Optional - Google API credentials paths  
GOOGLE_OAUTH_CLIENT_JSON=./.secrets/google_client.json
GOOGLE_OAUTH_TOKEN_JSON=./.secrets/google_token.json
```

### 2. Database Setup

```bash
# Create database
createdb linkedin_scraper

# Apply migrations
python linkedin_pipeline.py migrate-database
```

### 3. Google Sheets API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google Sheets API
3. Create OAuth 2.0 credentials
4. Download client JSON and save as `.secrets/google_client.json`

### 4. Run Complete Pipeline

```bash
# Full pipeline from sheets to scraped data
python linkedin_pipeline.py run-full-pipeline --max-scrape 20

# Or run individual stages
python linkedin_pipeline.py ingest-google-sheets
python linkedin_pipeline.py classify-links  
python linkedin_pipeline.py scrape-posts --batch-size 10
```

## 📚 Usage Guide

### Command Reference

#### Pipeline Commands
```bash
# Complete pipeline
python linkedin_pipeline.py run-full-pipeline [--sheets-urls URL1,URL2] [--max-scrape 20]

# Individual stages
python linkedin_pipeline.py ingest-google-sheets --urls "url1,url2"
python linkedin_pipeline.py import-to-database --csv links.csv
python linkedin_pipeline.py classify-links
```

#### Scraping Commands  
```bash
# Process queued posts
python linkedin_pipeline.py scrape-posts --batch-size 10 --concurrent 2

# Scrape single post
python linkedin_pipeline.py scrape-single-post --url "https://linkedin.com/posts/..."

# Run continuous worker
python linkedin_pipeline.py run-posts-worker --batch-size 5 --sleep 10
```

#### Monitoring Commands
```bash
# Overall pipeline status
python linkedin_pipeline.py pipeline-status

# Detailed scraping statistics  
python linkedin_pipeline.py scraping-stats

# Storage usage information
python linkedin_pipeline.py storage-info

# Reset failed scraping attempts
python linkedin_pipeline.py reset-failed
```

### Configuration Options

#### Environment Variables
- `DATABASE_URL` - PostgreSQL connection string (required)
- `GOOGLE_SHEETS_URLS` - Comma-separated Google Sheets URLs  
- `SHEETS_CONFIG` - Path to YAML config file with sheet URLs
- `GOOGLE_OAUTH_CLIENT_JSON` - Path to Google OAuth client credentials
- `GOOGLE_OAUTH_TOKEN_JSON` - Path to stored OAuth tokens

#### Command Line Options
- `--database-url` - Override DATABASE_URL environment variable
- `--storage` - Storage base directory (default: `./storage`) 
- `--headless` - Run browser in headless mode (default: true)
- `--concurrent N` - Number of concurrent scrapers (default: 2)
- `--batch-size N` - Batch size for processing (default: 10)
- `--verbose` - Enable verbose output

## 🗄️ Database Schema

### linkedin_links
Primary table for storing LinkedIn URLs from Google Sheets:
```sql
id BIGSERIAL PRIMARY KEY
url TEXT NOT NULL
url_canonical TEXT GENERATED -- normalized URL
classification TEXT -- 'job', 'post', 'unknown'  
status TEXT -- 'new', 'queued', 'scraping', 'scraped', 'error'
attempt_count INT DEFAULT 0
next_attempt_at TIMESTAMPTZ
sheet_name TEXT
tab TEXT  
source TEXT
extracted_at TIMESTAMPTZ DEFAULT now()
```

### linkedin_posts_raw  
Storage for scraped LinkedIn post content:
```sql
id BIGSERIAL PRIMARY KEY
link_id BIGINT REFERENCES linkedin_links(id)
url TEXT NOT NULL
raw_html_path TEXT -- relative path to HTML file
screenshot_path TEXT -- relative path to screenshot
metadata_json_path TEXT -- relative path to metadata JSON
status TEXT -- 'pending', 'scraping', 'completed', 'failed', 'retry'
scraped_at TIMESTAMPTZ
scrape_metadata JSONB -- technical scraping metadata
extracted_data JSONB -- parsed post content
attempt_count INT DEFAULT 0
error_message TEXT
trace_id TEXT
```

### events
Audit trail for link state transitions:
```sql
id BIGSERIAL PRIMARY KEY  
kind TEXT NOT NULL -- 'link.new', 'link.classified', etc
link_id BIGINT REFERENCES linkedin_links(id)
payload JSONB
created_at TIMESTAMPTZ DEFAULT now()
```

## 📁 File Storage Structure

Scraped content is organized in the storage directory:
```
./storage/
├── posts/
│   └── 20241231/        # Date-based directories
│       └── link_123/    # Link ID directories  
│           ├── content.html
│           ├── screenshot.png
│           └── metadata.json
├── backups/             # Database backup CSVs
└── ingest/              # Google Sheets extraction outputs
    └── google_sheets/
        └── 20241231-143022/
            └── links.csv
```

## 🔄 Workflow Examples

### Basic Workflow
1. **Ingest**: Extract URLs from Google Sheets → CSV
2. **Import**: Load CSV into `linkedin_links` table  
3. **Classify**: Categorize links and set status to 'queued'
4. **Scrape**: Process queued post links with Playwright
5. **Store**: Save HTML, screenshots, and metadata

### Continuous Processing  
```bash
# Terminal 1: Run continuous worker
python linkedin_pipeline.py run-posts-worker

# Terminal 2: Add new data periodically  
python linkedin_pipeline.py ingest-google-sheets
python linkedin_pipeline.py classify-links
```

### Error Recovery
```bash
# Check what failed
python linkedin_pipeline.py scraping-stats

# Reset failed attempts  
python linkedin_pipeline.py reset-failed

# Process queue again
python linkedin_pipeline.py scrape-posts
```

## 🐛 Troubleshooting

### Common Issues

**Google Sheets API Authentication**
```bash
# Check credentials files exist
ls -la .secrets/

# Test authentication manually
python -c "from src.extractor.google_sheets.client import ensure_credentials; ensure_credentials()"
```

**Database Connection Issues**  
```bash
# Test database connection
psql "$DATABASE_URL" -c "SELECT version();"

# Check if tables exist
python linkedin_pipeline.py migrate-database
```

**Playwright Browser Issues**
```bash
# Reinstall browsers
playwright install --force

# Test browser launch
python -c "import asyncio; from playwright.async_api import async_playwright; asyncio.run(async_playwright().start().chromium.launch())"
```

**LinkedIn Access Issues**
- LinkedIn may show login walls for automated requests
- Consider using proxies or residential IPs for production
- Respect rate limits and implement delays between requests
- Monitor for anti-bot detection patterns

### Error Messages

| Error | Solution |
|-------|----------|
| `DATABASE_URL is required` | Set DATABASE_URL environment variable |
| `Google API client libraries not installed` | Run `pip install google-api-python-client` |
| `Playwright not installed` | Run `pip install playwright && playwright install` |
| `LinkedIn login wall encountered` | Check IP/proxy settings, implement authentication |
| `Timeout while loading page` | Increase timeout values, check network connectivity |

## 🔧 Development

### Project Structure
```
├── src/
│   ├── pipeline/           # Pipeline orchestration
│   ├── routers/           # Queue management  
│   ├── workers/           # Background workers
│   ├── ingest/            # Google Sheets ingestion
│   ├── db/               # Database operations
│   └── extractor/        # Content extraction utilities
├── apps/
│   └── scraper-playwright/
│       └── posts/        # LinkedIn post scraping
├── linkedin_pipeline.py  # Main CLI interface
└── requirements.txt
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test modules  
pytest tests/test_router.py
pytest tests/test_scraper.py
```

### Adding New Link Types

1. **Update Classification Logic** (`src/db/classify_and_queue.py`):
   ```python
   # Add new classification type
   classification = CASE
       WHEN url LIKE '%linkedin.com/jobs%' THEN 'job'
       WHEN url LIKE '%linkedin.com/posts%' THEN 'post'  
       WHEN url LIKE '%linkedin.com/company%' THEN 'company'  -- NEW
       ELSE 'unknown'
   ```

2. **Create New Router** (`src/routers/companies_router.py`):
   ```python
   # Similar to posts_router.py but for companies
   ```

3. **Add Storage Schema**:
   ```sql
   CREATE TABLE linkedin_companies_raw (...);
   ```

## 📊 Monitoring & Analytics

### Key Metrics to Track
- **Ingestion Rate**: Links extracted per hour from Google Sheets
- **Classification Accuracy**: Percentage of correctly classified links
- **Scraping Success Rate**: Percentage of successful scrapes  
- **Queue Depth**: Number of pending links by type
- **Error Rates**: Failed scrapes by error type
- **Storage Growth**: Disk usage over time

### Grafana Dashboard Queries (if using Prometheus)
```promql
# Scraping success rate
rate(linkedin_scrapes_successful_total[5m]) / rate(linkedin_scrapes_total[5m])

# Queue depth by status  
linkedin_queue_depth{status="queued"}

# Storage usage
linkedin_storage_bytes / (1024^3)
```

## 🚦 Production Deployment

### Recommended Architecture
- **Application Server**: Run pipeline orchestrator and API
- **Worker Nodes**: Dedicated scraping workers with browser pools
- **Database**: PostgreSQL with read replicas
- **Storage**: Shared filesystem or object storage (S3/GCS)
- **Monitoring**: Prometheus + Grafana for metrics
- **Logging**: Structured logging with correlation IDs

### Docker Deployment
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget gnupg && \
    playwright install-deps

COPY requirements.txt .
RUN pip install -r requirements.txt && \
    playwright install chromium

COPY . /app
WORKDIR /app

CMD ["python", "linkedin_pipeline.py", "run-posts-worker"]
```

### Kubernetes Example
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: linkedin-scraper-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: linkedin-scraper-worker
  template:
    metadata:
      labels:
        app: linkedin-scraper-worker
    spec:
      containers:
      - name: worker
        image: linkedin-scraper:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: linkedin-scraper-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"  
            cpu: "1000m"
```

## 📝 License

[Your License Here]

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Commit your changes (`git commit -m 'Add amazing feature'`)  
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Documentation**: [Wiki](https://github.com/your-repo/wiki)

---

*Built with ❤️ for efficient LinkedIn data extraction*
