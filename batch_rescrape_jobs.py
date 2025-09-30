#!/usr/bin/env python3
"""
Batch Re-scraping Script for LinkedIn Jobs
==========================================

This script processes all queued job links in batches to update missing job descriptions
using the corrected LinkedIn job scraper with the updated selectors.
"""

import os
import time
import psycopg
from src.scraper.linkedin_job_scraper import LinkedInJobScraperService


def get_rescrape_stats():
    """Get current statistics on jobs needing re-scraping"""
    conn = psycopg.connect('postgresql://postgres:postgres@localhost:5432/data_lake')
    cur = conn.cursor()
    
    # Count jobs in linkedin_jobs_raw without proper descriptions
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN extracted_data->>'description_text' IS NOT NULL 
                       AND LENGTH(extracted_data->>'description_text') > 100 THEN 1 END) as with_desc,
            COUNT(CASE WHEN extracted_data->>'description_text' IS NULL 
                       OR LENGTH(extracted_data->>'description_text') <= 100 THEN 1 END) as without_desc
        FROM linkedin_jobs_raw
    """)
    
    stats = cur.fetchone()
    total, with_desc, without_desc = stats
    
    # Count queued jobs ready for scraping
    cur.execute("SELECT COUNT(*) FROM linkedin_links WHERE status = 'queued' AND classification = 'job'")
    queued_count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return {
        'total_jobs': total,
        'with_descriptions': with_desc,
        'without_descriptions': without_desc,
        'queued_for_scraping': queued_count
    }


def run_batch_rescraping(batch_size=10, max_batches=None):
    """Run batch re-scraping of LinkedIn jobs"""
    
    # Set environment variables  
    os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/data_lake'
    os.environ['LINKEDIN_EMAIL'] = 'bhatiyash456@gmail.com'
    os.environ['LINKEDIN_PASSWORD'] = 'Bhati@4567'
    
    # Initialize scraper
    scraper = LinkedInJobScraperService()
    
    batch_count = 0
    total_processed = 0
    total_successful = 0
    total_failed = 0
    
    print("🚀 Starting batch re-scraping of LinkedIn jobs...")
    print("=" * 60)
    
    # Initial stats
    initial_stats = get_rescrape_stats()
    print(f"Initial Status:")
    print(f"  Total jobs in database: {initial_stats['total_jobs']}")
    print(f"  Jobs with descriptions: {initial_stats['with_descriptions']}")
    print(f"  Jobs without descriptions: {initial_stats['without_descriptions']}")
    print(f"  Jobs queued for scraping: {initial_stats['queued_for_scraping']}")
    print("-" * 60)
    
    while True:
        # Check if we have reached max batches
        if max_batches and batch_count >= max_batches:
            print(f"✋ Reached maximum batch limit ({max_batches})")
            break
            
        # Check if there are still queued jobs
        stats = get_rescrape_stats()
        if stats['queued_for_scraping'] == 0:
            print("✅ No more queued jobs to process")
            break
            
        batch_count += 1
        print(f"🔄 Processing Batch {batch_count}")
        print(f"   Queued jobs remaining: {stats['queued_for_scraping']}")
        
        # Run scraping batch
        try:
            result = scraper.run_scraping_batch(max_jobs=batch_size)
            
            # Update totals
            batch_total = result.get('total', 0)
            batch_successful = result.get('successful', 0)
            batch_failed = result.get('failed', 0)
            
            total_processed += batch_total
            total_successful += batch_successful
            total_failed += batch_failed
            
            print(f"   Batch Result: {result}")
            
            # If no jobs were processed, break to avoid infinite loop
            if batch_total == 0:
                print("⚠️  No jobs processed in this batch, stopping")
                break
                
        except Exception as e:
            print(f"❌ Batch {batch_count} failed: {e}")
            batch_failed += batch_size
            total_failed += batch_size
            
        # Brief pause between batches to be respectful to LinkedIn
        if stats['queued_for_scraping'] > batch_size:  # More batches to go
            print("⏳ Waiting 10 seconds before next batch...")
            time.sleep(10)
            
        print("-" * 40)
    
    # Final summary
    final_stats = get_rescrape_stats()
    print("🎉 Batch re-scraping completed!")
    print("=" * 60)
    print(f"Final Status:")
    print(f"  Total jobs with descriptions: {final_stats['with_descriptions']} (was {initial_stats['with_descriptions']})")
    print(f"  Jobs without descriptions: {final_stats['without_descriptions']} (was {initial_stats['without_descriptions']})")
    print(f"  Improvement: +{final_stats['with_descriptions'] - initial_stats['with_descriptions']} descriptions extracted")
    print(f"")
    print(f"Processing Summary:")
    print(f"  Batches processed: {batch_count}")
    print(f"  Total jobs processed: {total_processed}")
    print(f"  Successful: {total_successful}")
    print(f"  Failed: {total_failed}")
    print(f"  Success rate: {(total_successful/max(total_processed,1)*100):.1f}%")
    
    return {
        'batches_processed': batch_count,
        'total_processed': total_processed,
        'successful': total_successful,
        'failed': total_failed,
        'initial_stats': initial_stats,
        'final_stats': final_stats
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch re-scrape LinkedIn jobs for missing descriptions")
    parser.add_argument("--batch-size", type=int, default=10, help="Jobs per batch (default: 10)")
    parser.add_argument("--max-batches", type=int, help="Maximum number of batches to run")
    parser.add_argument("--stats-only", action="store_true", help="Show stats without running scraper")
    
    args = parser.parse_args()
    
    if args.stats_only:
        stats = get_rescrape_stats()
        print("Current Re-scraping Stats:")
        print(f"  Total jobs: {stats['total_jobs']}")
        print(f"  With descriptions: {stats['with_descriptions']}")
        print(f"  Without descriptions: {stats['without_descriptions']}")  
        print(f"  Queued for scraping: {stats['queued_for_scraping']}")
    else:
        run_batch_rescraping(batch_size=args.batch_size, max_batches=args.max_batches)