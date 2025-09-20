# LinkedIn Pipeline Testing Documentation

## Overview

This document provides comprehensive testing documentation for the unified LinkedIn scraping pipeline. The testing strategy ensures reliable operation of the orchestration system, from Google Sheets ingestion through LinkedIn scraping and data persistence.

## Testing Architecture

```
Unit Tests → Component Tests → Integration Tests → End-to-End Tests
    ↓              ↓                ↓                   ↓
Individual      Isolated        Task Chains      Production Flow
Functions       Components                              
```

## Quick Start

```bash
# Setup test environment
make setup

# Ensure .env file exists with your configuration
cp .env.example .env  # Edit with your values

# Run different test categories
make test.unit          # Unit tests (no external dependencies)
make test.components    # Component tests (may use real data if credentials available)
make test.live          # Live tests with real Google Sheets data
make test.e2e           # End-to-end pipeline test

# Run all tests (excluding live tests)
make test
```

### Real Data Testing

This testing setup prioritizes **real data testing** over extensive mocking:

- **Live Tests (`tests/live/`)**: Use actual Google Sheets, database, and services
- **Component Tests (`tests/components/`)**: Test with real data when credentials available, skip otherwise
- **Unit Tests (`tests/unit/`)**: Test configuration and schema validation without external calls

**Benefits:**
- Faster test development (no complex mocking)
- Real validation of Google Sheets access and data structure
- Actual LinkedIn URL extraction and classification
- True end-to-end pipeline validation

## Test Categories

### 1. Unit Tests (`tests/unit/`)

**Purpose:** Test individual functions and configuration in isolation.

#### 1.1 Configuration Tests (`test_orchestration_config.py`)

- **`test_celery_app_configuration()`**
  - Validates Celery app loads with correct settings
  - Verifies task routing configuration
  - Checks beat schedule existence
  - Tests queue assignments (ingest, route, scrape.job, scrape.post)

- **`test_environment_variable_handling()`**
  - Tests custom PIPELINE_CRON parsing
  - Validates environment variable defaults
  - Verifies schedule updates with custom settings

- **`test_database_url_validation()`**
  - Tests valid DATABASE_URL handling
  - Verifies error on missing DATABASE_URL
  - Validates connection string format

- **`test_url_and_month_resolution()`**
  - Tests GOOGLE_SHEETS_URLS parsing (comma-separated)
  - Validates MONTH_FILTER handling
  - Checks URL list generation

- **`test_message_schema_validation()`**
  - Validates standardized message format
  - Tests required fields: link_id, url, type, trace_id, attempt
  - Checks field type validation
  - Tests invalid message handling

#### 1.2 Task Function Tests

```python
def test_resolve_urls_and_month():
    """Test URL resolution from environment"""
    from apps.orchestration.tasks import _resolve_urls_and_month
    urls, month = _resolve_urls_and_month()
    assert isinstance(urls, list)
    assert isinstance(month, str)

def test_get_database_url():
    """Test database URL validation"""
    from apps.orchestration.tasks import _get_database_url
    # Test with valid URL
    # Test with missing URL (should raise)
```

### 2. Component Tests (`tests/components/`)

**Purpose:** Test each pipeline component in isolation with controlled inputs.

#### 2.1 Ingestion Component (`test_ingest_component.py`)

```python
def test_ingest_links_component():
    """Test Google Sheets ingestion without dependencies"""
    from apps.orchestration.tasks import ingest_links
    
    # Mock environment with test sheet
    result = ingest_links(trace_id="test123")
    
    # Assertions
    assert result["ok"] == True
    assert "output_csv" in result
    assert os.path.exists(result["output_csv"])
    
    # Verify CSV content
    df = pd.read_csv(result["output_csv"])
    assert len(df) >= 1
    assert "url" in df.columns
```

**Success Criteria:**
- ✅ CSV file created with timestamp
- ✅ Contains expected LinkedIn URLs  
- ✅ Correct columns: date, company, role, location, url
- ✅ Trace ID propagated

#### 2.2 Import Component (`test_import_component.py`)

```python
def test_import_csv_component():
    """Test CSV import to database without dependencies"""
    from apps.orchestration.tasks import import_csv
    
    # Create test CSV
    test_csv = create_test_csv([
        {"url": "https://linkedin.com/posts/test1", "company": "TestCorp"},
        {"url": "https://linkedin.com/jobs/view/12345", "company": "JobCorp"}
    ])
    
    # Mock ingest result
    ingest_result = {
        "ok": True,
        "output_csv": test_csv,
        "trace_id": "test123"
    }
    
    result = import_csv(ingest_result)
    
    # Verify database insertion
    with psycopg.connect(DATABASE_URL) as conn:
        count = conn.execute("SELECT count(*) FROM linkedin_links").fetchone()[0]
        assert count >= 2
```

**Success Criteria:**
- ✅ Records inserted into `linkedin_links`
- ✅ Unique constraint on `url_canonical` works
- ✅ Backup CSV created
- ✅ Idempotent (re-running doesn't create duplicates)

#### 2.3 Classification Component (`test_classify_component.py`)

```python
def test_classify_links_component():
    """Test link classification without dependencies"""
    from apps.orchestration.tasks import classify_links
    
    # Setup test data
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""
            INSERT INTO linkedin_links (url) VALUES 
            ('https://linkedin.com/posts/test'),
            ('https://linkedin.com/jobs/view/12345')
        """)
        conn.commit()
    
    import_result = {"ok": True, "trace_id": "test123"}
    result = classify_links(import_result)
    
    # Verify classification
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute("""
            SELECT url, classification, status 
            FROM linkedin_links 
            WHERE url LIKE '%test%' OR url LIKE '%12345%'
        """).fetchall()
        
        post_row = [r for r in rows if 'posts' in r[0]][0]
        job_row = [r for r in rows if 'jobs' in r[0]][0]
        
        assert post_row[1] == 'post'  # classification
        assert post_row[2] == 'queued'  # status
        assert job_row[1] == 'job'
        assert job_row[2] == 'queued'
```

**Success Criteria:**
- ✅ Post URLs → classification='post', status='queued'
- ✅ Job URLs → classification='job', status='queued'  
- ✅ Status transitions: new → queued

#### 2.4 Router Component (`test_router_component.py`)

```python
def test_route_links_component():
    """Test routing without actual scraping"""
    from apps.orchestration.tasks import route_links
    from unittest.mock import patch
    
    # Setup queued links
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/posts/route_test', 'post', 'queued'),
            ('https://linkedin.com/jobs/view/route_test', 'job', 'queued')
        """)
        conn.commit()
    
    # Mock scrapers to avoid actual scraping
    with patch('apps.orchestration.scrapers.scrape_job.apply_async') as mock_job, \
         patch('apps.orchestration.scrapers.scrape_post.apply_async') as mock_post:
        
        classify_result = {"ok": True, "trace_id": "test123"}
        result = route_links(classify_result)
        
        # Verify routing
        assert result["ok"] == True
        assert result["routed"]["jobs"] == 1
        assert result["routed"]["posts"] == 1
        
        # Verify tasks were enqueued
        mock_job.apply_async.assert_called_once()
        mock_post.apply_async.assert_called_once()
        
        # Check message format
        job_message = mock_job.apply_async.call_args[1]['args'][0]
        assert job_message["type"] == "job"
        assert "link_id" in job_message
        assert "trace_id" in job_message
```

**Success Criteria:**
- ✅ Queued jobs → `scrape_job.apply_async()` called
- ✅ Queued posts → `scrape_post.apply_async()` called
- ✅ Correct message format passed to scrapers
- ✅ Count of routed items matches queued items

#### 2.5 Scraper Components (`test_scrapers_component.py`)

```python
def test_scrape_job_component():
    """Test job scraping with mocked LinkedIn"""
    from apps.orchestration.scrapers import scrape_job
    from unittest.mock import patch
    
    # Setup link in scraping-ready state
    with psycopg.connect(DATABASE_URL) as conn:
        link_id = conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/jobs/view/test_job', 'job', 'queued')
            RETURNING id
        """).fetchone()[0]
        conn.commit()
    
    # Mock scraper to avoid hitting LinkedIn
    mock_scrape_result = {
        "html_path": "./storage/jobs/123/job.html",
        "screenshot_path": "./storage/jobs/123/screenshot.png", 
        "role_title": "Software Engineer",
        "company_name": "Test Company",
        "location": "San Francisco, CA"
    }
    
    with patch('src.scraper.dev.scrape_single_job', return_value=mock_scrape_result):
        message = {
            "link_id": link_id,
            "url": "https://linkedin.com/jobs/view/test_job",
            "type": "job",
            "trace_id": "test123",
            "attempt": 1
        }
        
        result = scrape_job.apply(args=[message])
        
        # Verify result
        assert result["ok"] == True
        assert result["link_id"] == link_id
        
        # Verify database updates
        with psycopg.connect(DATABASE_URL) as conn:
            # Check link status
            link_status = conn.execute(
                "SELECT status FROM linkedin_links WHERE id = %s", 
                (link_id,)
            ).fetchone()[0]
            assert link_status == 'scraped'
            
            # Check raw job record
            job_raw = conn.execute(
                "SELECT role_title, company_name FROM linkedin_jobs_raw WHERE link_id = %s",
                (link_id,)
            ).fetchone()
            assert job_raw[0] == "Software Engineer" 
            assert job_raw[1] == "Test Company"
```

**Success Criteria:**
- ✅ Link claimed (status='scraping') before scraping
- ✅ LinkedIn scraper called with correct URL
- ✅ Results saved to `linkedin_jobs_raw`
- ✅ Link marked as 'scraped'
- ✅ Error handling: failed scrapes → status='error' + backoff

### 3. Integration Tests (`tests/integration/`)

**Purpose:** Test task chains and component interactions.

#### 3.1 Task Chain Tests (`test_chain_integration.py`)

```python
def test_ingest_to_route_chain():
    """Test complete task chain without actual scraping"""
    from apps.orchestration.tasks import pipeline_chain
    from unittest.mock import patch
    
    # Mock scrapers to avoid actual LinkedIn requests
    with patch('apps.orchestration.scrapers.scrape_job.apply_async'), \
         patch('apps.orchestration.scrapers.scrape_post.apply_async'):
        
        result = pipeline_chain.apply()
        
        # Wait for chain completion
        chain_id = result["chain_id"]
        # Poll chain status until complete
        
        # Verify each stage completed
        # Check database state after each stage
```

#### 3.2 Cross-Component Data Flow (`test_data_flow.py`)

- Tests message passing between components
- Validates trace_id propagation
- Checks error propagation and handling
- Verifies idempotency across components

### 4. End-to-End Tests (`tests/e2e/`)

**Purpose:** Test complete pipeline with real services.

#### 4.1 Full Pipeline Test (`test_complete_pipeline.py`)

**Setup:**
- Real Google Sheet with test data (3 rows: 2 posts, 1 job)
- LinkedIn test account with limited permissions
- All services running (Redis, PostgreSQL, Celery worker)

**Execution:**
```bash
# Terminal 1: Start worker
make orchestration.worker

# Terminal 2: Trigger pipeline
make orchestration.pipeline

# Monitor logs and database
```

**Validation:**
```python
def test_e2e_pipeline():
    """Complete end-to-end pipeline test"""
    initial_count = get_link_count()
    
    # Trigger pipeline
    trigger_pipeline()
    
    # Wait and monitor progress
    wait_for_completion()
    
    # Verify results
    final_count = get_link_count()
    assert final_count > initial_count
    
    # Check artifacts
    assert os.path.exists("./storage/posts/")
    assert os.path.exists("./storage/jobs/")
    
    # Verify scraping results
    scraped_links = get_scraped_links()
    assert len(scraped_links) > 0
    
    for link in scraped_links:
        if link.classification == 'post':
            assert post_raw_exists(link.id)
        elif link.classification == 'job':  
            assert job_raw_exists(link.id)
```

### 5. Monitoring & Observability Tests (`tests/monitoring/`)

#### 5.1 Queue Monitoring (`test_queue_monitoring.py`)

```python
def test_queue_monitoring():
    """Monitor queue depths during pipeline run"""
    from celery import Celery
    
    app = Celery()  
    app.config_from_object('apps.orchestration.celery_app')
    
    inspect = app.control.inspect()
    
    # Check queue lengths
    active_queues = inspect.active_queues()
    assert 'ingest' in active_queues
    assert 'route' in active_queues
    assert 'scrape.job' in active_queues
    assert 'scrape.post' in active_queues
```

#### 5.2 Error Rate Monitoring (`test_error_monitoring.py`)

- Track error rates across pipeline stages
- Verify exponential backoff working
- Check dead letter queue behavior
- Monitor retry mechanisms

### 6. Performance Tests (`tests/performance/`)

#### 6.1 Throughput Test (`test_throughput.py`)

```python
def test_pipeline_throughput():
    """Test pipeline with larger dataset"""
    
    # Create CSV with 100+ links
    # Measure time from ingest to completion
    # Verify no memory leaks
    # Check concurrent task handling
```

#### 6.2 Concurrency Test (`test_concurrency.py`)

```python
def test_concurrent_workers():
    """Test multiple workers processing same queues"""
    
    # Start 2+ workers
    # Ensure no duplicate processing
    # Verify task distribution
```

## Test Environment Setup

### Prerequisites

```bash
# Required services
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/data_lake_test
CELERY_BROKER_URL=redis://localhost:6379/0  
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Test data
GOOGLE_SHEETS_URLS="TEST_SHEET_URL_WITH_KNOWN_CONTENT"
MONTH_FILTER=aug
LINKEDIN_USERNAME=test-account@example.com
LINKEDIN_PASSWORD=test-password
```

### Test Database Setup

```sql
-- Create test database
CREATE DATABASE data_lake_test;

-- Switch to test database and run migrations
-- Tables: linkedin_links, linkedin_posts_raw, linkedin_jobs_raw
```

### Fixtures and Helpers (`tests/conftest.py`)

```python
@pytest.fixture(scope="session")
def test_env():
    """Setup test environment variables"""
    os.environ.update({
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/data_lake_test",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "CELERY_RESULT_BACKEND": "redis://localhost:6379/1",
        "GOOGLE_SHEETS_URLS": "https://docs.google.com/spreadsheets/d/test_sheet",
        "MONTH_FILTER": "aug"
    })

@pytest.fixture
def clean_database():
    """Clean database before each test"""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("TRUNCATE linkedin_links, linkedin_posts_raw, linkedin_jobs_raw")
        conn.commit()

class TestHelpers:
    @staticmethod
    def create_test_message(link_id, url, type_, trace_id, attempt=1):
        """Create standardized test message"""
        return {
            "link_id": link_id,
            "url": url,
            "type": type_,
            "trace_id": trace_id,
            "attempt": attempt
        }
    
    @staticmethod
    def assert_message_schema(message):
        """Validate message schema"""
        required_fields = ["link_id", "url", "type", "trace_id", "attempt"]
        for field in required_fields:
            assert field in message, f"Missing required field: {field}"
        assert isinstance(message["link_id"], int)
        assert isinstance(message["attempt"], int)
```

## Test Execution Plan

### Phase 1: Unit & Component Tests (30 min)
```bash
pytest tests/unit/ -v --tb=short
pytest tests/components/ -v --tb=short
```

### Phase 2: Integration Tests (45 min)
```bash
pytest tests/integration/ -v --tb=short
```

### Phase 3: End-to-End Test (60 min)
```bash
# Manual execution with real data
# Full monitoring and validation
pytest tests/e2e/ -v -s
```

### Phase 4: Performance & Load Tests (30 min)
```bash
pytest tests/performance/ -v --tb=short
```

## Success Criteria

### Pipeline Health Indicators

- ✅ All unit tests pass
- ✅ Task chains complete without errors
- ✅ Database state consistent after each stage  
- ✅ No duplicate link processing (idempotency)
- ✅ Error handling works (failed links → 'error' + backoff)
- ✅ Artifacts saved to correct storage paths
- ✅ Single beat scheduler running (no conflicts)
- ✅ Queue depths reasonable (not backing up)

### Data Quality Checks

- ✅ Post URLs → 'post' classification → `linkedin_posts_raw`
- ✅ Job URLs → 'job' classification → `linkedin_jobs_raw`  
- ✅ HTML/screenshot artifacts present
- ✅ Canonical URL deduplication working
- ✅ Status flow: new → queued → scraping → scraped (or error)

### Performance Benchmarks

- Ingest: <30s for 100 links
- Import: <10s for 100 links
- Classification: <5s for 100 links  
- Routing: <2s for 100 links
- Per-link scraping: <30s average

## Test Data Management

### Test Fixtures

- **Google Sheets Test Data:** 3 rows (2 posts, 1 job) with known URLs
- **Database Fixtures:** Pre-created links in various states
- **Mock Responses:** Standardized scraper responses
- **Error Scenarios:** Invalid URLs, network timeouts, LinkedIn blocks

### Test Data Cleanup

```python
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data after each test"""
    yield
    # Remove test CSV files
    # Clean test storage directories
    # Reset database state
```

## Continuous Integration

### CI Pipeline Integration

```yaml
# .github/workflows/test.yml
name: Test Pipeline
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:6
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run tests
        run: |
          make test
```

## Troubleshooting

### Common Issues

1. **Database Connection Failures**
   - Check PostgreSQL is running: `brew services list | grep postgres`
   - Verify connection string: `psql $DATABASE_URL`

2. **Redis Connection Failures**  
   - Check Redis is running: `brew services list | grep redis`
   - Test connection: `redis-cli ping`

3. **Celery Worker Issues**
   - Check worker logs: `celery -A apps.orchestration.celery_app worker --loglevel=info`
   - Verify task registration: `celery -A apps.orchestration.celery_app inspect registered`

4. **Test Data Issues**
   - Ensure test database exists: `createdb data_lake_test`
   - Check test sheet permissions
   - Verify LinkedIn test account access

### Debug Commands

```bash
# Check Celery app configuration
celery -A apps.orchestration.celery_app inspect conf

# Monitor queue activity  
celery -A apps.orchestration.celery_app flower

# Database inspection
psql $DATABASE_URL -c "SELECT count(*) FROM linkedin_links;"

# Test specific component
python -m pytest tests/components/test_ingest_component.py::test_ingest_links_component -v -s
```

This comprehensive testing documentation ensures robust validation of the unified LinkedIn pipeline across all components and integration points! 🧪