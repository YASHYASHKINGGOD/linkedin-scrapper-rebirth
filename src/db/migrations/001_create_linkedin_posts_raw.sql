-- Migration: Create linkedin_posts_raw table for storing scraped LinkedIn post data
-- This table stores raw scraped content and metadata for LinkedIn posts

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

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_linkedin_posts_raw_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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
