#!/usr/bin/env python3
"""
Quick smoke test to verify the real data setup works.
Run this to test Google Sheets access and basic functionality.
"""
import os
import sys


def test_environment():
    """Check that all required files and environment variables are present"""
    print("🔍 Checking environment...")
    
    # Check credential files
    oauth_client = "./client_secret_28309019366-evvs939pulo3l9rbnopi4i1tnojf5ium.apps.googleusercontent.com.json"
    if not os.path.exists(oauth_client):
        print(f"❌ Google OAuth client file not found: {oauth_client}")
        return False
    print(f"✅ Google OAuth client file found")
    
    # Check config files
    if not os.path.exists("./config/sheets.yaml"):
        print("❌ sheets.yaml config not found")
        return False
    print("✅ sheets.yaml config found")
    
    if not os.path.exists("./config.json"):
        print("❌ LinkedIn config.json not found")
        return False
    print("✅ LinkedIn config.json found")
    
    # Check .env file
    if not os.path.exists("./.env"):
        print("❌ .env file not found - copy from .env.example")
        return False
    print("✅ .env file found")
    
    return True


def test_google_sheets_access():
    """Test basic Google Sheets access"""
    print("\n📊 Testing Google Sheets access...")
    
    try:
        import yaml
        with open("./config/sheets.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        urls = config.get('sheets', [])
        print(f"✅ Found {len(urls)} Google Sheets URLs in config")
        
        # Test basic ingestion
        from src.ingest.google_sheets_run import run_google_sheets_ingest
        
        print("🔄 Testing ingestion from first sheet (limited)...")
        test_urls = urls[:1]  # Just test first sheet
        
        stats = run_google_sheets_ingest(
            urls=test_urls,
            month_filter="sep",
            output_csv=None  # No file output for smoke test
        )
        
        print(f"✅ Ingestion successful!")
        print(f"   Raw links: {stats['total_links_raw']}")
        print(f"   Unique links: {stats['total_links_unique']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Google Sheets access failed: {e}")
        return False


def test_database_connection():
    """Test database connectivity"""
    print("\n🗄️  Testing database connection...")
    
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("⚠️  DATABASE_URL not set - skipping database test")
        return True
    
    try:
        import psycopg
        with psycopg.connect(database_url) as conn:
            conn.execute("SELECT 1")
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def test_redis_connection():
    """Test Redis connectivity"""
    print("\n📦 Testing Redis connection...")
    
    celery_broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    
    try:
        import redis
        r = redis.from_url(celery_broker)
        r.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False


def main():
    """Run all smoke tests"""
    print("🚀 LinkedIn Pipeline Smoke Test")
    print("=" * 50)
    
    # Load environment from .env file
    if os.path.exists(".env"):
        from dotenv import load_dotenv
        load_dotenv()
    
    success = True
    
    success &= test_environment()
    success &= test_google_sheets_access()
    success &= test_database_connection()
    success &= test_redis_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All smoke tests passed!")
        print("\nNext steps:")
        print("  1. Run live tests: make test.live")
        print("  2. Start pipeline: make orchestration.worker")
        print("  3. Run full test: make test.e2e")
        return 0
    else:
        print("💥 Some tests failed - check configuration")
        return 1


if __name__ == "__main__":
    sys.exit(main())