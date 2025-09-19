#!/usr/bin/env python3
"""
PostgreSQL Migration: Create linkedin_posts_raw table

This script creates the linkedin_posts_raw table and related indexes/functions
directly in your PostgreSQL database.

Usage:
    python src/db/migrations/create_posts_table.py
    
Or via the main CLI:
    python linkedin_pipeline.py migrate-database

Environment Variables Required:
    DATABASE_URL - PostgreSQL connection string
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import psycopg
except ImportError:
    print("❌ psycopg is required. Install with: pip install 'psycopg[binary]'")
    sys.exit(1)


def create_linkedin_posts_raw_table(database_url: str) -> None:
    """Create the linkedin_posts_raw table with all indexes and triggers"""
    
    print("🔄 Creating linkedin_posts_raw table in PostgreSQL...")
    
    # PostgreSQL DDL for linkedin_posts_raw table
    migration_sql = """
    -- Migration: Create linkedin_posts_raw table for storing scraped LinkedIn post data
    -- This table stores raw scraped content and metadata for LinkedIn posts
    
    BEGIN;
    
    -- Create the linkedin_posts_raw table
    CREATE TABLE IF NOT EXISTS public.linkedin_posts_raw (
        -- Primary key and references
        id BIGSERIAL PRIMARY KEY,
        link_id BIGINT NOT NULL REFERENCES public.linkedin_links(id) ON DELETE CASCADE,
        
        -- Core data
        url TEXT NOT NULL,
        canonical_url TEXT GENERATED ALWAYS AS (lower(url)) STORED,
        
        -- Scraped content storage paths (relative to storage root)
        raw_html_path TEXT,           -- Path to saved HTML file
        screenshot_path TEXT,         -- Path to screenshot image
        metadata_json_path TEXT,      -- Path to extracted metadata JSON
        
        -- Status and timing
        status TEXT CHECK (status IN ('pending', 'scraping', 'completed', 'failed', 'retry')) DEFAULT 'pending',
        scraped_at TIMESTAMPTZ,       -- When scraping was completed
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        
        -- Scraping metadata
        scrape_metadata JSONB DEFAULT '{}',  -- Browser info, timing, etc.
        extracted_data JSONB DEFAULT '{}',   -- Parsed post content, author, etc.
        
        -- Error handling
        error_message TEXT,
        attempt_count INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 3,
        next_retry_at TIMESTAMPTZ,
        
        -- Audit fields
        trace_id TEXT,               -- For distributed tracing
        scraper_version TEXT,        -- Version of scraper used
        
        -- Constraints
        UNIQUE(link_id),            -- One raw record per link
        CHECK (attempt_count >= 0),
        CHECK (max_attempts > 0)
    );
    
    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS ix_linkedin_posts_raw_link_id ON public.linkedin_posts_raw(link_id);
    CREATE INDEX IF NOT EXISTS ix_linkedin_posts_raw_status ON public.linkedin_posts_raw(status);
    CREATE INDEX IF NOT EXISTS ix_linkedin_posts_raw_scraped_at ON public.linkedin_posts_raw(scraped_at DESC);
    CREATE INDEX IF NOT EXISTS ix_linkedin_posts_raw_next_retry ON public.linkedin_posts_raw(next_retry_at) WHERE next_retry_at IS NOT NULL;
    CREATE INDEX IF NOT EXISTS ix_linkedin_posts_raw_trace_id ON public.linkedin_posts_raw(trace_id) WHERE trace_id IS NOT NULL;
    
    -- Index on extracted content for search
    CREATE INDEX IF NOT EXISTS ix_linkedin_posts_raw_extracted_data ON public.linkedin_posts_raw USING gin(extracted_data);
    
    -- Updated at trigger function
    CREATE OR REPLACE FUNCTION update_linkedin_posts_raw_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = now();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Create trigger
    DROP TRIGGER IF EXISTS trigger_linkedin_posts_raw_updated_at ON public.linkedin_posts_raw;
    CREATE TRIGGER trigger_linkedin_posts_raw_updated_at
        BEFORE UPDATE ON public.linkedin_posts_raw
        FOR EACH ROW
        EXECUTE FUNCTION update_linkedin_posts_raw_updated_at();
    
    -- Comments for documentation
    COMMENT ON TABLE public.linkedin_posts_raw IS 'Raw scraped data for LinkedIn posts including HTML, screenshots, and metadata';
    COMMENT ON COLUMN public.linkedin_posts_raw.link_id IS 'Foreign key to linkedin_links table';
    COMMENT ON COLUMN public.linkedin_posts_raw.raw_html_path IS 'Relative path to stored HTML file under storage/posts/';
    COMMENT ON COLUMN public.linkedin_posts_raw.screenshot_path IS 'Relative path to screenshot image under storage/posts/';
    COMMENT ON COLUMN public.linkedin_posts_raw.scrape_metadata IS 'Technical metadata about the scraping process';
    COMMENT ON COLUMN public.linkedin_posts_raw.extracted_data IS 'Parsed content from the LinkedIn post';
    
    COMMIT;
    """
    
    try:
        with psycopg.connect(database_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            
            # Execute the migration
            conn.execute(migration_sql)
            
            # Verify table creation
            result = conn.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'linkedin_posts_raw'
            """).fetchone()
            
            if result[0] == 1:
                print("✅ linkedin_posts_raw table created successfully")
                
                # Check indexes
                indexes = conn.execute("""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = 'linkedin_posts_raw' AND schemaname = 'public'
                    ORDER BY indexname
                """).fetchall()
                
                print(f"📊 Created {len(indexes)} indexes:")
                for idx in indexes:
                    print(f"   - {idx[0]}")
                
                # Check trigger
                triggers = conn.execute("""
                    SELECT trigger_name FROM information_schema.triggers 
                    WHERE event_object_table = 'linkedin_posts_raw'
                """).fetchall()
                
                if triggers:
                    print(f"🔄 Created {len(triggers)} triggers:")
                    for trigger in triggers:
                        print(f"   - {trigger[0]}")
                
            else:
                print("❌ Failed to create linkedin_posts_raw table")
                sys.exit(1)
                
    except psycopg.Error as e:
        print(f"❌ PostgreSQL error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


def verify_linkedin_links_table(database_url: str) -> bool:
    """Verify that the linkedin_links table exists (required for foreign key)"""
    
    try:
        with psycopg.connect(database_url) as conn:
            result = conn.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'linkedin_links'
            """).fetchone()
            
            return result[0] == 1
    except Exception:
        return False


def main():
    """Main migration execution"""
    
    # Get database URL
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable is required")
        print("   Example: export DATABASE_URL='postgresql://user:password@localhost:5432/database'")
        sys.exit(1)
    
    # Validate database URL
    if not database_url.startswith(('postgresql://', 'postgres://')):
        print("❌ DATABASE_URL must be a PostgreSQL connection string")
        sys.exit(1)
    
    print(f"🔗 Connecting to PostgreSQL database: {database_url[:30]}...")
    
    # Test database connection
    try:
        with psycopg.connect(database_url) as conn:
            version = conn.execute("SELECT version()").fetchone()[0]
            print(f"📊 Connected to: {version.split(',')[0]}")
    except Exception as e:
        print(f"❌ Cannot connect to database: {e}")
        sys.exit(1)
    
    # Check if linkedin_links table exists
    if not verify_linkedin_links_table(database_url):
        print("⚠️  linkedin_links table not found!")
        print("   The linkedin_posts_raw table requires linkedin_links to exist first.")
        print("   Please ensure you have run the linkedin_links migration:")
        print("   python linkedin_pipeline.py classify-links")
        
        create_anyway = input("\n   Continue anyway? (y/N): ").lower().strip()
        if create_anyway != 'y':
            print("   Migration cancelled.")
            sys.exit(1)
    else:
        print("✅ linkedin_links table found")
    
    # Run migration
    create_linkedin_posts_raw_table(database_url)
    
    print("\n🎉 Migration completed successfully!")
    print("\nNext steps:")
    print("1. Test the router: python linkedin_pipeline.py scraping-stats")
    print("2. Process posts: python linkedin_pipeline.py scrape-posts")
    print("3. Run worker: python linkedin_pipeline.py run-posts-worker")


if __name__ == "__main__":
    main()
