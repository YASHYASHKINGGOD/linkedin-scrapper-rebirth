"""
Live tests using real Google Sheets data.
These tests require:
1. Valid Google OAuth credentials 
2. Access to the configured Google Sheets
3. LIVE_TESTS=1 environment variable to enable
"""
import pytest
import os
import pandas as pd
from pathlib import Path


# Skip all tests unless LIVE_TESTS=1
pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE_TESTS") != "1",
    reason="Live tests disabled. Set LIVE_TESTS=1 to enable."
)


def test_live_google_sheets_ingestion():
    """Test ingestion from real Google Sheets"""
    from src.ingest.google_sheets_run import run_google_sheets_ingest
    
    # Load URLs from config
    import yaml
    sheets_config = "./config/sheets.yaml"
    
    assert os.path.exists(sheets_config), f"sheets.yaml not found at {sheets_config}"
    
    with open(sheets_config, 'r') as f:
        config = yaml.safe_load(f)
    
    urls = config.get('sheets', [])
    assert len(urls) == 3, f"Expected 3 sheets, got {len(urls)}"
    
    # Create output path
    output_csv = "./storage/test_live_ingest.csv"
    os.makedirs("./storage", exist_ok=True)
    
    try:
        # Run ingestion
        stats = run_google_sheets_ingest(
            urls=urls,
            month_filter="sep",  # September data
            output_csv=output_csv
        )
        
        # Verify results
        assert stats["total_links_raw"] > 0, "Should have found some raw links"
        assert stats["total_links_unique"] > 0, "Should have found some unique links"
        assert os.path.exists(output_csv), "Output CSV should exist"
        
        # Verify CSV structure
        df = pd.read_csv(output_csv)
        assert len(df) > 0, "CSV should have rows"
        
        required_columns = ["url", "source", "spreadsheet_id", "sheet_name", "discovered_at"]
        for col in required_columns:
            assert col in df.columns, f"Missing required column: {col}"
        
        # Verify we have LinkedIn URLs
        linkedin_urls = df[df['url'].str.contains('linkedin.com', na=False)]
        assert len(linkedin_urls) > 0, "Should have LinkedIn URLs"
        
        # Print stats for manual verification
        print(f"\nLive ingestion results:")
        print(f"Raw links: {stats['total_links_raw']}")
        print(f"Unique links: {stats['total_links_unique']}")
        print(f"Output CSV: {output_csv} ({len(df)} rows)")
        print(f"LinkedIn URLs: {len(linkedin_urls)}")
        
        # Show sample URLs
        print(f"Sample URLs:")
        for url in df['url'].head(5):
            print(f"  - {url}")
            
    finally:
        # Cleanup
        if os.path.exists(output_csv):
            os.remove(output_csv)


def test_live_orchestration_ingest_task():
    """Test the orchestration ingest task with real data"""
    from apps.orchestration.tasks import ingest_links
    import uuid
    
    trace_id = f"live_test_{uuid.uuid4().hex[:8]}"
    
    # Run ingest task
    result = ingest_links(trace_id=trace_id)
    
    # Verify result structure
    assert result["ok"] == True, f"Ingest failed: {result.get('error', 'Unknown error')}"
    assert result["trace_id"] == trace_id
    assert "output_csv" in result
    assert os.path.exists(result["output_csv"])
    
    # Verify CSV content
    df = pd.read_csv(result["output_csv"])
    assert len(df) > 0, "CSV should have data"
    
    # Verify LinkedIn URLs
    linkedin_count = len(df[df['url'].str.contains('linkedin.com', na=False)])
    assert linkedin_count > 0, "Should have LinkedIn URLs"
    
    print(f"\nOrchestration ingest results:")
    print(f"Total rows: {len(df)}")
    print(f"LinkedIn URLs: {linkedin_count}")
    print(f"Output CSV: {result['output_csv']}")
    
    # Cleanup
    try:
        os.remove(result["output_csv"])
    except:
        pass


def test_live_full_import_and_classify():
    """Test full import and classification with real data"""
    import psycopg
    from apps.orchestration.tasks import ingest_links, import_csv, classify_links
    import uuid
    
    # Skip if no database
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not configured")
    
    trace_id = f"live_full_test_{uuid.uuid4().hex[:8]}"
    
    try:
        # Step 1: Ingest
        ingest_result = ingest_links(trace_id=trace_id)
        assert ingest_result["ok"] == True
        
        # Step 2: Import to database  
        import_result = import_csv(ingest_result)
        assert import_result["ok"] == True
        
        # Step 3: Classify links
        classify_result = classify_links(import_result)
        assert classify_result["ok"] == True
        
        # Verify database state
        with psycopg.connect(database_url) as conn:
            # Check total links
            total_count = conn.execute("SELECT count(*) FROM linkedin_links").fetchone()[0]
            print(f"Total links in database: {total_count}")
            
            # Check classifications
            classifications = conn.execute("""
                SELECT classification, count(*) 
                FROM linkedin_links 
                WHERE classification IS NOT NULL
                GROUP BY classification
            """).fetchall()
            
            print(f"Classifications:")
            for classification, count in classifications:
                print(f"  {classification}: {count}")
            
            # Check queued status
            queued_count = conn.execute(
                "SELECT count(*) FROM linkedin_links WHERE status = 'queued'"
            ).fetchone()[0]
            print(f"Queued for scraping: {queued_count}")
            
            assert queued_count > 0, "Should have links queued for scraping"
        
        print(f"\nFull pipeline test completed successfully!")
        print(f"Trace ID: {trace_id}")
        
    finally:
        # Cleanup CSV files
        try:
            if 'ingest_result' in locals() and ingest_result.get("output_csv"):
                os.remove(ingest_result["output_csv"])
            if 'import_result' in locals() and import_result.get("backup_csv"):
                os.remove(import_result["backup_csv"])
        except:
            pass


def test_live_orchestration_environment():
    """Test that all required environment variables and files are present"""
    # Check Google credentials
    oauth_client = os.environ.get("GOOGLE_OAUTH_CLIENT_JSON", "./client_secret_28309019366-evvs939pulo3l9rbnopi4i1tnojf5ium.apps.googleusercontent.com.json")
    assert os.path.exists(oauth_client), f"Google OAuth client file not found: {oauth_client}"
    
    # Check sheets config
    sheets_config = os.environ.get("SHEETS_CONFIG", "./config/sheets.yaml")
    assert os.path.exists(sheets_config), f"Sheets config not found: {sheets_config}"
    
    # Check LinkedIn config
    linkedin_config = "./config.json"
    assert os.path.exists(linkedin_config), f"LinkedIn config not found: {linkedin_config}"
    
    # Verify database connectivity
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        import psycopg
        try:
            with psycopg.connect(database_url) as conn:
                conn.execute("SELECT 1")
            print("✓ Database connection successful")
        except Exception as e:
            pytest.fail(f"Database connection failed: {e}")
    
    # Verify Redis connectivity  
    celery_broker = os.environ.get("CELERY_BROKER_URL")
    if celery_broker:
        import redis
        try:
            r = redis.from_url(celery_broker)
            r.ping()
            print("✓ Redis connection successful")
        except Exception as e:
            pytest.fail(f"Redis connection failed: {e}")
    
    print("✓ All environment checks passed")