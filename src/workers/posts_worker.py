#!/usr/bin/env python3
"""
LinkedIn Posts Scraper Worker

Worker process that:
1. Consumes queued post links from the posts router
2. Runs the LinkedIn post scraper for each link
3. Saves raw HTML and screenshots to storage 
4. Persists metadata and results to linkedin_posts_raw table
5. Handles errors, retries, and dead letter queue

Usage:
    python -m src.workers.posts_worker run-worker
    python -m src.workers.posts_worker scrape-single --url "https://linkedin.com/posts/..."
"""

import os
import sys
import json
import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.routers.posts_router import LinkedInPostsRouter, ScrapingResult
from apps.scraper_playwright.posts.scraper import LinkedInPostScraper, ScrapedPost


class LinkedInPostsWorker:
    """Worker that processes LinkedIn post scraping queue"""
    
    def __init__(
        self, 
        database_url: str, 
        storage_base: str = "./storage",
        headless: bool = True,
        concurrent_scrapers: int = 2
    ):
        self.database_url = database_url
        self.storage_base = storage_base
        self.headless = headless
        self.concurrent_scrapers = concurrent_scrapers
        
        # Initialize router and scraper
        self.router = LinkedInPostsRouter(database_url, storage_base)
        self.scraper = LinkedInPostScraper(storage_base, headless)
        
        # Worker configuration
        self.batch_size = 5
        self.worker_sleep_seconds = 10
        self.max_consecutive_errors = 5
        
        print(f"🤖 LinkedIn Posts Worker initialized")
        print(f"   📊 Database: {database_url[:30]}...")
        print(f"   💾 Storage: {storage_base}")
        print(f"   🕷️  Concurrent scrapers: {concurrent_scrapers}")
        print(f"   👁️  Headless mode: {headless}")
    
    def _convert_scraped_to_scraping_result(self, scraped: ScrapedPost) -> ScrapingResult:
        """Convert ScrapedPost to ScrapingResult for database persistence"""
        scrape_metadata = {
            "scrape_timestamp": scraped.scrape_timestamp,
            "html_length": scraped.html_length,
            "screenshot_taken": scraped.screenshot_taken,
            "canonical_url": scraped.canonical_url,
            "error_type": scraped.error_type
        }
        
        extracted_data = {}
        if scraped.author_name:
            extracted_data["author_name"] = scraped.author_name
        if scraped.author_profile_url:
            extracted_data["author_profile_url"] = scraped.author_profile_url
        if scraped.post_text:
            extracted_data["post_text"] = scraped.post_text
        if scraped.post_date:
            extracted_data["post_date"] = scraped.post_date
        if scraped.like_count is not None:
            extracted_data["like_count"] = scraped.like_count
        if scraped.comment_count is not None:
            extracted_data["comment_count"] = scraped.comment_count
        if scraped.repost_count is not None:
            extracted_data["repost_count"] = scraped.repost_count
        
        return ScrapingResult(
            success=scraped.success,
            raw_html_path=scraped.raw_html_path,
            screenshot_path=scraped.screenshot_path,
            metadata_json_path=scraped.metadata_json_path,
            scrape_metadata=scrape_metadata,
            extracted_data=extracted_data,
            error_message=scraped.error_message
        )
    
    async def scrape_single_post(
        self, 
        url: str, 
        link_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scrape a single LinkedIn post (for testing/manual use)
        
        Args:
            url: LinkedIn post URL
            link_id: Optional database link ID
            
        Returns:
            Scraping results
        """
        trace_id = str(uuid.uuid4())[:8]
        print(f"🕷️  [trace:{trace_id}] Scraping single post: {url}")
        
        try:
            # Run scraper
            scraped = await self.scraper.scrape_post(url, link_id, trace_id)
            
            # Convert to result format
            result = self._convert_scraped_to_scraping_result(scraped)
            
            print(f"   {'✅' if result.success else '❌'} [trace:{trace_id}] Scraping {'completed' if result.success else 'failed'}")
            
            return {
                "trace_id": trace_id,
                "success": result.success,
                "url": url,
                "link_id": link_id,
                "error_message": result.error_message,
                "raw_html_path": result.raw_html_path,
                "screenshot_path": result.screenshot_path,
                "extracted_data": result.extracted_data
            }
            
        except Exception as e:
            print(f"   ❌ [trace:{trace_id}] Worker error: {e}")
            return {
                "trace_id": trace_id,
                "success": False,
                "url": url,
                "link_id": link_id,
                "error_message": f"Worker error: {e}",
                "raw_html_path": None,
                "screenshot_path": None,
                "extracted_data": {}
            }
    
    async def process_batch(self, batch_size: int = None) -> Dict[str, Any]:
        """
        Process a batch of queued post links
        
        Args:
            batch_size: Number of links to process in this batch
            
        Returns:
            Processing results and statistics
        """
        batch_size = batch_size or self.batch_size
        batch_start = datetime.now(timezone.utc)
        trace_id = str(uuid.uuid4())[:8]
        
        print(f"\\n🔄 [trace:{trace_id}] Processing batch (size={batch_size})")
        
        try:
            # Get queued links from router
            router_result = await self.router.process_post_queue(batch_size)
            
            if router_result["status"] == "no_work":
                print("   ✅ No work available")
                return {
                    "trace_id": trace_id,
                    "batch_size": batch_size,
                    "processed": 0,
                    "successful": 0,
                    "failed": 0,
                    "status": "no_work"
                }
            
            ready_links = router_result["ready_for_scraping"]
            print(f"   📋 [trace:{trace_id}] Got {len(ready_links)} links ready for scraping")
            
            # Process links with concurrency control
            successful = 0
            failed = 0
            semaphore = asyncio.Semaphore(self.concurrent_scrapers)
            
            async def process_single_link(link_data: Dict[str, Any]) -> None:
                nonlocal successful, failed
                
                async with semaphore:
                    link_id = link_data["link_id"]
                    raw_id = link_data["raw_id"]
                    url = link_data["url"]
                    link_trace_id = link_data["trace_id"]
                    
                    try:
                        print(f"   🕷️  [trace:{link_trace_id}] Scraping link_id={link_id}")
                        
                        # Run scraper
                        scraped = await self.scraper.scrape_post(url, link_id, link_trace_id)
                        
                        # Convert result
                        result = self._convert_scraped_to_scraping_result(scraped)
                        
                        if result.success:
                            # Update database with successful result
                            await self.router.update_scraping_status(raw_id, 'completed', result)
                            await self.router.update_link_status(link_id, 'scraped')
                            successful += 1
                            print(f"   ✅ [trace:{link_trace_id}] Successfully scraped link_id={link_id}")
                            
                        else:
                            # Handle failure - decide between retry or failed
                            # This could be enhanced with more sophisticated retry logic
                            await self.router.update_scraping_status(raw_id, 'retry', error_message=result.error_message)
                            failed += 1
                            print(f"   ❌ [trace:{link_trace_id}] Failed to scrape link_id={link_id}: {result.error_message}")
                        
                    except Exception as e:
                        # Handle unexpected errors
                        await self.router.update_scraping_status(raw_id, 'failed', error_message=f"Worker exception: {e}")
                        failed += 1
                        print(f"   ❌ [trace:{link_trace_id}] Exception processing link_id={link_id}: {e}")
            
            # Process all links concurrently
            await asyncio.gather(
                *[process_single_link(link_data) for link_data in ready_links],
                return_exceptions=True
            )
            
            # Calculate timing
            batch_duration = (datetime.now(timezone.utc) - batch_start).total_seconds()
            
            print(f"   📊 [trace:{trace_id}] Batch completed in {batch_duration:.1f}s")
            print(f"      ✅ Successful: {successful}")
            print(f"      ❌ Failed: {failed}")
            
            return {
                "trace_id": trace_id,
                "batch_size": len(ready_links),
                "processed": len(ready_links),
                "successful": successful,
                "failed": failed,
                "duration_seconds": batch_duration,
                "status": "completed"
            }
            
        except Exception as e:
            print(f"   ❌ [trace:{trace_id}] Batch processing error: {e}")
            return {
                "trace_id": trace_id,
                "batch_size": batch_size,
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "duration_seconds": (datetime.now(timezone.utc) - batch_start).total_seconds(),
                "error": str(e),
                "status": "error"
            }
    
    async def run_continuous_worker(self) -> None:
        """
        Run the worker continuously, processing batches as work becomes available
        """
        print(f"🚀 Starting continuous LinkedIn posts worker")
        print(f"   ⏱️  Batch size: {self.batch_size}")
        print(f"   😴 Sleep between batches: {self.worker_sleep_seconds}s")
        print(f"   🔄 Max consecutive errors: {self.max_consecutive_errors}")
        
        consecutive_errors = 0
        total_batches = 0
        total_processed = 0
        total_successful = 0
        
        start_time = datetime.now(timezone.utc)
        
        try:
            while True:
                try:
                    # Process a batch
                    result = await self.process_batch()
                    total_batches += 1
                    
                    if result["status"] == "completed":
                        total_processed += result["processed"]
                        total_successful += result["successful"]
                        consecutive_errors = 0
                        
                        if result["processed"] > 0:
                            print(f"\\n📈 Worker stats: {total_batches} batches, {total_processed} processed, {total_successful} successful")
                    
                    elif result["status"] == "no_work":
                        consecutive_errors = 0
                        # No logging for no work - keep output clean
                    
                    elif result["status"] == "error":
                        consecutive_errors += 1
                        print(f"\\n⚠️  Batch error ({consecutive_errors}/{self.max_consecutive_errors}): {result.get('error')}")
                        
                        if consecutive_errors >= self.max_consecutive_errors:
                            print(f"❌ Too many consecutive errors. Stopping worker.")
                            break
                    
                    # Sleep between batches
                    await asyncio.sleep(self.worker_sleep_seconds)
                
                except KeyboardInterrupt:
                    print(f"\\n🛑 Worker stopped by user")
                    break
                    
                except Exception as e:
                    consecutive_errors += 1
                    print(f"\\n❌ Unexpected worker error ({consecutive_errors}/{self.max_consecutive_errors}): {e}")
                    
                    if consecutive_errors >= self.max_consecutive_errors:
                        print(f"❌ Too many consecutive errors. Stopping worker.")
                        break
                    
                    await asyncio.sleep(self.worker_sleep_seconds * 2)  # Longer sleep on error
        
        finally:
            # Print final statistics
            uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
            print(f"\\n📊 Final worker statistics:")
            print(f"   ⏱️  Uptime: {uptime:.0f} seconds")
            print(f"   🔄 Total batches: {total_batches}")
            print(f"   📝 Total processed: {total_processed}")
            print(f"   ✅ Total successful: {total_successful}")
            if total_processed > 0:
                success_rate = (total_successful / total_processed) * 100
                print(f"   📊 Success rate: {success_rate:.1f}%")


async def main():
    """CLI entry point for posts worker"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LinkedIn Posts Scraper Worker")
    parser.add_argument("command", choices=[
        "run-worker",
        "process-batch", 
        "scrape-single",
        "status"
    ], help="Command to run")
    
    # Worker configuration
    parser.add_argument("--database-url", type=str, help="Database URL (or use DATABASE_URL env)")
    parser.add_argument("--storage", type=str, default="./storage", help="Storage base directory")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size for processing")
    parser.add_argument("--concurrent", type=int, default=2, help="Concurrent scrapers")
    parser.add_argument("--sleep", type=int, default=10, help="Sleep seconds between batches")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    
    # Single scrape options
    parser.add_argument("--url", type=str, help="LinkedIn post URL for single scrape")
    parser.add_argument("--link-id", type=int, help="Database link ID for single scrape")
    
    args = parser.parse_args()
    
    # Get database URL
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL is required")
        return
    
    # Initialize worker
    worker = LinkedInPostsWorker(
        database_url=database_url,
        storage_base=args.storage,
        headless=args.headless,
        concurrent_scrapers=args.concurrent
    )
    
    # Update configuration from args
    worker.batch_size = args.batch_size
    worker.worker_sleep_seconds = args.sleep
    
    # Run requested command
    if args.command == "run-worker":
        await worker.run_continuous_worker()
        
    elif args.command == "process-batch":
        result = await worker.process_batch(args.batch_size)
        print("\\n📊 Batch Results:")
        print(json.dumps(result, indent=2))
        
    elif args.command == "scrape-single":
        if not args.url:
            print("❌ --url is required for scrape-single")
            return
        
        result = await worker.scrape_single_post(args.url, args.link_id)
        print("\\n📊 Scraping Results:")
        print(json.dumps(result, indent=2))
        
    elif args.command == "status":
        stats = await worker.router.get_scraping_statistics()
        print("\\n📊 Scraping Statistics:")
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
