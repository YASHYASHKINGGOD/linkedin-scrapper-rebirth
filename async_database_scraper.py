#!/usr/bin/env python3
"""
Async Database LinkedIn Scraper

An async wrapper around the Selenium LinkedIn scraper that:
1. Integrates with PostgreSQL database
2. Stores raw HTML and screenshots
3. Saves extracted data to linkedin_posts_raw table
4. Updates link status in linkedin_links table
5. Supports async operation for pipeline integration
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

try:
    import psycopg
except ImportError:
    print("❌ psycopg is required. Install with: pip install 'psycopg[binary]'")
    psycopg = None

# Import the base scraper
from batch_linkedin_scraper_base import BatchLinkedInScraper

logger = logging.getLogger(__name__)

class AsyncDatabaseLinkedInScraper:
    """
    Async wrapper for LinkedIn scraper with database integration
    """
    
    def __init__(
        self, 
        database_url: str,
        config_path: str = "config.json",
        storage_base: str = "./storage"
    ):
        self.database_url = database_url
        self.config_path = config_path
        self.storage_base = Path(storage_base)
        self.storage_base.mkdir(parents=True, exist_ok=True)
        
        # Load config
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize base scraper
        self.scraper = None
        self.initialized = False
        
        logger.info(f"🕷️ AsyncDatabaseLinkedInScraper initialized")
        logger.info(f"   📊 Database: {database_url[:30]}...")
        logger.info(f"   💾 Storage: {storage_base}")
    
    async def initialize(self):
        """Initialize the scraper and login"""
        if self.initialized:
            return
        
        loop = asyncio.get_event_loop()
        
        # Run scraper setup in thread pool since it's sync
        await loop.run_in_executor(None, self._initialize_scraper)
        self.initialized = True
        logger.info("✅ Scraper initialized and logged in")
    
    def _initialize_scraper(self):
        """Initialize the scraper (sync method)"""
        self.scraper = BatchLinkedInScraper(config=self.config)
        self.scraper.setup_driver()
        
        # Login
        email = self.config.get('linkedin_credentials', {}).get('email')
        password = self.config.get('linkedin_credentials', {}).get('password')
        
        if not self.scraper.login_to_linkedin(email, password):
            raise Exception("Failed to login to LinkedIn")
    
    async def scrape_post(self, url: str, link_id: int, trace_id: str) -> Dict[str, Any]:
        """
        Scrape a LinkedIn post and save to database
        
        Args:
            url: LinkedIn post URL
            link_id: Database link ID
            trace_id: Trace ID for logging
            
        Returns:
            Dictionary with scraping results
        """
        if not self.initialized:
            await self.initialize()
        
        logger.info(f"🕷️ [trace:{trace_id}] Starting scrape for link_id={link_id}")
        
        try:
            # Create storage directories
            post_dir = self.storage_base / f"posts/{link_id}"
            post_dir.mkdir(parents=True, exist_ok=True)
            
            # Update link status to 'scraping'
            await self._update_link_status(link_id, 'scraping')
            
            # Run scraping in thread pool (since selenium is sync)
            loop = asyncio.get_event_loop()
            scraped_data = await loop.run_in_executor(
                None, 
                self._scrape_post_sync, 
                url
            )
            
            # Save raw HTML
            raw_html_path = post_dir / f"{trace_id}_raw.html"
            with open(raw_html_path, 'w', encoding='utf-8') as f:
                f.write(scraped_data.get('raw_html', ''))
            
            # Take and save screenshot
            screenshot_path = post_dir / f"{trace_id}_screenshot.png"
            await loop.run_in_executor(
                None,
                self._take_screenshot,
                str(screenshot_path)
            )
            
            # Prepare database record
            db_record = {
                'link_id': link_id,
                'trace_id': trace_id,
                'url': url,
                'raw_html_path': str(raw_html_path),
                'screenshot_path': str(screenshot_path),
                'extracted_data': scraped_data,
                'scraped_at': datetime.now(timezone.utc),
                'success': scraped_data.get('extraction_success', False)
            }
            
            # Save to database
            await self._save_to_database(db_record)
            
            # Update link status based on success
            final_status = 'scraped' if db_record['success'] else 'failed'
            await self._update_link_status(link_id, final_status)
            
            logger.info(f"✅ [trace:{trace_id}] Scraping completed for link_id={link_id}")
            
            return {
                'trace_id': trace_id,
                'success': db_record['success'],
                'url': url,
                'link_id': link_id,
                'raw_html_path': str(raw_html_path),
                'screenshot_path': str(screenshot_path),
                'extracted_data': scraped_data,
                'error_message': scraped_data.get('error') if not db_record['success'] else None
            }
            
        except Exception as e:
            logger.error(f"❌ [trace:{trace_id}] Scraping failed for link_id={link_id}: {e}")
            
            # Update link status to failed
            await self._update_link_status(link_id, 'failed')
            
            return {
                'trace_id': trace_id,
                'success': False,
                'url': url,
                'link_id': link_id,
                'error_message': str(e),
                'raw_html_path': None,
                'screenshot_path': None,
                'extracted_data': {}
            }
    
    def _scrape_post_sync(self, url: str) -> Dict[str, Any]:
        """Run the sync scraping method"""
        try:
            # Extract post data using the base scraper
            post_data = self.scraper.extract_post_data(url)
            
            # Also get the raw HTML
            raw_html = self.scraper.driver.page_source
            post_data['raw_html'] = raw_html
            
            return post_data
            
        except Exception as e:
            return {
                'extraction_success': False,
                'error': str(e),
                'raw_html': ''
            }
    
    def _take_screenshot(self, filepath: str):
        """Take screenshot of current page"""
        try:
            self.scraper.driver.save_screenshot(filepath)
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {e}")
    
    async def _update_link_status(self, link_id: int, status: str):
        """Update status of link in database"""
        if not psycopg:
            return
        
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url) as conn:
                await conn.execute(
                    "UPDATE linkedin_links SET status = %s, updated_at = %s WHERE id = %s",
                    [status, datetime.now(timezone.utc), link_id]
                )
                logger.debug(f"Updated link {link_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update link status: {e}")
    
    async def _save_to_database(self, record: Dict[str, Any]):
        """Save scraped data to linkedin_posts_raw table"""
        if not psycopg:
            return
        
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url) as conn:
                # Insert or update record in linkedin_posts_raw
                await conn.execute("""
                    INSERT INTO linkedin_posts_raw (
                        link_id, trace_id, url, raw_html_path, screenshot_path,
                        extracted_data, scraped_at, success
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (link_id) DO UPDATE SET
                        trace_id = EXCLUDED.trace_id,
                        raw_html_path = EXCLUDED.raw_html_path,
                        screenshot_path = EXCLUDED.screenshot_path,
                        extracted_data = EXCLUDED.extracted_data,
                        scraped_at = EXCLUDED.scraped_at,
                        success = EXCLUDED.success
                """, [
                    record['link_id'],
                    record['trace_id'],
                    record['url'],
                    record['raw_html_path'],
                    record['screenshot_path'],
                    json.dumps(record['extracted_data']),
                    record['scraped_at'],
                    record['success']
                ])
                
                logger.debug(f"Saved record to database for link_id {record['link_id']}")
                
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
            raise
    
    async def close(self):
        """Close the scraper and cleanup"""
        if self.scraper and self.scraper.driver:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.scraper.driver.quit)
        logger.info("🔒 Scraper closed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# CLI for testing
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Async Database LinkedIn Scraper")
    parser.add_argument("--url", required=True, help="LinkedIn post URL to scrape")
    parser.add_argument("--link-id", type=int, help="Database link ID")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--storage", default="./storage", help="Storage base directory")
    parser.add_argument("--database-url", help="Database URL (or use DATABASE_URL env)")
    
    args = parser.parse_args()
    
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL is required")
        return
    
    trace_id = str(uuid.uuid4())[:8]
    link_id = args.link_id or 999  # Default test ID
    
    async with AsyncDatabaseLinkedInScraper(
        database_url=database_url,
        config_path=args.config,
        storage_base=args.storage
    ) as scraper:
        result = await scraper.scrape_post(args.url, link_id, trace_id)
        
        print("📊 Scraping Results:")
        print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
