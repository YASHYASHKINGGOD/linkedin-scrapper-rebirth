#!/usr/bin/env python3
"""
Test PostgreSQL LinkedIn Scraper

This script will:
1. Connect to your PostgreSQL database
2. Fetch one pending LinkedIn link 
3. Run the scraper on that URL
4. Save the results to linkedin_posts_raw table
5. Update the link status
"""

import json
import logging
import psycopg
from datetime import datetime, timezone
from batch_linkedin_scraper_base import BatchLinkedInScraper

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseLinkedInScraper:
    def __init__(self, database_url: str, config_path: str = "config.json"):
        self.database_url = database_url
        self.config_path = config_path
        
        # Load config
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize scraper
        self.scraper = None
        
        logger.info(f"🕷️ DatabaseLinkedInScraper initialized")
        logger.info(f"   📊 Database: {database_url[:30]}...")

    def setup_scraper(self):
        """Initialize and login to LinkedIn"""
        logger.info("🔧 Setting up scraper...")
        
        self.scraper = BatchLinkedInScraper(config=self.config)
        self.scraper.setup_driver()
        
        # Login
        email = self.config.get('linkedin_credentials', {}).get('email')
        password = self.config.get('linkedin_credentials', {}).get('password')
        
        if not self.scraper.login_to_linkedin(email, password):
            raise Exception("Failed to login to LinkedIn")
        
        logger.info("✅ Scraper setup complete and logged in")

    def get_pending_link(self):
        """Get one pending link from the database"""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                # Get a LinkedIn post URL (not a job URL)
                cursor.execute("""
                    SELECT id, url
                    FROM linkedin_links 
                    WHERE status = 'queued' 
                    AND url LIKE '%linkedin.com/posts/%'
                    ORDER BY id 
                    LIMIT 1
                """)
                result = cursor.fetchone()
                
                if not result:
                    # If no posts, try any LinkedIn URL
                    cursor.execute("""
                        SELECT id, url
                        FROM linkedin_links 
                        WHERE status = 'queued' 
                        AND url LIKE '%linkedin.com%'
                        ORDER BY id 
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                
                return result

    def update_link_status(self, link_id: int, status: str):
        """Update the status of a link in the database"""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE linkedin_links 
                    SET status = %s
                    WHERE id = %s
                """, [status, link_id])
                logger.info(f"📝 Updated link {link_id} status to '{status}'")

    def save_scraped_data(self, link_id: int, url: str, scraped_data: dict):
        """Save scraped data to linkedin_posts_raw table"""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO linkedin_posts_raw (
                        link_id, url, author_name, author_title, author_location,
                        post_text, post_date, likes, comments, shares,
                        post_links, post_images, hashtags, mentions,
                        comments_count, comments_data_json,
                        extraction_timestamp, extraction_success
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, [
                    link_id,
                    url,
                    scraped_data.get('author_name'),
                    scraped_data.get('author_title'),
                    scraped_data.get('author_location'),
                    scraped_data.get('post_text'),
                    scraped_data.get('post_date'),
                    scraped_data.get('likes'),
                    scraped_data.get('comments'),
                    scraped_data.get('shares'),
                    json.dumps(scraped_data.get('post_links', [])),
                    json.dumps(scraped_data.get('post_images', [])),
                    json.dumps(scraped_data.get('hashtags', [])),
                    json.dumps(scraped_data.get('mentions', [])),
                    scraped_data.get('comments_count', 0),
                    json.dumps(scraped_data.get('comments_data', [])),
                    datetime.now(timezone.utc),
                    scraped_data.get('extraction_success', False)
                ])
                logger.info(f"💾 Saved scraped data for link {link_id}")

    def run_test_scrape(self):
        """Run a test scraping session"""
        try:
            # Get a pending link
            logger.info("🔍 Looking for a pending link...")
            link_data = self.get_pending_link()
            
            if not link_data:
                logger.warning("❌ No pending links found in database")
                return
            
            link_id, url = link_data
            logger.info(f"🎯 Found link to scrape: ID {link_id}")
            logger.info(f"   URL: {url}")
            
            # Update status to processing
            self.update_link_status(link_id, 'processing')
            
            # Setup scraper
            self.setup_scraper()
            
            # Scrape the post
            logger.info(f"🕷️ Starting scrape...")
            scraped_data = self.scraper.extract_post_data(url)
            
            logger.info(f"📊 Scraping completed:")
            logger.info(f"   Success: {scraped_data.get('extraction_success', False)}")
            if scraped_data.get('author_name'):
                logger.info(f"   Author: {scraped_data['author_name']}")
            if scraped_data.get('post_text'):
                post_preview = scraped_data['post_text'][:100] + '...' if len(scraped_data['post_text']) > 100 else scraped_data['post_text']
                logger.info(f"   Post: {post_preview}")
            
            # Save to database
            self.save_scraped_data(link_id, url, scraped_data)
            
            # Update final status
            final_status = 'completed' if scraped_data.get('extraction_success') else 'failed'
            self.update_link_status(link_id, final_status)
            
            logger.info(f"✅ Test scraping completed successfully!")
            
            return {
                'link_id': link_id,
                'url': url,
                'success': scraped_data.get('extraction_success', False),
                'author_name': scraped_data.get('author_name'),
                'post_length': len(scraped_data.get('post_text', ''))
            }
            
        except Exception as e:
            logger.error(f"❌ Test scraping failed: {e}")
            if 'link_id' in locals():
                self.update_link_status(link_id, 'failed')
            raise
        
        finally:
            if self.scraper and self.scraper.driver:
                self.scraper.driver.quit()
                logger.info("🔒 Scraper session closed")

def main():
    # PostgreSQL connection
    database_url = "postgresql://localhost:5432/data_lake"
    
    # Run test
    scraper = DatabaseLinkedInScraper(database_url)
    result = scraper.run_test_scrape()
    
    if result:
        print(f"\n🎉 Test Results:")
        print(f"   Link ID: {result['link_id']}")
        print(f"   Success: {result['success']}")
        print(f"   Author: {result['author_name']}")
        print(f"   Post Length: {result['post_length']} characters")

if __name__ == "__main__":
    main()
