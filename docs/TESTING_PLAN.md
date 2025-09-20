# LinkedIn Pipeline Testing Plan

## Overview

This document outlines comprehensive testing for the unified LinkedIn pipeline with multiple validation points to catch issues early in the complex orchestration chain.

## Test Architecture

```
Unit Tests → Integration Tests → Component Tests → End-to-End Tests
    ↓              ↓                  ↓               ↓
Individual    Task Chains       Full Components   Production Flow
Functions                                        
```

## Pre-Testing Setup

### Environment Requirements
```bash
# Required services
DATABASE_URL=postgresql://user:pass@localhost:5432/data_lake
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

-- Required tables (auto-created by tasks, but verify schema)
-- linkedin_links, linkedin_posts_raw, linkedin_jobs_raw
```

---

## 1. Unit Tests

### 1.1 Configuration Tests
```python
def test_celery_app_configuration():
    """Verify Celery app loads with correct settings"""
    from apps.orchestration.celery_app import app
    assert app.conf.task_routes is not None
    assert "ingest" in str(app.conf.task_routes)
    assert app.conf.beat_schedule is not None

def test_environment_variable_parsing():
    """Test environment variable handling"""
    import os
    os.environ['PIPELINE_CRON'] = '0 */3 * * *'
    # Reload app and verify schedule updated
```

### 1.2 Task Function Tests
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

### 1.3 Message Schema Tests  
```python
def test_message_schema_validation():
    """Verify standardized message format"""
    message = {
        "link_id": 123,
        "url": "https://linkedin.com/posts/test",
        "type": "post",
        "trace_id": "abc12345",
        "attempt": 1
    }
    # Validate all required fields present
    # Test scraper functions accept this format
```

---

## 2. Component Tests (Isolated)

### 2.1 Ingestion Component Test

**Test Case:** `test_ingest_links_component`

**Setup:**
```bash
# Create test Google Sheet with known content
# 3 rows: 2 posts, 1 job, known URLs
```

**Execution:**
```python
def test_ingest_links_isolated():
    """Test ingestion without dependencies"""
    from apps.orchestration.tasks import ingest_links
    
    # Mock environment with test sheet
    result = ingest_links(trace_id="test123")
    
    # Assertions
    assert result["ok"] == True
    assert "output_csv" in result
    assert os.path.exists(result["output_csv"])
    
    # Verify CSV content
    import pandas as pd
    df = pd.read_csv(result["output_csv"])
    assert len(df) >= 1  # At least one row
    assert "url" in df.columns
```

**Success Criteria:**
- ✅ CSV file created with timestamp
- ✅ Contains expected LinkedIn URLs  
- ✅ Correct columns: date, company, role, location, url
- ✅ Trace ID propagated

### 2.2 Import Component Test

**Test Case:** `test_import_csv_component`

**Setup:**
```bash
# Create test CSV with known LinkedIn URLs
```

**Execution:**
```python
def test_import_csv_isolated():
    """Test CSV import without dependencies"""
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
    
    # Assertions
    assert result["ok"] == True
    assert "backup_csv" in result
    
    # Verify database
    with psycopg.connect(DATABASE_URL) as conn:
        count = conn.execute("SELECT count(*) FROM linkedin_links").fetchone()[0]
        assert count >= 2
```

**Success Criteria:**
- ✅ Records inserted into `linkedin_links`
- ✅ Unique constraint on `url_canonical` works
- ✅ Backup CSV created
- ✅ Re-running doesn't create duplicates (idempotent)

### 2.3 Classification Component Test

**Test Case:** `test_classify_links_component`

**Execution:**
```python  
def test_classify_links_isolated():
    """Test classification without dependencies"""
    from apps.orchestration.tasks import classify_links
    
    # Setup: Insert test links first
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""
            INSERT INTO linkedin_links (url) VALUES 
            ('https://linkedin.com/posts/test'),
            ('https://linkedin.com/jobs/view/12345')
        """)
        conn.commit()
    
    import_result = {"ok": True, "trace_id": "test123"}
    result = classify_links(import_result)
    
    # Assertions
    assert result["ok"] == True
    
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
- ✅ Other URLs → appropriate classification
- ✅ Status transitions: new → queued

### 2.4 Router Component Test

**Test Case:** `test_route_links_component`

**Execution:**
```python
def test_route_links_isolated():
    """Test routing without actual scraping"""
    from apps.orchestration.tasks import route_links
    from unittest.mock import patch
    
    # Setup: Create queued links
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/posts/route_test', 'post', 'queued'),
            ('https://linkedin.com/jobs/view/route_test', 'job', 'queued')
        """)
        conn.commit()
    
    # Mock the scrapers to avoid actual scraping
    with patch('apps.orchestration.scrapers.scrape_job.apply_async') as mock_job, \
         patch('apps.orchestration.scrapers.scrape_post.apply_async') as mock_post:
        
        classify_result = {"ok": True, "trace_id": "test123"}
        result = route_links(classify_result)
        
        # Assertions
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

### 2.5 Scraper Component Tests

**Test Case:** `test_scrape_job_component`

**Execution:**
```python
def test_scrape_job_isolated():
    """Test job scraping with mocked LinkedIn"""
    from apps.orchestration.scrapers import scrape_job
    from unittest.mock import patch
    
    # Setup: Create link in scraping-ready state
    with psycopg.connect(DATABASE_URL) as conn:
        link_id = conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/jobs/view/test_job', 'job', 'queued')
            RETURNING id
        """).fetchone()[0]
        conn.commit()
    
    # Mock the actual scraper to avoid hitting LinkedIn
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
        
        # Assertions
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

---

## 3. Integration Tests (Task Chains)

### 3.1 Chain Integration Test

**Test Case:** `test_ingest_to_route_chain`

**Execution:**
```python
def test_full_task_chain():
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

---

## 4. End-to-End Tests

### 4.1 Full Pipeline Test

**Test Case:** `test_complete_pipeline_e2e`

**Setup:**
- Real Google Sheet with 3 test rows (2 posts, 1 job)  
- LinkedIn test account with limited permissions
- All services running (Redis, PostgreSQL, Celery worker)

**Execution:**
```bash
# Terminal 1: Start worker
make orchestration.worker

# Terminal 2: Start beat (optional for manual trigger)
make orchestration.beat  

# Terminal 3: Trigger one-shot pipeline
make orchestration.pipeline

# Monitor logs and database
```

**Validation Script:**
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

---

## 5. Monitoring & Observability Tests

### 5.1 Queue Depth Monitoring

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

### 5.2 Error Rate Monitoring  

```python
def test_error_rate_tracking():
    """Track error rates across pipeline stages"""
    
    # Inject deliberate failures
    # Monitor error counts
    # Verify exponential backoff working
    # Check dead letter queue behavior
```

---

## 6. Performance Tests

### 6.1 Throughput Test

```python
def test_pipeline_throughput():
    """Test pipeline with larger dataset"""
    
    # Create CSV with 100+ links
    # Measure time from ingest to completion
    # Verify no memory leaks
    # Check concurrent task handling
```

### 6.2 Concurrency Test

```python
def test_concurrent_workers():
    """Test multiple workers processing same queues"""
    
    # Start 2+ workers
    # Ensure no duplicate processing
    # Verify task distribution
```

---

## Test Execution Plan

### Phase 1: Unit & Component Tests (30 min)
```bash
pytest tests/unit/ -v
pytest tests/components/ -v  
```

### Phase 2: Integration Tests (45 min)
```bash
pytest tests/integration/ -v
```

### Phase 3: End-to-End Test (60 min)
```bash
# Manual execution with real data
# Full monitoring and validation
```

### Phase 4: Performance & Load Tests (30 min)  
```bash
pytest tests/performance/ -v
```

---

## Success Criteria Summary

**✅ Pipeline Health Indicators:**
- All unit tests pass
- Task chains complete without errors
- Database state consistent after each stage  
- No duplicate link processing (idempotency)
- Error handling works (failed links → 'error' + backoff)
- Artifacts saved to correct storage paths
- Single beat scheduler running (no conflicts)
- Queue depths reasonable (not backing up)

**✅ Data Quality Checks:**
- Post URLs → 'post' classification → `linkedin_posts_raw`
- Job URLs → 'job' classification → `linkedin_jobs_raw`  
- HTML/screenshot artifacts present
- Canonical URL deduplication working
- Status flow: new → queued → scraping → scraped (or error)

**📊 Performance Benchmarks:**
- Ingest: <30s for 100 links
- Import: <10s for 100 links
- Classification: <5s for 100 links  
- Routing: <2s for 100 links
- Per-link scraping: <30s average

This comprehensive testing plan ensures every component works in isolation and integration! 🧪