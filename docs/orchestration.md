# orchestration.md - LinkedIn Selenium Scraper Batch Pipeline

## Overview

The LinkedIn Selenium scraper orchestration system provides a robust batch processing pipeline for large-scale data collection with built-in reliability, deduplication, and scheduling capabilities.

## Batch Pipeline Architecture

### Pipeline Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestration Pipeline                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │    URL      │    │ Dedup &     │    │   Batch     │        │
│  │ Validation  │───▶│ Tracking    │───▶│ Processor   │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│         │                   │                   │              │
│         ▼                   ▼                   ▼              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Input     │    │   SQLite    │    │   Retry     │        │
│  │ Sanitizer   │    │  Database   │    │  Handler    │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│         │                   │                   │              │
│         └───────────────────┼───────────────────┘              │
│                             ▼                                  │
│                    ┌─────────────┐                             │
│                    │  Scheduler  │                             │
│                    │  & Output   │                             │
│                    └─────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

## URL Validation

### Input URL Processing

```python
import re
from urllib.parse import urlparse
from typing import List, Tuple, Set

class URLValidator:
    """Validates and normalizes LinkedIn URLs"""
    
    LINKEDIN_POST_PATTERNS = [
        r'https://www\.linkedin\.com/posts/.*activity-\d+.*',
        r'https://www\.linkedin\.com/feed/update/urn:li:activity:\d+',
        r'https://linkedin\.com/posts/.*'
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern) for pattern in self.LINKEDIN_POST_PATTERNS]
    
    def validate_url(self, url: str) -> Tuple[bool, str, str]:
        """
        Validate and normalize LinkedIn URL
        
        Returns:
            (is_valid, normalized_url, error_message)
        """
        try:
            # Basic URL parsing
            parsed = urlparse(url.strip())
            
            # Check domain
            if not parsed.netloc.endswith('linkedin.com'):
                return False, "", "Not a LinkedIn URL"
            
            # Normalize protocol
            if not parsed.scheme:
                url = f"https://{url}"
                parsed = urlparse(url)
            
            # Check against patterns
            for pattern in self.compiled_patterns:
                if pattern.match(url):
                    # Extract activity ID for normalization
                    activity_id = self._extract_activity_id(url)
                    if activity_id:
                        normalized = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"
                        return True, normalized, ""
            
            return False, "", "URL pattern not recognized as LinkedIn post"
            
        except Exception as e:
            return False, "", f"URL parsing error: {str(e)}"
    
    def _extract_activity_id(self, url: str) -> str:
        """Extract LinkedIn activity ID from various URL formats"""
        patterns = [
            r'activity-(\d+)',
            r'urn:li:activity:(\d+)',
            r'/posts/.*?(\d{19})'  # 19-digit activity IDs
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return ""
    
    def batch_validate(self, urls: List[str]) -> Tuple[List[str], List[str], List[str]]:
        """
        Validate a batch of URLs
        
        Returns:
            (valid_urls, invalid_urls, error_messages)
        """
        valid_urls = []
        invalid_urls = []
        error_messages = []
        
        for url in urls:
            is_valid, normalized_url, error = self.validate_url(url)
            if is_valid:
                valid_urls.append(normalized_url)
            else:
                invalid_urls.append(url)
                error_messages.append(error)
        
        return valid_urls, invalid_urls, error_messages
```

## Deduplication Tracking with SQLite

### Database Schema

```sql
-- SQLite database schema for orchestration tracking
CREATE TABLE IF NOT EXISTS scraping_urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL UNIQUE,
    activity_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_attempt TIMESTAMP,
    attempt_count INTEGER DEFAULT 0,
    success_at TIMESTAMP,
    error_message TEXT,
    batch_id TEXT,
    priority INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scraping_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER REFERENCES scraping_urls(id),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    post_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    output_file TEXT,
    file_size INTEGER,
    processing_time_seconds REAL,
    scraper_version TEXT
);

CREATE TABLE IF NOT EXISTS batch_metadata (
    batch_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_urls INTEGER,
    completed_urls INTEGER DEFAULT 0,
    failed_urls INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',
    config_snapshot TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_normalized_url ON scraping_urls(normalized_url);
CREATE INDEX IF NOT EXISTS idx_status ON scraping_urls(status);
CREATE INDEX IF NOT EXISTS idx_batch_id ON scraping_urls(batch_id);
CREATE INDEX IF NOT EXISTS idx_activity_id ON scraping_urls(activity_id);
```

### Database Manager

```python
import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import List, Dict, Optional

class OrchestrationDB:
    """SQLite database manager for orchestration tracking"""
    
    def __init__(self, db_path: str = "orchestration.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database with required schema"""
        with self._get_connection() as conn:
            # Execute schema creation SQL here
            conn.executescript(SCHEMA_SQL)
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def add_batch(self, urls: List[str], batch_id: str, config: dict) -> int:
        """Add a new batch of URLs for processing"""
        validator = URLValidator()
        valid_urls, invalid_urls, errors = validator.batch_validate(urls)
        
        with self._get_connection() as conn:
            # Insert batch metadata
            conn.execute("""
                INSERT INTO batch_metadata (batch_id, total_urls, config_snapshot)
                VALUES (?, ?, ?)
            """, (batch_id, len(valid_urls), json.dumps(config)))
            
            # Insert URLs
            for url in valid_urls:
                activity_id = validator._extract_activity_id(url)
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO scraping_urls 
                        (original_url, normalized_url, activity_id, batch_id)
                        VALUES (?, ?, ?, ?)
                    """, (url, url, activity_id, batch_id))
                except sqlite3.IntegrityError:
                    # URL already exists, update batch_id if needed
                    conn.execute("""
                        UPDATE scraping_urls 
                        SET batch_id = ? 
                        WHERE normalized_url = ? AND status = 'pending'
                    """, (batch_id, url))
            
            conn.commit()
        
        return len(valid_urls)
    
    def get_pending_urls(self, batch_id: str = None, limit: int = 50) -> List[Dict]:
        """Get pending URLs for processing"""
        with self._get_connection() as conn:
            if batch_id:
                cursor = conn.execute("""
                    SELECT * FROM scraping_urls 
                    WHERE batch_id = ? AND status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                """, (batch_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM scraping_urls 
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_processing(self, url_id: int):
        """Mark URL as currently being processed"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE scraping_urls 
                SET status = 'processing', last_attempt = CURRENT_TIMESTAMP,
                    attempt_count = attempt_count + 1
                WHERE id = ?
            """, (url_id,))
            conn.commit()
    
    def mark_success(self, url_id: int, result_data: dict):
        """Mark URL as successfully processed"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE scraping_urls 
                SET status = 'completed', success_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (url_id,))
            
            conn.execute("""
                INSERT INTO scraping_results 
                (url_id, post_count, comment_count, output_file, file_size, processing_time_seconds, scraper_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                url_id,
                result_data.get('post_count', 0),
                result_data.get('comment_count', 0),
                result_data.get('output_file'),
                result_data.get('file_size', 0),
                result_data.get('processing_time', 0.0),
                result_data.get('scraper_version', '1.0')
            ))
            
            conn.commit()
    
    def mark_failed(self, url_id: int, error_message: str, max_attempts: int = 3):
        """Mark URL as failed, with retry logic"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT attempt_count FROM scraping_urls WHERE id = ?
            """, (url_id,))
            
            row = cursor.fetchone()
            if row and row['attempt_count'] >= max_attempts:
                # Max attempts reached, mark as permanently failed
                conn.execute("""
                    UPDATE scraping_urls 
                    SET status = 'failed', error_message = ?
                    WHERE id = ?
                """, (error_message, url_id))
            else:
                # Still retries left, mark as pending for retry
                conn.execute("""
                    UPDATE scraping_urls 
                    SET status = 'pending', error_message = ?
                    WHERE id = ?
                """, (error_message, url_id))
            
            conn.commit()
```

## Batching and Delays

### Batch Processing Strategy

```python
import time
import random
from typing import List, Iterator
from dataclasses import dataclass

@dataclass
class BatchConfig:
    """Configuration for batch processing"""
    batch_size: int = 10
    inter_batch_delay: tuple = (300, 600)  # 5-10 minutes between batches
    inter_url_delay: tuple = (2.0, 5.0)    # 2-5 seconds between URLs
    max_concurrent_sessions: int = 1
    session_cooldown: int = 3600  # 1 hour between sessions

class BatchProcessor:
    """Handles batch processing with intelligent delays"""
    
    def __init__(self, config: BatchConfig):
        self.config = config
        self.db = OrchestrationDB()
        self.last_batch_time = 0
        self.session_start_time = time.time()
    
    def process_batch(self, batch_id: str) -> dict:
        """Process a single batch of URLs"""
        stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': time.time()
        }
        
        while True:
            # Get next batch of URLs
            pending_urls = self.db.get_pending_urls(
                batch_id=batch_id, 
                limit=self.config.batch_size
            )
            
            if not pending_urls:
                break
            
            # Process URLs in current batch
            for url_data in pending_urls:
                try:
                    result = self._process_single_url(url_data)
                    stats['total_processed'] += 1
                    
                    if result['success']:
                        stats['successful'] += 1
                        self.db.mark_success(url_data['id'], result)
                    else:
                        stats['failed'] += 1
                        self.db.mark_failed(url_data['id'], result['error'])
                    
                    # Inter-URL delay
                    self._apply_url_delay()
                    
                except Exception as e:
                    stats['failed'] += 1
                    self.db.mark_failed(url_data['id'], str(e))
            
            # Inter-batch delay
            self._apply_batch_delay()
        
        stats['duration'] = time.time() - stats['start_time']
        return stats
    
    def _process_single_url(self, url_data: dict) -> dict:
        """Process a single URL using the scraper"""
        self.db.mark_processing(url_data['id'])
        
        try:
            with LinkedInSeleniumScraper() as scraper:
                # Initialize and login
                if not scraper.initialize_driver():
                    return {'success': False, 'error': 'Failed to initialize driver'}
                
                success, message = scraper.login()
                if not success:
                    return {'success': False, 'error': f'Login failed: {message}'}
                
                # Navigate to post URL
                scraper.driver.get(url_data['normalized_url'])
                scraper._random_delay()
                
                # Scrape post data (placeholder - implement actual scraping)
                post_data = {'placeholder': 'data'}
                
                # Save results (placeholder - implement actual saving)
                output_file = f"outputs/post_{url_data['activity_id']}_{int(time.time())}.json"
                
                return {
                    'success': True,
                    'post_count': 1,
                    'comment_count': 0,
                    'output_file': output_file,
                    'file_size': 1024,
                    'processing_time': 5.0,
                    'scraper_version': '1.0'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _apply_url_delay(self):
        """Apply delay between URL processing"""
        delay = random.uniform(*self.config.inter_url_delay)
        time.sleep(delay)
    
    def _apply_batch_delay(self):
        """Apply delay between batch processing"""
        current_time = time.time()
        
        # Check if we need session cooldown
        session_duration = current_time - self.session_start_time
        if session_duration > 7200:  # 2 hours
            cooldown_delay = random.uniform(1800, 3600)  # 30-60 minutes
            time.sleep(cooldown_delay)
            self.session_start_time = time.time()
        
        # Standard inter-batch delay
        delay = random.uniform(*self.config.inter_batch_delay)
        time.sleep(delay)
        self.last_batch_time = current_time
```

## Retries and Error Handling

### Retry Policy Configuration

```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List

class RetryReason(Enum):
    NETWORK_ERROR = "network_error"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "auth_failed"
    PAGE_LOAD_TIMEOUT = "page_timeout"
    ELEMENT_NOT_FOUND = "element_missing"
    GENERIC_ERROR = "generic_error"

@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: Dict[RetryReason, int] = None
    backoff_multiplier: float = 2.0
    base_delay: int = 60  # seconds
    max_delay: int = 3600  # 1 hour max
    
    def __post_init__(self):
        if self.max_attempts is None:
            self.max_attempts = {
                RetryReason.NETWORK_ERROR: 5,
                RetryReason.RATE_LIMITED: 3,
                RetryReason.AUTHENTICATION_FAILED: 2,
                RetryReason.PAGE_LOAD_TIMEOUT: 3,
                RetryReason.ELEMENT_NOT_FOUND: 2,
                RetryReason.GENERIC_ERROR: 3
            }

class RetryManager:
    """Manages retry logic with exponential backoff"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    def should_retry(self, url_id: int, error_type: RetryReason) -> bool:
        """Determine if URL should be retried"""
        with OrchestrationDB()._get_connection() as conn:
            cursor = conn.execute("""
                SELECT attempt_count FROM scraping_urls WHERE id = ?
            """, (url_id,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            current_attempts = row['attempt_count']
            max_attempts = self.config.max_attempts.get(error_type, 3)
            
            return current_attempts < max_attempts
    
    def get_retry_delay(self, attempt_count: int) -> int:
        """Calculate exponential backoff delay"""
        delay = self.config.base_delay * (self.config.backoff_multiplier ** attempt_count)
        return min(delay, self.config.max_delay)
    
    def schedule_retry(self, url_id: int, error_type: RetryReason, error_message: str):
        """Schedule URL for retry with appropriate delay"""
        if not self.should_retry(url_id, error_type):
            return False
        
        # Calculate delay and schedule retry
        with OrchestrationDB()._get_connection() as conn:
            cursor = conn.execute("""
                SELECT attempt_count FROM scraping_urls WHERE id = ?
            """, (url_id,))
            
            row = cursor.fetchone()
            delay = self.get_retry_delay(row['attempt_count'])
            
            # Schedule for retry after delay
            retry_time = datetime.now() + timedelta(seconds=delay)
            conn.execute("""
                UPDATE scraping_urls 
                SET status = 'retry_scheduled', 
                    error_message = ?,
                    next_retry_at = ?
                WHERE id = ?
            """, (error_message, retry_time, url_id))
            
            conn.commit()
        
        return True
```

## Scheduling Cadence

### Cron-Style Scheduling

```python
import schedule
import threading
from datetime import datetime, timedelta

class OrchestrationScheduler:
    """Handles scheduled batch processing"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.db = OrchestrationDB()
        self.is_running = False
        self.current_batch_id = None
    
    def setup_schedules(self):
        """Set up scheduled jobs"""
        # Daily batch processing
        schedule.every().day.at("02:00").do(self._run_daily_batch)
        
        # Retry processing every 2 hours
        schedule.every(2).hours.do(self._process_retries)
        
        # Maintenance tasks
        schedule.every().week.do(self._weekly_maintenance)
        schedule.every().day.at("01:00").do(self._daily_cleanup)
    
    def _run_daily_batch(self):
        """Execute daily batch processing"""
        if self.is_running:
            return  # Skip if already running
        
        self.is_running = True
        batch_id = f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Load URLs from configured sources
            urls = self._load_urls_from_sources()
            
            if urls:
                self.db.add_batch(urls, batch_id, self.config)
                
                # Process batch
                processor = BatchProcessor(BatchConfig())
                stats = processor.process_batch(batch_id)
                
                # Log results
                self._log_batch_results(batch_id, stats)
            
        finally:
            self.is_running = False
    
    def _process_retries(self):
        """Process URLs scheduled for retry"""
        with self.db._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM scraping_urls 
                WHERE status = 'retry_scheduled' 
                AND next_retry_at <= CURRENT_TIMESTAMP
                LIMIT 50
            """)
            
            retry_urls = [dict(row) for row in cursor.fetchall()]
        
        if retry_urls:
            # Create retry batch
            batch_id = f"retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Update URLs to pending status
            url_ids = [url['id'] for url in retry_urls]
            with self.db._get_connection() as conn:
                placeholders = ','.join('?' * len(url_ids))
                conn.execute(f"""
                    UPDATE scraping_urls 
                    SET status = 'pending', batch_id = ?
                    WHERE id IN ({placeholders})
                """, [batch_id] + url_ids)
                conn.commit()
            
            # Process retry batch
            processor = BatchProcessor(BatchConfig(batch_size=5))  # Smaller batches for retries
            processor.process_batch(batch_id)
    
    def start_scheduler(self):
        """Start the background scheduler"""
        self.setup_schedules()
        
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
    
    def _load_urls_from_sources(self) -> List[str]:
        """Load URLs from configured sources (files, APIs, etc.)"""
        urls = []
        
        # Example: Load from file
        url_file = self.config.get('input_settings', {}).get('url_file')
        if url_file and os.path.exists(url_file):
            with open(url_file, 'r') as f:
                urls.extend([line.strip() for line in f if line.strip()])
        
        # Example: Load from API endpoint
        api_endpoint = self.config.get('input_settings', {}).get('api_endpoint')
        if api_endpoint:
            # Implement API loading logic
            pass
        
        return urls
```

## Output Management

### Intermediate and Summary Outputs

```python
class OutputManager:
    """Manages batch processing outputs and summaries"""
    
    def __init__(self, output_dir: str = "batch_outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def generate_batch_summary(self, batch_id: str) -> dict:
        """Generate comprehensive batch summary"""
        db = OrchestrationDB()
        
        with db._get_connection() as conn:
            # Batch statistics
            batch_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_urls,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    AVG(attempt_count) as avg_attempts,
                    MIN(created_at) as start_time,
                    MAX(COALESCE(success_at, last_attempt)) as end_time
                FROM scraping_urls 
                WHERE batch_id = ?
            """, (batch_id,)).fetchone()
            
            # Results summary
            results_stats = conn.execute("""
                SELECT 
                    SUM(post_count) as total_posts,
                    SUM(comment_count) as total_comments,
                    SUM(file_size) as total_file_size,
                    AVG(processing_time_seconds) as avg_processing_time,
                    COUNT(DISTINCT output_file) as output_files_created
                FROM scraping_results sr
                JOIN scraping_urls su ON sr.url_id = su.id
                WHERE su.batch_id = ?
            """, (batch_id,)).fetchone()
            
            # Error breakdown
            error_stats = conn.execute("""
                SELECT error_message, COUNT(*) as count
                FROM scraping_urls 
                WHERE batch_id = ? AND status = 'failed'
                GROUP BY error_message
                ORDER BY count DESC
            """, (batch_id,)).fetchall()
        
        summary = {
            'batch_id': batch_id,
            'batch_stats': dict(batch_stats) if batch_stats else {},
            'results_stats': dict(results_stats) if results_stats else {},
            'error_breakdown': [dict(row) for row in error_stats],
            'generated_at': datetime.now().isoformat()
        }
        
        return summary
    
    def save_batch_summary(self, batch_id: str):
        """Save batch summary to file"""
        summary = self.generate_batch_summary(batch_id)
        
        summary_file = self.output_dir / f"batch_summary_{batch_id}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        return summary_file
    
    def export_batch_data(self, batch_id: str, format: str = 'csv'):
        """Export batch data in specified format"""
        db = OrchestrationDB()
        
        with db._get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    su.original_url,
                    su.normalized_url,
                    su.status,
                    su.attempt_count,
                    su.success_at,
                    su.error_message,
                    sr.post_count,
                    sr.comment_count,
                    sr.output_file,
                    sr.processing_time_seconds
                FROM scraping_urls su
                LEFT JOIN scraping_results sr ON su.id = sr.url_id
                WHERE su.batch_id = ?
                ORDER BY su.created_at
            """, (batch_id,))
            
            rows = cursor.fetchall()
        
        if format == 'csv':
            import pandas as pd
            df = pd.DataFrame([dict(row) for row in rows])
            
            output_file = self.output_dir / f"batch_data_{batch_id}.csv"
            df.to_csv(output_file, index=False)
            
            return output_file
        
        elif format == 'json':
            data = [dict(row) for row in rows]
            
            output_file = self.output_dir / f"batch_data_{batch_id}.json"
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            return output_file
```

## Example Usage and Tuning Tips

### Basic Batch Processing Setup

```python
# Example: Process a batch of LinkedIn post URLs

def main():
    # Initialize orchestration system
    batch_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # URLs to process
    urls = [
        "https://www.linkedin.com/posts/example_activity-123456789",
        "https://www.linkedin.com/posts/example_activity-987654321",
        # ... more URLs
    ]
    
    # Add batch to database
    db = OrchestrationDB()
    config = json.load(open('config.json'))
    added_count = db.add_batch(urls, batch_id, config)
    print(f"Added {added_count} valid URLs to batch {batch_id}")
    
    # Process batch
    batch_config = BatchConfig(
        batch_size=5,           # Process 5 URLs at a time
        inter_batch_delay=(600, 900),  # 10-15 minutes between batches
        inter_url_delay=(3.0, 6.0)    # 3-6 seconds between URLs
    )
    
    processor = BatchProcessor(batch_config)
    stats = processor.process_batch(batch_id)
    
    print(f"Batch processing completed:")
    print(f"  Total processed: {stats['total_processed']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Duration: {stats['duration']:.2f} seconds")
    
    # Generate summary
    output_manager = OutputManager()
    summary_file = output_manager.save_batch_summary(batch_id)
    data_file = output_manager.export_batch_data(batch_id, 'csv')
    
    print(f"Summary saved to: {summary_file}")
    print(f"Data exported to: {data_file}")

if __name__ == "__main__":
    main()
```

### Tuning Recommendations

#### Performance Tuning
- **Small Batches**: Start with batch sizes of 5-10 URLs
- **Conservative Delays**: Use longer delays initially (2-5 minutes between batches)
- **Monitor Rate Limits**: Watch for 429 responses and increase delays accordingly
- **Resource Usage**: Monitor memory and CPU usage during processing

#### Reliability Tuning
- **Retry Logic**: Configure retry attempts based on error types
- **Database Backup**: Regular backups of orchestration.db
- **Checkpoint Recovery**: Resume processing from where you left off
- **Error Categorization**: Classify errors to improve retry strategies

#### Scale Tuning
- **Account Rotation**: Use multiple LinkedIn accounts for larger scale
- **Proxy Integration**: Rotate IP addresses for high-volume processing
- **Distributed Processing**: Split batches across multiple machines
- **Storage Optimization**: Compress outputs and archive old data

This orchestration system provides a robust foundation for large-scale LinkedIn scraping with proper error handling, deduplication, and monitoring capabilities.
