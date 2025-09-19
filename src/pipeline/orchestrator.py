#!/usr/bin/env python3
"""
LinkedIn Scraper Pipeline Orchestrator

Coordinates the complete pipeline:
1. Google Sheets ingestion 
2. Link classification and queuing
3. LinkedIn scraping (jobs & posts)
4. Data storage and backup

Usage:
    python -m src.pipeline.orchestrator run-full-pipeline
    python -m src.pipeline.orchestrator ingest-only
    python -m src.pipeline.orchestrator scrape-queue
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingest.google_sheets_run import run_google_sheets_ingest
from src.db.import_and_backup import import_and_backup
from src.db.classify_and_queue import migrate_and_classify


class LinkedInScraperPipeline:
    """Main pipeline orchestrator for LinkedIn scraping workflow"""
    
    def __init__(self):
        self.database_url = os.environ.get("DATABASE_URL", "")
        self.storage_base = Path("./storage")
        self.storage_base.mkdir(exist_ok=True)
        
        # Ensure required environment variables
        self._validate_environment()
    
    def _validate_environment(self):
        """Validate required environment variables and dependencies"""
        required_vars = ["DATABASE_URL"]
        missing = [var for var in required_vars if not os.environ.get(var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        # Check for Google Sheets URLs
        if not os.environ.get("GOOGLE_SHEETS_URLS") and not os.environ.get("SHEETS_CONFIG"):
            print("⚠️  Warning: No GOOGLE_SHEETS_URLS or SHEETS_CONFIG found")
    
    async def run_full_pipeline(
        self, 
        sheets_urls: Optional[List[str]] = None,
        month_filter: str = "aug",
        max_scrape_links: int = 50
    ) -> Dict[str, Any]:
        """
        Run the complete pipeline from Google Sheets to scraped data
        
        Args:
            sheets_urls: List of Google Sheets URLs to process
            month_filter: Month filter for sheet tabs
            max_scrape_links: Maximum links to scrape in this run
        
        Returns:
            Dict with pipeline results and statistics
        """
        pipeline_start = datetime.now(timezone.utc)
        results = {
            "pipeline_start": pipeline_start.isoformat(),
            "stages": {}
        }
        
        try:
            print("🚀 Starting LinkedIn Scraper Pipeline")
            
            # Stage 1: Google Sheets Ingestion
            print("\n📊 Stage 1: Google Sheets Ingestion")
            ingest_result = await self._run_ingestion_stage(sheets_urls, month_filter)
            results["stages"]["ingestion"] = ingest_result
            
            # Stage 2: Database Import
            print("\n💾 Stage 2: Database Import & Backup")
            if ingest_result.get("output_csv"):
                import_result = await self._run_import_stage(ingest_result["output_csv"])
                results["stages"]["import"] = import_result
            else:
                print("⚠️  No CSV output from ingestion, skipping import")
                results["stages"]["import"] = {"status": "skipped", "reason": "no_csv"}
            
            # Stage 3: Classification & Queuing
            print("\n🏷️  Stage 3: Classification & Queuing")
            classify_result = await self._run_classify_stage()
            results["stages"]["classification"] = classify_result
            
            # Stage 4: LinkedIn Scraping
            print("\n🕷️  Stage 4: LinkedIn Scraping")
            scrape_result = await self._run_scraping_stage(max_scrape_links)
            results["stages"]["scraping"] = scrape_result
            
            # Pipeline completion
            pipeline_end = datetime.now(timezone.utc)
            results["pipeline_end"] = pipeline_end.isoformat()
            results["duration_seconds"] = (pipeline_end - pipeline_start).total_seconds()
            results["status"] = "completed"
            
            print(f"\n✅ Pipeline completed in {results['duration_seconds']:.1f} seconds")
            return results
            
        except Exception as e:
            results["status"] = "error"
            results["error"] = str(e)
            print(f"\n❌ Pipeline failed: {e}")
            raise
    
    async def _run_ingestion_stage(
        self, 
        sheets_urls: Optional[List[str]], 
        month_filter: str
    ) -> Dict[str, Any]:
        """Run Google Sheets ingestion stage"""
        try:
            # Determine URLs to process
            if not sheets_urls:
                from src.app import load_urls_from_env_and_config
                sheets_urls = load_urls_from_env_and_config()
            
            if not sheets_urls:
                raise ValueError("No Google Sheets URLs provided")
            
            print(f"   📋 Processing {len(sheets_urls)} Google Sheets")
            
            # Run ingestion
            stats = run_google_sheets_ingest(
                urls=sheets_urls,
                month_filter=month_filter,
                output_csv=None  # Will auto-generate timestamped path
            )
            
            print(f"   ✅ Ingested {stats['total_links_unique']} unique links")
            return stats
            
        except Exception as e:
            print(f"   ❌ Ingestion failed: {e}")
            raise
    
    async def _run_import_stage(self, csv_path: str) -> Dict[str, Any]:
        """Run database import stage"""
        try:
            print(f"   📥 Importing from {csv_path}")
            
            backup_path = import_and_backup(
                database_url=self.database_url,
                csv_path=csv_path,
                backup_dir=str(self.storage_base / "backups"),
                insert_window_minutes=10
            )
            
            print(f"   💾 Backup created: {backup_path}")
            return {
                "csv_path": csv_path,
                "backup_path": backup_path,
                "status": "completed"
            }
            
        except Exception as e:
            print(f"   ❌ Import failed: {e}")
            raise
    
    async def _run_classify_stage(self) -> Dict[str, Any]:
        """Run classification and queuing stage"""
        try:
            print("   🔍 Classifying links and updating status")
            
            result = migrate_and_classify(self.database_url)
            
            print(f"   ✅ Classified {result['new_classified']} new links")
            print(f"   📋 Total queued: {result['queued_total']}")
            
            return result
            
        except Exception as e:
            print(f"   ❌ Classification failed: {e}")
            raise
    
    async def _run_scraping_stage(self, max_links: int = 50) -> Dict[str, Any]:
        """Run LinkedIn scraping stage"""
        try:
            from src.workers.posts_worker import LinkedInPostsWorker
            from src.routers.posts_router import LinkedInPostsRouter
            
            print(f"   🔍 Looking for up to {max_links} links to scrape")
            
            # Initialize posts router for migration and queue management
            router = LinkedInPostsRouter(self.database_url, str(self.storage_base))
            
            # Apply migration if needed
            await router.apply_migration()
            
            # Initialize worker for processing
            worker = LinkedInPostsWorker(
                database_url=self.database_url,
                storage_base=str(self.storage_base),
                headless=True,
                concurrent_scrapers=2
            )
            
            # Process a batch of posts
            batch_size = min(max_links, 10)  # Reasonable batch size
            scraping_result = await worker.process_batch(batch_size)
            
            if scraping_result["status"] == "no_work":
                print("   ✅ No post links found for scraping")
                return {
                    "status": "no_work",
                    "processed": 0,
                    "successful": 0,
                    "message": "No queued post links available"
                }
            
            print(f"   ✅ Processed {scraping_result['processed']} links, {scraping_result['successful']} successful")
            
            return {
                "status": "completed",
                "processed": scraping_result["processed"],
                "successful": scraping_result["successful"],
                "failed": scraping_result["failed"],
                "duration_seconds": scraping_result.get("duration_seconds"),
                "trace_id": scraping_result.get("trace_id")
            }
            
        except Exception as e:
            print(f"   ❌ Scraping failed: {e}")
            raise
    
    async def ingest_only(
        self, 
        sheets_urls: Optional[List[str]] = None,
        month_filter: str = "aug"
    ) -> Dict[str, Any]:
        """Run only the ingestion stage"""
        print("📊 Running ingestion-only pipeline")
        return await self._run_ingestion_stage(sheets_urls, month_filter)


async def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LinkedIn Scraper Pipeline Orchestrator")
    parser.add_argument("command", choices=[
        "run-full-pipeline", 
        "ingest-only", 
        "classify-only",
        "scrape-queue"
    ], help="Pipeline command to run")
    parser.add_argument("--sheets-urls", type=str, help="Comma-separated Google Sheets URLs")
    parser.add_argument("--month-filter", type=str, default="aug", help="Month filter for sheets")
    parser.add_argument("--max-scrape", type=int, default=50, help="Max links to scrape")
    
    args = parser.parse_args()
    
    pipeline = LinkedInScraperPipeline()
    
    # Parse URLs if provided
    sheets_urls = None
    if args.sheets_urls:
        sheets_urls = [url.strip() for url in args.sheets_urls.split(",") if url.strip()]
    
    # Run requested command
    if args.command == "run-full-pipeline":
        result = await pipeline.run_full_pipeline(
            sheets_urls=sheets_urls,
            month_filter=args.month_filter,
            max_scrape_links=args.max_scrape
        )
    elif args.command == "ingest-only":
        result = await pipeline.ingest_only(
            sheets_urls=sheets_urls,
            month_filter=args.month_filter
        )
    elif args.command == "classify-only":
        result = await pipeline._run_classify_stage()
    elif args.command == "scrape-queue":
        result = await pipeline._run_scraping_stage(args.max_scrape)
    
    # Output results
    print("\n📊 Pipeline Results:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
