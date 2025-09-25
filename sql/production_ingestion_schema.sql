-- Production Ingestion Tracking Schema
-- This schema tracks ingestion progress, state, and metadata for the LinkedIn scraper system

-- Table to track ingestion runs and their status
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) UNIQUE NOT NULL,  -- UUID for this specific run
    start_date DATE NOT NULL,            -- First date being processed in this run
    end_date DATE NOT NULL,              -- Last date being processed in this run
    status VARCHAR(20) NOT NULL DEFAULT 'running', -- running, completed, failed, partial
    total_records INTEGER DEFAULT 0,     -- Total records extracted in this run
    growth_desk_records INTEGER DEFAULT 0,
    soul_product_records INTEGER DEFAULT 0,
    csv_output_path TEXT,                -- Path to the generated CSV file
    error_message TEXT,                  -- Error details if failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    CONSTRAINT valid_status CHECK (status IN ('running', 'completed', 'failed', 'partial'))
);

-- Table to track ingestion progress by sheet and date
CREATE TABLE IF NOT EXISTS ingestion_progress (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) REFERENCES ingestion_runs(run_id) ON DELETE CASCADE,
    sheet_name VARCHAR(100) NOT NULL,    -- "Job Dashboard - The Growth Desk" or "Soul in Product - Dashboard"
    sheet_id VARCHAR(100) NOT NULL,      -- Google Sheets ID
    tab_name VARCHAR(100) NOT NULL,      -- Tab name within the sheet
    ingestion_date DATE NOT NULL,        -- The date being processed (Sep 1, Sep 2, etc.)
    records_found INTEGER DEFAULT 0,     -- Number of records found for this date/sheet
    jobs_count INTEGER DEFAULT 0,        -- Number of job postings
    posts_count INTEGER DEFAULT 0,       -- Number of LinkedIn posts
    others_count INTEGER DEFAULT 0,      -- Number of other link types
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, completed, failed, skipped
    error_message TEXT,                  -- Specific error for this date/sheet if any
    processed_at TIMESTAMP,
    
    UNIQUE(run_id, sheet_name, ingestion_date),
    CONSTRAINT valid_progress_status CHECK (status IN ('pending', 'completed', 'failed', 'skipped'))
);

-- Table to track the overall ingestion state (what's been processed)
CREATE TABLE IF NOT EXISTS ingestion_state (
    id SERIAL PRIMARY KEY,
    sheet_name VARCHAR(100) NOT NULL,
    sheet_id VARCHAR(100) NOT NULL,
    last_successful_date DATE,           -- Last date that was successfully processed
    last_successful_run_id VARCHAR(50),  -- Run ID of the last successful ingestion
    total_records_ingested INTEGER DEFAULT 0, -- Running total across all successful runs
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(sheet_name, sheet_id)
);

-- Table to store configuration and settings
CREATE TABLE IF NOT EXISTS ingestion_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default configuration
INSERT INTO ingestion_config (key, value, description) VALUES
    ('sheets.growth_desk.id', '1uwqOFQpzGCoXU25YtTZ52LweI4W2MVbQ3JxAIGTka6Q', 'Google Sheets ID for Growth Desk'),
    ('sheets.growth_desk.tab', 'September (2025)', 'Tab name for Growth Desk current month'),
    ('sheets.growth_desk.name', 'Job Dashboard - The Growth Desk', 'Display name for Growth Desk'),
    ('sheets.soul_product.id', '1p7O7tUBYM94IqEmIlXp8a5B0nGdX8DwP-bmVFu0FAK0', 'Google Sheets ID for Soul in Product'),
    ('sheets.soul_product.tab', 'September Openings ', 'Tab name for Soul in Product current month'),
    ('sheets.soul_product.name', 'Soul in Product - Dashboard', 'Display name for Soul in Product'),
    ('ingestion.storage_path', './storage/production', 'Directory for storing CSV outputs'),
    ('ingestion.batch_size', '50', 'Number of records to process in each batch'),
    ('ingestion.retry_attempts', '3', 'Number of retry attempts for failed operations')
ON CONFLICT (key) DO NOTHING;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status ON ingestion_runs(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_dates ON ingestion_runs(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_ingestion_progress_date ON ingestion_progress(ingestion_date);
CREATE INDEX IF NOT EXISTS idx_ingestion_progress_sheet ON ingestion_progress(sheet_name, ingestion_date);
CREATE INDEX IF NOT EXISTS idx_ingestion_state_sheet ON ingestion_state(sheet_name);

-- View to get the current ingestion status
CREATE OR REPLACE VIEW v_ingestion_status AS
SELECT 
    s.sheet_name,
    s.last_successful_date,
    s.total_records_ingested,
    s.last_updated,
    r.run_id as last_run_id,
    r.status as last_run_status,
    r.completed_at as last_run_completed,
    COALESCE(DATE(NOW()) - s.last_successful_date, 999) as days_behind
FROM ingestion_state s
LEFT JOIN ingestion_runs r ON s.last_successful_run_id = r.run_id
ORDER BY s.sheet_name;

-- View to get detailed run statistics
CREATE OR REPLACE VIEW v_run_statistics AS
SELECT 
    r.run_id,
    r.start_date,
    r.end_date,
    r.status,
    r.total_records,
    r.growth_desk_records,
    r.soul_product_records,
    COUNT(p.id) as date_sheet_combinations,
    SUM(CASE WHEN p.status = 'completed' THEN 1 ELSE 0 END) as successful_combinations,
    SUM(CASE WHEN p.status = 'failed' THEN 1 ELSE 0 END) as failed_combinations,
    r.created_at,
    r.completed_at,
    EXTRACT(EPOCH FROM (COALESCE(r.completed_at, NOW()) - r.created_at))/60 as duration_minutes
FROM ingestion_runs r
LEFT JOIN ingestion_progress p ON r.run_id = p.run_id
GROUP BY r.id, r.run_id, r.start_date, r.end_date, r.status, r.total_records, 
         r.growth_desk_records, r.soul_product_records, r.created_at, r.completed_at
ORDER BY r.created_at DESC;