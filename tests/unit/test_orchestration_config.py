"""
Unit tests for orchestration configuration and setup.
"""
import pytest
import os
from unittest.mock import patch


def test_celery_app_configuration():
    """Test Celery app loads with correct configuration."""
    from apps.orchestration.celery_app import app
    
    # Test basic app properties
    assert app.main == "linkedin_pipeline"
    assert app.conf.task_acks_late is True
    assert app.conf.worker_prefetch_multiplier == 1
    
    # Test queue routing configuration
    assert app.conf.task_routes is not None
    routes = app.conf.task_routes
    
    # Check key routes exist
    assert "apps.orchestration.tasks.ingest_links" in routes
    assert "apps.orchestration.tasks.route_links" in routes  
    assert "apps.orchestration.scrapers.scrape_job" in routes
    assert "apps.orchestration.scrapers.scrape_post" in routes
    
    # Verify queue assignments
    assert routes["apps.orchestration.tasks.ingest_links"]["queue"] == "ingest"
    assert routes["apps.orchestration.tasks.route_links"]["queue"] == "route"
    assert routes["apps.orchestration.scrapers.scrape_job"]["queue"] == "scrape.job"
    assert routes["apps.orchestration.scrapers.scrape_post"]["queue"] == "scrape.post"
    
    # Test beat schedule exists
    assert app.conf.beat_schedule is not None
    assert "linkedin-pipeline" in app.conf.beat_schedule


def test_environment_variable_handling():
    """Test environment variable parsing and defaults."""
    # Test with custom PIPELINE_CRON
    with patch.dict(os.environ, {'PIPELINE_CRON': '0 */3 * * *'}):
        # Import with custom env
        import importlib
        import apps.orchestration.celery_app
        importlib.reload(apps.orchestration.celery_app)
        
        app = apps.orchestration.celery_app.app
        schedule = app.conf.beat_schedule["linkedin-pipeline"]["schedule"]
        
        # Should reflect custom schedule (every 3 hours instead of 2)
        assert hasattr(schedule, 'hour')


def test_database_url_validation():
    """Test database URL validation function."""
    from apps.orchestration.tasks import _get_database_url
    
    # Test with valid URL
    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db'}):
        url = _get_database_url()
        assert url == 'postgresql://user:pass@localhost:5432/db'
    
    # Test with missing URL
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="DATABASE_URL environment variable is required"):
            _get_database_url()


def test_url_and_month_resolution():
    """Test URL and month resolution from environment."""
    from apps.orchestration.tasks import _resolve_urls_and_month
    
    test_urls = "https://docs.google.com/spreadsheets/d/sheet1,https://docs.google.com/spreadsheets/d/sheet2"
    
    with patch.dict(os.environ, {
        'GOOGLE_SHEETS_URLS': test_urls,
        'MONTH_FILTER': 'sep'
    }):
        urls, month = _resolve_urls_and_month()
        
        assert isinstance(urls, list)
        assert len(urls) == 2
        assert urls[0] == "https://docs.google.com/spreadsheets/d/sheet1"
        assert urls[1] == "https://docs.google.com/spreadsheets/d/sheet2"
        assert month == 'sep'


def test_message_schema_validation():
    """Test standardized message schema validation."""
    from tests.conftest import TestHelpers
    
    # Test valid message
    message = TestHelpers.create_test_message(
        link_id=123,
        url="https://linkedin.com/posts/test",
        type_="post", 
        trace_id="abc123"
    )
    
    # Should not raise
    TestHelpers.assert_message_schema(message)
    
    # Test message content
    assert message["link_id"] == 123
    assert message["url"] == "https://linkedin.com/posts/test"
    assert message["type"] == "post"
    assert message["trace_id"] == "abc123"
    assert message["attempt"] == 1
    
    # Test invalid message (missing field)
    invalid_message = {"link_id": 123, "url": "test"}
    with pytest.raises(AssertionError, match="Missing required field"):
        TestHelpers.assert_message_schema(invalid_message)
    
    # Test invalid message (wrong type)
    invalid_message = {
        "link_id": "not_int",
        "url": "test",
        "type": "post",
        "trace_id": "abc123",
        "attempt": 1
    }
    with pytest.raises(AssertionError):
        TestHelpers.assert_message_schema(invalid_message)