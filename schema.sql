-- LinkedIn Scraper Pipeline Database Schema

-- Table to store LinkedIn post links for scraping
CREATE TABLE IF NOT EXISTS linkedin_links (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    classification VARCHAR(50) DEFAULT 'post', -- 'post', 'profile', 'company', etc.
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'queued', 'scraping', 'scraped', 'failed'
    priority INTEGER DEFAULT 0,
    source VARCHAR(100), -- Where this link came from
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store raw scraped post data
CREATE TABLE IF NOT EXISTS linkedin_posts_raw (
    id SERIAL PRIMARY KEY,
    link_id INTEGER REFERENCES linkedin_links(id) ON DELETE CASCADE,
    trace_id VARCHAR(20),
    url TEXT NOT NULL,
    raw_html_path TEXT,
    screenshot_path TEXT,
    extracted_data JSONB,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT FALSE,
    UNIQUE(link_id) -- One raw record per link
);

-- Table to track scraping queue and retry logic
CREATE TABLE IF NOT EXISTS linkedin_posts_scraping_queue (
    id SERIAL PRIMARY KEY,
    link_id INTEGER REFERENCES linkedin_links(id) ON DELETE CASCADE,
    raw_id INTEGER REFERENCES linkedin_posts_raw(id) ON DELETE CASCADE,
    trace_id VARCHAR(20),
    status VARCHAR(50) DEFAULT 'queued', -- 'queued', 'processing', 'completed', 'retry', 'failed'
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    priority INTEGER DEFAULT 0,
    error_message TEXT,
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    next_retry_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_linkedin_links_status ON linkedin_links(status);
CREATE INDEX IF NOT EXISTS idx_linkedin_links_priority ON linkedin_links(priority DESC);
CREATE INDEX IF NOT EXISTS idx_linkedin_links_created_at ON linkedin_links(created_at);

CREATE INDEX IF NOT EXISTS idx_linkedin_posts_raw_link_id ON linkedin_posts_raw(link_id);
CREATE INDEX IF NOT EXISTS idx_linkedin_posts_raw_scraped_at ON linkedin_posts_raw(scraped_at);
CREATE INDEX IF NOT EXISTS idx_linkedin_posts_raw_success ON linkedin_posts_raw(success);

CREATE INDEX IF NOT EXISTS idx_scraping_queue_status ON linkedin_posts_scraping_queue(status);
CREATE INDEX IF NOT EXISTS idx_scraping_queue_priority ON linkedin_posts_scraping_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_scraping_queue_queued_at ON linkedin_posts_scraping_queue(queued_at);
CREATE INDEX IF NOT EXISTS idx_scraping_queue_next_retry_at ON linkedin_posts_scraping_queue(next_retry_at);

-- Update triggers to maintain updated_at timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_linkedin_links_modified
    BEFORE UPDATE ON linkedin_links
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();
