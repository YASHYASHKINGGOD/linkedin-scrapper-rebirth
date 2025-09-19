#!/usr/bin/env python3
"""
LinkedIn Posts Router

Manages the flow of LinkedIn post links from classification to scraping:
1. Queries linkedin_links table for classification='post' and status='queued'  
2. Creates entries in linkedin_posts_raw table
3. Manages state transitions (queued → scraping → scraped)
4. Handles retries and dead letter queue for failed scrapes
5. Coordinates with scraper workers

Usage:
    python -m src.routers.posts_router process-queue
    python -m src.routers.posts_router status
"""

import os
import json
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, NamedTuple
from dataclasses import dataclass, asdict
import psycopg
from pathlib import Path


@dataclass
class PostLink:
    """Data structure for a post link to be processed"""
    id: int
    link_id: int
    url: str
    status: str
    attempt_count: int
    max_attempts: int
    next_retry_at: Optional[datetime] = None
    trace_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass  
class ScrapingResult:
    """Result from scraping a LinkedIn post"""
    success: bool
    raw_html_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    metadata_json_path: Optional[str] = None
    scrape_metadata: Dict[str, Any] = None
    extracted_data: Dict[str, Any] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.scrape_metadata is None:
            self.scrape_metadata = {}
        if self.extracted_data is None:
            self.extracted_data = {}


class LinkedInPostsRouter:
    """Router for managing LinkedIn post scraping workflow"""
    
    def __init__(self, database_url: str, storage_base: str = "./storage"):
        self.database_url = database_url
        self.storage_base = Path(storage_base)
        self.posts_storage = self.storage_base / "posts"
        self.posts_storage.mkdir(parents=True, exist_ok=True)
        
        # Default configuration
        self.batch_size = 10
        self.retry_delay_base = 60  # Base retry delay in seconds
        self.max_retry_delay = 3600  # Max retry delay in seconds
        
    def _get_trace_id(self) -> str:
        """Generate a new trace ID for request tracking"""
        return str(uuid.uuid4())[:8]
    
    def _calculate_retry_delay(self, attempt_count: int) -> timedelta:
        """Calculate exponential backoff delay for retries"""
        delay_seconds = min(
            self.retry_delay_base * (2 ** attempt_count),
            self.max_retry_delay
        )
        return timedelta(seconds=delay_seconds)
    
    async def apply_migration(self) -> None:
        """Apply the linkedin_posts_raw table migration"""
        from src.db.migrations.create_posts_table import create_linkedin_posts_raw_table
        
        try:
            create_linkedin_posts_raw_table(self.database_url)
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise
    
    async def get_queued_post_links(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get LinkedIn post links that are queued for scraping
        
        Returns:
            List of post links ready for processing
        """
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        query = f"""
        SELECT 
            ll.id as link_id,
            ll.url,
            ll.status as link_status,
            ll.classification,
            lpr.id as raw_id,
            lpr.success as raw_status,
            ll.created_at
        FROM public.linkedin_links ll
        LEFT JOIN public.linkedin_posts_raw lpr ON ll.id = lpr.link_id
        WHERE ll.classification = 'post' 
          AND (ll.status = 'queued' OR ll.status = 'pending')
          AND (lpr.id IS NULL OR lpr.success = false)
        ORDER BY ll.id ASC
        {limit_clause}
        """
        
        with psycopg.connect(self.database_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            rows = conn.execute(query).fetchall()
            
        return [dict(row._asdict()) for row in rows]
    
    async def create_or_update_raw_entry(self, link_id: int, url: str, trace_id: str) -> int:
        """
        Create or update entry in linkedin_posts_raw table
        
        Returns:
            The raw entry ID
        """
        with psycopg.connect(self.database_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            with conn.transaction():
                # Try to insert, on conflict update
                result = conn.execute("""
                    INSERT INTO public.linkedin_posts_raw 
                        (link_id, trace_id, url, success)
                    VALUES (%s, %s, %s, false)
                    ON CONFLICT (link_id) DO UPDATE SET
                        trace_id = EXCLUDED.trace_id
                    RETURNING id
                """, [link_id, trace_id, url]).fetchone()
                
                return result[0]
    
    async def update_link_status(self, link_id: int, status: str) -> None:
        """Update status in linkedin_links table"""
        with psycopg.connect(self.database_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            conn.execute("""
                UPDATE public.linkedin_links 
                SET status = %s
                WHERE id = %s
            """, [status, link_id])
    
    async def update_scraping_status(
        self, 
        raw_id: int, 
        status: str,
        result: Optional[ScrapingResult] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update scraping status and results in linkedin_posts_raw table"""
        
        # For our simplified schema, just update what we have
        if status == 'completed' and result:
            with psycopg.connect(self.database_url) as conn:
                conn.execute("""
                    UPDATE public.linkedin_posts_raw 
                    SET success = true,
                        raw_html_path = %s,
                        screenshot_path = %s,
                        extracted_data = %s,
                        scraped_at = now()
                    WHERE id = %s
                """, [
                    result.raw_html_path,
                    result.screenshot_path,
                    json.dumps(result.extracted_data),
                    raw_id
                ])
        else:
            # Just mark as not successful for now
            with psycopg.connect(self.database_url) as conn:
                conn.execute("""
                    UPDATE public.linkedin_posts_raw 
                    SET success = false
                    WHERE id = %s
                """, [raw_id])
    
    async def process_post_queue(self, batch_size: int = None) -> Dict[str, Any]:
        """
        Process a batch of queued post links
        
        This method:
        1. Gets queued post links
        2. Creates/updates raw entries  
        3. Marks links as 'scraping'
        4. Returns links ready for scraper workers
        
        Returns:
            Processing results and statistics
        """
        batch_size = batch_size or self.batch_size
        trace_id = self._get_trace_id()
        
        print(f"🔍 [trace:{trace_id}] Processing post queue (batch_size={batch_size})")
        
        # Get queued links
        queued_links = await self.get_queued_post_links(limit=batch_size)
        
        if not queued_links:
            print("   ✅ No queued post links found")
            return {
                "trace_id": trace_id,
                "processed": 0,
                "ready_for_scraping": [],
                "status": "no_work"
            }
        
        print(f"   📋 Found {len(queued_links)} queued post links")
        
        ready_for_scraping = []
        processed_count = 0
        
        for link_data in queued_links:
            try:
                link_id = link_data['link_id']
                url = link_data['url']
                raw_status = link_data['raw_status']
                
                print(f"   🔗 Processing link_id={link_id}, url={url[:60]}...")
                
                # Create or update raw entry
                raw_id = await self.create_or_update_raw_entry(link_id, url, trace_id)
                
                # Update linkedin_links status to 'scraping'
                await self.update_link_status(link_id, 'scraping')
                
                # Mark raw entry as 'scraping'
                await self.update_scraping_status(raw_id, 'scraping')
                
                # Add to ready list
                ready_for_scraping.append({
                    "link_id": link_id,
                    "raw_id": raw_id,
                    "url": url,
                    "trace_id": trace_id
                })
                
                processed_count += 1
                
            except Exception as e:
                print(f"   ❌ Error processing link_id={link_data['link_id']}: {e}")
                # Could add to dead letter queue here
                continue
        
        print(f"   ✅ Processed {processed_count} links, {len(ready_for_scraping)} ready for scraping")
        
        return {
            "trace_id": trace_id,
            "processed": processed_count,
            "ready_for_scraping": ready_for_scraping,
            "status": "ready"
        }
    
    async def get_scraping_statistics(self) -> Dict[str, Any]:
        """Get current scraping statistics"""
        
        stats_query = """
        SELECT 
            COUNT(*) FILTER (WHERE ll.status = 'queued' AND ll.classification = 'post') as queued_links,
            COUNT(*) FILTER (WHERE ll.status = 'scraping' AND ll.classification = 'post') as scraping_links,
            COUNT(*) FILTER (WHERE ll.status = 'scraped' AND ll.classification = 'post') as scraped_links,
            COUNT(*) FILTER (WHERE ll.status = 'failed' AND ll.classification = 'post') as failed_links,
            COUNT(*) FILTER (WHERE lpr.success = true) as successful_scrapes,
            COUNT(*) FILTER (WHERE lpr.success = false) as failed_scrapes,
            COUNT(lpr.id) as total_raw_entries,
            MIN(ll.created_at) as oldest_pending,
            MAX(lpr.scraped_at) as latest_scraped
        FROM public.linkedin_links ll
        LEFT JOIN public.linkedin_posts_raw lpr ON ll.id = lpr.link_id
        WHERE ll.classification = 'post'
        """
        
        with psycopg.connect(self.database_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            cursor = conn.execute(stats_query)
            row = cursor.fetchone()
            
        # Convert row to dict manually since we get a tuple
        column_names = [desc[0] for desc in cursor.description]
        stats = dict(zip(column_names, row))
        
        # Convert timestamps to ISO format
        for key in ['oldest_pending', 'latest_scraped']:
            if stats[key]:
                stats[key] = stats[key].isoformat()
        
        # Add calculated fields if needed
        # (avg_attempts removed as it's not in the current schema)
        
        return stats


async def main():
    """CLI entry point for posts router"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LinkedIn Posts Router")
    parser.add_argument("command", choices=[
        "process-queue",
        "status", 
        "migrate",
        "reset-failed"
    ], help="Command to run")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    parser.add_argument("--database-url", type=str, help="Database URL (or use DATABASE_URL env)")
    
    args = parser.parse_args()
    
    # Get database URL
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL is required")
        return
    
    router = LinkedInPostsRouter(database_url)
    
    if args.command == "migrate":
        await router.apply_migration()
        
    elif args.command == "process-queue":
        result = await router.process_post_queue(batch_size=args.batch_size)
        print("\n📊 Processing Results:")
        print(json.dumps(result, indent=2))
        
    elif args.command == "status":
        stats = await router.get_scraping_statistics()
        print("\n📊 Scraping Statistics:")
        print(json.dumps(stats, indent=2))
        
    elif args.command == "reset-failed":
        # Reset failed entries to retry status
        with psycopg.connect(database_url) as conn:
            result = conn.execute("""
                UPDATE public.linkedin_posts_raw 
                SET status = 'retry', next_retry_at = now(), error_message = NULL
                WHERE status = 'failed' AND attempt_count < max_attempts
                RETURNING id
            """).fetchall()
        
        print(f"✅ Reset {len(result)} failed entries to retry status")


if __name__ == "__main__":
    asyncio.run(main())
