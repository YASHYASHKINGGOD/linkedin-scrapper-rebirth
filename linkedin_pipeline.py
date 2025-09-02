#!/usr/bin/env python3
"""
LinkedIn Scraper Pipeline - Main CLI Interface

Unified command-line interface for the complete LinkedIn scraping pipeline:
- Google Sheets ingestion and link extraction
- Database management and classification  
- LinkedIn posts scraping with queue management
- Status monitoring and statistics

Usage Examples:
    # Run complete pipeline
    python linkedin_pipeline.py run-full-pipeline
    
    # Individual stages
    python linkedin_pipeline.py ingest-google-sheets --urls "url1,url2"
    python linkedin_pipeline.py classify-links
    python linkedin_pipeline.py scrape-posts --batch-size 10
    
    # Worker management
    python linkedin_pipeline.py run-posts-worker
    python linkedin_pipeline.py scrape-single-post --url "https://linkedin.com/posts/..."
    
    # Monitoring
    python linkedin_pipeline.py pipeline-status
    python linkedin_pipeline.py scraping-stats

Environment Variables:
    DATABASE_URL - PostgreSQL connection string (required)
    GOOGLE_SHEETS_URLS - Comma-separated Google Sheets URLs
    SHEETS_CONFIG - Path to YAML config file with sheet URLs
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


async def main():
    """Main CLI entry point with comprehensive command handling"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="LinkedIn Scraper Pipeline - Complete workflow management",
        epilog="Use 'python linkedin_pipeline.py <command> --help' for command-specific options"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # =============================================================================
    # PIPELINE COMMANDS
    # =============================================================================
    
    # Full pipeline
    cmd_full = subparsers.add_parser("run-full-pipeline", help="Run complete pipeline from sheets to scraped data")
    cmd_full.add_argument("--sheets-urls", type=str, help="Comma-separated Google Sheets URLs")
    cmd_full.add_argument("--month-filter", type=str, default="aug", help="Month filter for sheet tabs")
    cmd_full.add_argument("--max-scrape", type=int, default=20, help="Max links to scrape")
    
    # Individual pipeline stages  
    cmd_ingest = subparsers.add_parser("ingest-google-sheets", help="Extract links from Google Sheets")
    cmd_ingest.add_argument("--urls", type=str, help="Comma-separated Google Sheets URLs")
    cmd_ingest.add_argument("--month-filter", type=str, default="aug", help="Month filter")
    cmd_ingest.add_argument("--output-csv", type=str, help="Output CSV path")
    
    cmd_import = subparsers.add_parser("import-to-database", help="Import CSV links to database")
    cmd_import.add_argument("--csv", type=str, required=True, help="CSV file to import")
    cmd_import.add_argument("--backup-dir", type=str, default="./storage/backups", help="Backup directory")
    
    cmd_classify = subparsers.add_parser("classify-links", help="Classify and queue links")
    
    # =============================================================================
    # SCRAPING COMMANDS  
    # =============================================================================
    
    cmd_scrape_batch = subparsers.add_parser("scrape-posts", help="Process queued post links")
    cmd_scrape_batch.add_argument("--batch-size", type=int, default=10, help="Batch size")
    cmd_scrape_batch.add_argument("--concurrent", type=int, default=2, help="Concurrent scrapers")
    cmd_scrape_batch.add_argument("--headless", action="store_true", default=True, help="Headless browser")
    
    cmd_scrape_single = subparsers.add_parser("scrape-single-post", help="Scrape a single LinkedIn post")
    cmd_scrape_single.add_argument("--url", type=str, required=True, help="LinkedIn post URL")
    cmd_scrape_single.add_argument("--link-id", type=int, help="Database link ID")
    cmd_scrape_single.add_argument("--headless", action="store_true", default=True, help="Headless browser")
    
    cmd_worker = subparsers.add_parser("run-posts-worker", help="Run continuous posts scraping worker")
    cmd_worker.add_argument("--batch-size", type=int, default=5, help="Worker batch size")  
    cmd_worker.add_argument("--concurrent", type=int, default=2, help="Concurrent scrapers")
    cmd_worker.add_argument("--sleep", type=int, default=10, help="Sleep seconds between batches")
    cmd_worker.add_argument("--headless", action="store_true", default=True, help="Headless browser")
    
    # =============================================================================
    # DATABASE & QUEUE MANAGEMENT
    # =============================================================================
    
    cmd_migrate = subparsers.add_parser("migrate-database", help="Apply database migrations")
    
    cmd_queue_status = subparsers.add_parser("queue-status", help="Show posts queue status")
    
    cmd_reset_failed = subparsers.add_parser("reset-failed", help="Reset failed scraping attempts")
    
    # =============================================================================
    # MONITORING & STATISTICS
    # =============================================================================
    
    cmd_pipeline_status = subparsers.add_parser("pipeline-status", help="Overall pipeline status")
    
    cmd_scraping_stats = subparsers.add_parser("scraping-stats", help="Detailed scraping statistics")
    
    cmd_storage_info = subparsers.add_parser("storage-info", help="Storage usage information")
    
    # =============================================================================
    # GLOBAL OPTIONS
    # =============================================================================
    
    parser.add_argument("--database-url", type=str, help="Database URL (overrides DATABASE_URL env)")
    parser.add_argument("--storage", type=str, default="./storage", help="Storage base directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Get database URL
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL is required. Set via environment variable or --database-url")
        return
    
    # Validate database URL format
    if not database_url.startswith(('postgresql://', 'postgres://')):
        print("❌ DATABASE_URL must be a PostgreSQL connection string")
        return
    
    print(f"🔗 Using database: {database_url[:30]}...")
    if args.verbose:
        print(f"📁 Storage directory: {args.storage}")
    
    try:
        # =============================================================================
        # HANDLE COMMANDS
        # =============================================================================
        
        if args.command == "run-full-pipeline":
            from src.pipeline.orchestrator import LinkedInScraperPipeline
            
            # Set environment variables for pipeline
            if database_url:
                os.environ["DATABASE_URL"] = database_url
                
            pipeline = LinkedInScraperPipeline()
            
            sheets_urls = None
            if args.sheets_urls:
                sheets_urls = [url.strip() for url in args.sheets_urls.split(",") if url.strip()]
            
            result = await pipeline.run_full_pipeline(
                sheets_urls=sheets_urls,
                month_filter=args.month_filter,
                max_scrape_links=args.max_scrape
            )
            
            print("\\n📊 Pipeline Results:")
            print(json.dumps(result, indent=2))
        
        elif args.command == "ingest-google-sheets":
            from src.ingest.google_sheets_run import run_google_sheets_ingest
            from src.app import load_urls_from_env_and_config
            
            urls = []
            if args.urls:
                urls = [u.strip() for u in args.urls.split(",") if u.strip()]
            else:
                urls = load_urls_from_env_and_config()
                
            if not urls:
                print("❌ No Google Sheets URLs found. Use --urls or set GOOGLE_SHEETS_URLS/SHEETS_CONFIG")
                return
                
            result = run_google_sheets_ingest(
                urls=urls,
                month_filter=args.month_filter,
                output_csv=args.output_csv
            )
            
            print("\\n📊 Ingestion Results:")
            print(json.dumps(result, indent=2))
        
        elif args.command == "import-to-database":
            from src.db.import_and_backup import import_and_backup
            
            backup_path = import_and_backup(
                database_url=database_url,
                csv_path=args.csv,
                backup_dir=args.backup_dir
            )
            
            print(f"✅ Import completed. Backup created: {backup_path}")
        
        elif args.command == "classify-links":
            from src.db.classify_and_queue import migrate_and_classify
            
            result = migrate_and_classify(database_url)
            
            print("\\n📊 Classification Results:")
            print(json.dumps(result, indent=2))
        
        elif args.command == "scrape-posts":
            from src.workers.posts_worker import LinkedInPostsWorker
            
            worker = LinkedInPostsWorker(
                database_url=database_url,
                storage_base=args.storage,
                headless=args.headless,
                concurrent_scrapers=args.concurrent
            )
            
            result = await worker.process_batch(args.batch_size)
            
            print("\\n📊 Scraping Results:")
            print(json.dumps(result, indent=2))
        
        elif args.command == "scrape-single-post":
            from src.workers.posts_worker import LinkedInPostsWorker
            
            worker = LinkedInPostsWorker(
                database_url=database_url,
                storage_base=args.storage,
                headless=args.headless
            )
            
            result = await worker.scrape_single_post(args.url, args.link_id)
            
            print("\\n📊 Scraping Results:")
            print(json.dumps(result, indent=2))
        
        elif args.command == "run-posts-worker":
            from src.workers.posts_worker import LinkedInPostsWorker
            
            worker = LinkedInPostsWorker(
                database_url=database_url,
                storage_base=args.storage,
                headless=args.headless,
                concurrent_scrapers=args.concurrent
            )
            
            worker.batch_size = args.batch_size
            worker.worker_sleep_seconds = args.sleep
            
            await worker.run_continuous_worker()
        
        elif args.command == "migrate-database":
            from src.routers.posts_router import LinkedInPostsRouter
            
            router = LinkedInPostsRouter(database_url, args.storage)
            await router.apply_migration()
            
            print("✅ Database migration completed")
        
        elif args.command in ["queue-status", "scraping-stats"]:
            from src.routers.posts_router import LinkedInPostsRouter
            
            router = LinkedInPostsRouter(database_url, args.storage)
            stats = await router.get_scraping_statistics()
            
            print("\\n📊 Scraping Statistics:")
            print(json.dumps(stats, indent=2))
        
        elif args.command == "reset-failed":
            import psycopg
            
            with psycopg.connect(database_url) as conn:
                result = conn.execute(\"\"\"
                    UPDATE public.linkedin_posts_raw 
                    SET status = 'retry', next_retry_at = now(), error_message = NULL
                    WHERE status = 'failed' AND attempt_count < max_attempts
                    RETURNING id
                \"\"\").fetchall()
            
            print(f"✅ Reset {len(result)} failed entries to retry status")
        
        elif args.command == "pipeline-status":
            # Combined status from multiple sources
            print("🔍 Gathering pipeline status...")
            
            # Database link counts
            import psycopg
            with psycopg.connect(database_url) as conn:
                conn.execute("SET TIME ZONE 'UTC'")
                
                link_stats = conn.execute(\"\"\"
                    SELECT 
                        classification,
                        status,
                        COUNT(*) as count
                    FROM public.linkedin_links 
                    GROUP BY classification, status
                    ORDER BY classification, status
                \"\"\").fetchall()
                
                print("\\n📋 LinkedIn Links Status:")
                for row in link_stats:
                    print(f"   {row[0] or 'unknown'} / {row[1] or 'new'}: {row[2]}")
            
            # Scraping statistics
            from src.routers.posts_router import LinkedInPostsRouter
            router = LinkedInPostsRouter(database_url, args.storage)
            scraping_stats = await router.get_scraping_statistics()
            
            print("\\n🕷️  Posts Scraping Status:")
            for key, value in scraping_stats.items():
                if value is not None and value != 0:
                    print(f"   {key}: {value}")
        
        elif args.command == "storage-info":
            import shutil
            storage_path = Path(args.storage)
            
            if storage_path.exists():
                total_size = sum(f.stat().st_size for f in storage_path.rglob('*') if f.is_file())
                file_count = len(list(storage_path.rglob('*')))
                
                print(f"\\n📁 Storage Information:")
                print(f"   Path: {storage_path.absolute()}")
                print(f"   Total size: {total_size / 1024 / 1024:.1f} MB")
                print(f"   Total files: {file_count}")
                
                # Breakdown by subdirectory
                for subdir in storage_path.iterdir():
                    if subdir.is_dir():
                        subdir_files = len(list(subdir.rglob('*')))
                        print(f"   {subdir.name}/: {subdir_files} files")
            else:
                print(f"📁 Storage directory does not exist: {storage_path}")
        
        else:
            print(f"❌ Unknown command: {args.command}")
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\\n❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
