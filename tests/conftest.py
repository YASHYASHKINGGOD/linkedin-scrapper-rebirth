"""
Test configuration and shared fixtures for LinkedIn Pipeline tests.
"""
import pytest
import os
import tempfile
import pandas as pd
from typing import Dict, Any, List
import psycopg


@pytest.fixture
def test_env_vars():
    """Set up test environment variables."""
    test_vars = {
        'DATABASE_URL': 'postgresql://user:pass@localhost:5432/data_lake_test',
        'CELERY_BROKER_URL': 'redis://localhost:6379/2',
        'CELERY_RESULT_BACKEND': 'redis://localhost:6379/3',
        'MONTH_FILTER': 'aug',
        'STORAGE_BASE': './test_storage'
    }
    
    # Save original values
    original_values = {}
    for key, value in test_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield test_vars
    
    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def test_database_url(test_env_vars):
    """Get test database URL."""
    return test_env_vars['DATABASE_URL']


@pytest.fixture
def create_test_csv():
    """Factory fixture to create test CSV files."""
    def _create_csv(data: List[Dict[str, Any]]) -> str:
        """Create a temporary CSV file with test data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df = pd.DataFrame(data)
            df.to_csv(f.name, index=False)
            return f.name
    
    return _create_csv


@pytest.fixture
def sample_linkedin_links():
    """Sample LinkedIn URLs for testing."""
    return [
        {
            'date': '2024-08-15',
            'company': 'TestCorp Inc',
            'role': 'Software Engineer',
            'location': 'San Francisco, CA',
            'url': 'https://www.linkedin.com/jobs/view/3987654321'
        },
        {
            'date': '2024-08-16', 
            'company': 'PostCorp Ltd',
            'role': 'Product Manager',
            'location': 'New York, NY',
            'url': 'https://www.linkedin.com/posts/john-doe_excited-to-share-our-latest-product-update'
        },
        {
            'date': '2024-08-17',
            'company': 'DataCorp',
            'role': 'Data Scientist', 
            'location': 'Remote',
            'url': 'https://www.linkedin.com/jobs/view/3987654322'
        }
    ]


@pytest.fixture
def mock_scrape_job_result():
    """Mock result from job scraping."""
    return {
        'html_path': './test_storage/jobs/123/job.html',
        'screenshot_path': './test_storage/jobs/123/screenshot.png',
        'role_title': 'Senior Software Engineer',
        'company_name': 'Mock Company Inc',
        'location': 'San Francisco, CA',
        'posted_time': '2 days ago',
        'status': 'Open',
        'description_text': 'We are looking for a talented engineer...'
    }


@pytest.fixture 
def mock_scrape_post_result():
    """Mock result from post scraping."""
    return {
        'success': True,
        'raw_html_path': './test_storage/posts/456/post.html',
        'screenshot_path': './test_storage/posts/456/screenshot.png',
        'extracted_data': {
            'author': 'John Doe',
            'content': 'Excited to share our latest product update!',
            'likes': 42,
            'comments': 5
        }
    }


def clean_test_database(database_url: str):
    """Clean test database tables."""
    try:
        with psycopg.connect(database_url) as conn:
            # Clean in dependency order
            conn.execute("DELETE FROM linkedin_posts_raw WHERE 1=1")
            conn.execute("DELETE FROM linkedin_jobs_raw WHERE 1=1") 
            conn.execute("DELETE FROM linkedin_links WHERE url LIKE '%test%'")
            conn.commit()
    except Exception:
        # If tables don't exist or connection fails, that's fine for tests
        pass


def get_link_count(database_url: str) -> int:
    """Get count of links in test database."""
    try:
        with psycopg.connect(database_url) as conn:
            result = conn.execute("SELECT count(*) FROM linkedin_links").fetchone()
            return result[0] if result else 0
    except Exception:
        return 0


def get_scraped_links(database_url: str) -> List[Dict[str, Any]]:
    """Get scraped links from test database."""
    try:
        with psycopg.connect(database_url) as conn:
            cursor = conn.execute("""
                SELECT id, url, classification, status 
                FROM linkedin_links 
                WHERE status IN ('scraped', 'error')
            """)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception:
        return []


# Shared test utilities
class TestHelpers:
    """Shared test utility functions."""
    
    @staticmethod
    def create_test_message(link_id: int, url: str, type_: str, trace_id: str = "test123") -> Dict[str, Any]:
        """Create a standardized test message."""
        return {
            "link_id": link_id,
            "url": url,
            "type": type_,
            "trace_id": trace_id,
            "attempt": 1
        }
    
    @staticmethod
    def assert_message_schema(message: Dict[str, Any]):
        """Assert message follows the standardized schema."""
        required_fields = ["link_id", "url", "type", "trace_id", "attempt"]
        for field in required_fields:
            assert field in message, f"Missing required field: {field}"
        
        assert isinstance(message["link_id"], int)
        assert isinstance(message["url"], str)
        assert message["type"] in ["job", "post"]
        assert isinstance(message["trace_id"], str)
        assert isinstance(message["attempt"], int)