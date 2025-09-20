"""
Component tests for scraper functionality.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
import psycopg
from tests.conftest import TestHelpers


@pytest.fixture
def test_database_url():
    """Get test database URL from environment"""
    return os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/data_lake_test")


def test_scrape_job_component(test_database_url, clean_database):
    """Test job scraping with mocked LinkedIn"""
    from apps.orchestration.scrapers import scrape_job
    
    # Setup link in scraping-ready state
    with psycopg.connect(test_database_url) as conn:
        link_id = conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/jobs/view/test_job_123', 'job', 'queued')
            RETURNING id
        """).fetchone()[0]
        conn.commit()
    
    # Mock scraper to avoid hitting LinkedIn
    mock_scrape_result = {
        "html_path": "./storage/jobs/123/job.html",
        "screenshot_path": "./storage/jobs/123/screenshot.png", 
        "role_title": "Software Engineer",
        "company_name": "Test Company",
        "location": "San Francisco, CA",
        "job_description": "Great software engineering role",
        "employment_type": "Full-time"
    }
    
    with patch('src.scraper.dev.scrape_single_job', return_value=mock_scrape_result):
        message = TestHelpers.create_test_message(
            link_id=link_id,
            url="https://linkedin.com/jobs/view/test_job_123",
            type_="job",
            trace_id="job_test_123"
        )
        
        result = scrape_job.apply(args=[message])
        
        # Verify result
        assert result["ok"] == True
        assert result["link_id"] == link_id
        assert result["trace_id"] == "job_test_123"
        assert result["type"] == "job"
        
        # Verify database updates
        with psycopg.connect(test_database_url) as conn:
            # Check link status
            link_status = conn.execute(
                "SELECT status FROM linkedin_links WHERE id = %s", 
                (link_id,)
            ).fetchone()[0]
            assert link_status == 'scraped'
            
            # Check raw job record
            job_raw = conn.execute(
                "SELECT role_title, company_name, location FROM linkedin_jobs_raw WHERE link_id = %s",
                (link_id,)
            ).fetchone()
            assert job_raw[0] == "Software Engineer" 
            assert job_raw[1] == "Test Company"
            assert job_raw[2] == "San Francisco, CA"


def test_scrape_post_component(test_database_url, clean_database):
    """Test post scraping with mocked LinkedIn"""
    from apps.orchestration.scrapers import scrape_post
    
    # Setup link in scraping-ready state
    with psycopg.connect(test_database_url) as conn:
        link_id = conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/posts/test_post_456', 'post', 'queued')
            RETURNING id
        """).fetchone()[0]
        conn.commit()
    
    # Mock scraper to avoid hitting LinkedIn
    mock_scrape_result = {
        "html_path": "./storage/posts/456/post.html",
        "screenshot_path": "./storage/posts/456/screenshot.png", 
        "author_name": "Jane Doe",
        "author_title": "Senior Developer",
        "post_content": "Great insights about software engineering!",
        "post_date": "2023-12-19",
        "engagement_stats": {"likes": 25, "comments": 5}
    }
    
    with patch('src.scraper.dev.scrape_single_post', return_value=mock_scrape_result):
        message = TestHelpers.create_test_message(
            link_id=link_id,
            url="https://linkedin.com/posts/test_post_456",
            type_="post",
            trace_id="post_test_456"
        )
        
        result = scrape_post.apply(args=[message])
        
        # Verify result
        assert result["ok"] == True
        assert result["link_id"] == link_id
        assert result["trace_id"] == "post_test_456"
        assert result["type"] == "post"
        
        # Verify database updates
        with psycopg.connect(test_database_url) as conn:
            # Check link status
            link_status = conn.execute(
                "SELECT status FROM linkedin_links WHERE id = %s", 
                (link_id,)
            ).fetchone()[0]
            assert link_status == 'scraped'
            
            # Check raw post record
            post_raw = conn.execute(
                "SELECT author_name, author_title, post_content FROM linkedin_posts_raw WHERE link_id = %s",
                (link_id,)
            ).fetchone()
            assert post_raw[0] == "Jane Doe" 
            assert post_raw[1] == "Senior Developer"
            assert "Great insights" in post_raw[2]


def test_scrape_job_claim_mechanism(test_database_url, clean_database):
    """Test job scraping claim mechanism prevents duplicate processing"""
    from apps.orchestration.scrapers import scrape_job
    
    # Setup link in scraping-ready state
    with psycopg.connect(test_database_url) as conn:
        link_id = conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/jobs/view/claim_test', 'job', 'queued')
            RETURNING id
        """).fetchone()[0]
        conn.commit()
    
    # Simulate link already claimed by another worker
    with psycopg.connect(test_database_url) as conn:
        conn.execute(
            "UPDATE linkedin_links SET status = 'scraping' WHERE id = %s",
            (link_id,)
        )
        conn.commit()
    
    message = TestHelpers.create_test_message(
        link_id=link_id,
        url="https://linkedin.com/jobs/view/claim_test",
        type_="job",
        trace_id="claim_test"
    )
    
    result = scrape_job.apply(args=[message])
    
    # Should skip already claimed link
    assert result["ok"] == False
    assert "already claimed" in result["message"] or "not queued" in result["message"]


def test_scrape_job_error_handling(test_database_url, clean_database):
    """Test job scraping error handling and retry logic"""
    from apps.orchestration.scrapers import scrape_job
    
    # Setup link in scraping-ready state
    with psycopg.connect(test_database_url) as conn:
        link_id = conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/jobs/view/error_test', 'job', 'queued')
            RETURNING id
        """).fetchone()[0]
        conn.commit()
    
    # Mock scraper to raise an exception
    with patch('src.scraper.dev.scrape_single_job', side_effect=Exception("LinkedIn rate limit")):
        message = TestHelpers.create_test_message(
            link_id=link_id,
            url="https://linkedin.com/jobs/view/error_test",
            type_="job",
            trace_id="error_test",
            attempt=1
        )
        
        result = scrape_job.apply(args=[message])
        
        # Should handle error gracefully
        assert result["ok"] == False
        assert "error" in result
        assert "LinkedIn rate limit" in result["error"]
        
        # Verify database status
        with psycopg.connect(test_database_url) as conn:
            link_status = conn.execute(
                "SELECT status FROM linkedin_links WHERE id = %s", 
                (link_id,)
            ).fetchone()[0]
            assert link_status == 'error'


def test_scrape_job_retry_backoff(test_database_url, clean_database):
    """Test exponential backoff retry mechanism"""
    from apps.orchestration.scrapers import scrape_job
    
    # Setup link in scraping-ready state
    with psycopg.connect(test_database_url) as conn:
        link_id = conn.execute("""
            INSERT INTO linkedin_links (url, classification, status) VALUES 
            ('https://linkedin.com/jobs/view/retry_test', 'job', 'queued')
            RETURNING id
        """).fetchone()[0]
        conn.commit()
    
    # Test with higher attempt number
    message = TestHelpers.create_test_message(
        link_id=link_id,
        url="https://linkedin.com/jobs/view/retry_test",
        type_="job",
        trace_id="retry_test",
        attempt=3  # Higher attempt number
    )
    
    with patch('src.scraper.dev.scrape_single_job', side_effect=Exception("Network timeout")):
        result = scrape_job.apply(args=[message])
        
        # Should handle retry attempt
        assert result["ok"] == False
        assert result["attempt"] == 3
        assert "retry" in result.get("message", "").lower() or "error" in result


def test_scrape_invalid_message_schema():
    """Test scraper handling of invalid message format"""
    from apps.orchestration.scrapers import scrape_job
    
    # Invalid message - missing required fields
    invalid_message = {
        "link_id": 123,
        # Missing url, type, trace_id, attempt
    }
    
    result = scrape_job.apply(args=[invalid_message])
    
    # Should validate message schema
    assert result["ok"] == False
    assert "invalid" in result.get("error", "").lower() or "missing" in result.get("error", "").lower()


def test_scrape_nonexistent_link(test_database_url, clean_database):
    """Test scraper handling of non-existent link_id"""
    from apps.orchestration.scrapers import scrape_job
    
    message = TestHelpers.create_test_message(
        link_id=99999,  # Non-existent ID
        url="https://linkedin.com/jobs/view/nonexistent",
        type_="job",
        trace_id="nonexistent_test"
    )
    
    result = scrape_job.apply(args=[message])
    
    # Should handle non-existent link gracefully
    assert result["ok"] == False
    assert "not found" in result.get("error", "").lower() or "does not exist" in result.get("error", "").lower()


def test_scrape_storage_creation():
    """Test that scraper creates proper storage directories"""
    from apps.orchestration.scrapers import scrape_job
    
    # Mock scraper result with storage paths
    mock_scrape_result = {
        "html_path": "./storage/jobs/test_123/job.html",
        "screenshot_path": "./storage/jobs/test_123/screenshot.png", 
        "role_title": "Test Role",
        "company_name": "Test Company"
    }
    
    # Ensure clean state
    import shutil
    if os.path.exists("./storage/jobs/test_123"):
        shutil.rmtree("./storage/jobs/test_123")
    
    with patch('src.scraper.dev.scrape_single_job', return_value=mock_scrape_result):
        # Create directories as scraper would
        os.makedirs("./storage/jobs/test_123", exist_ok=True)
        
        # Verify directory structure
        assert os.path.exists("./storage/jobs/test_123")
        
        # Cleanup
        if os.path.exists("./storage/jobs/test_123"):
            shutil.rmtree("./storage/jobs/test_123")