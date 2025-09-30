#!/usr/bin/env python3
"""
Simple Direct Re-scraper for LinkedIn Jobs
==========================================

Re-scrapes all jobs in linkedin_jobs_raw table using the updated scraper.
"""

import os
import time
import psycopg
from datetime import datetime, timezone


def get_all_jobs():
    """Get all jobs from linkedin_jobs_raw table"""
    conn = psycopg.connect('postgresql://postgres:postgres@localhost:5432/data_lake')
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, url, link_id, success, 
               COALESCE(LENGTH(extracted_data->>'description_text'), 0) as desc_length
        FROM linkedin_jobs_raw 
        ORDER BY id ASC
    """)
    
    jobs = []
    for row in cur.fetchall():
        jobs.append({
            'raw_id': row[0],
            'url': row[1], 
            'link_id': row[2],
            'success': row[3],
            'desc_length': row[4]
        })
    
    cur.close()
    conn.close()
    return jobs


def reset_all_jobs():
    """Reset all jobs for re-scraping"""
    conn = psycopg.connect('postgresql://postgres:postgres@localhost:5432/data_lake')
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE linkedin_jobs_raw 
        SET success = false, 
            scraped_at = NULL,
            extracted_data = NULL
    """)
    
    updated_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"Reset {updated_count} jobs for re-scraping")
    return updated_count


def add_jobs_to_linkedin_links():
    """Add/update jobs in linkedin_links table so the existing scraper can process them"""
    conn = psycopg.connect('postgresql://postgres:postgres@localhost:5432/data_lake')
    cur = conn.cursor()
    
    # Get all jobs from linkedin_jobs_raw
    cur.execute("SELECT id, url, link_id FROM linkedin_jobs_raw ORDER BY id ASC")
    jobs = cur.fetchall()
    
    added_count = 0
    updated_count = 0
    
    for raw_id, url, link_id in jobs:
        # Check if this link_id exists in linkedin_links
        cur.execute("SELECT id, status FROM linkedin_links WHERE id = %s", (link_id,))
        existing = cur.fetchone()
        
        if existing:
            # Update to queued if not already
            if existing[1] != 'queued':
                cur.execute("""
                    UPDATE linkedin_links 
                    SET status = 'queued', 
                        classification = 'job',
                        updated_at = NOW()
                    WHERE id = %s
                """, (link_id,))
                updated_count += 1
        else:
            # Insert new entry
            cur.execute("""
                INSERT INTO linkedin_links (id, url, status, classification, priority, created_at, updated_at)
                VALUES (%s, %s, 'queued', 'job', 5, NOW(), NOW())
                ON CONFLICT (url) DO UPDATE SET 
                    status = 'queued',
                    classification = 'job',
                    updated_at = NOW()
            """, (link_id, url))
            added_count += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"Added {added_count} new jobs, updated {updated_count} existing jobs to queued status")
    return added_count + updated_count


def run_scraper_until_complete():
    """Run the existing scraper in batches until all jobs are processed"""
    from src.scraper.linkedin_job_scraper import LinkedInJobScraperService
    
    # Set environment variables  
    os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/data_lake'
    os.environ['LINKEDIN_EMAIL'] = 'bhatiyash456@gmail.com'
    os.environ['LINKEDIN_PASSWORD'] = 'Bhati@4567'
    
    scraper = LinkedInJobScraperService()
    
    batch_count = 0
    total_processed = 0
    total_successful = 0
    total_failed = 0
    
    print("🚀 Running scraper batches until all jobs are processed...")
    print("-" * 60)
    
    while True:
        batch_count += 1
        print(f"🔄 Running batch {batch_count}...")
        
        try:
            # Run a batch of scraping
            result = scraper.run_scraping_batch(max_jobs=10)  # Process 10 jobs per batch
            
            batch_total = result.get('total', 0)
            batch_successful = result.get('successful', 0)
            batch_failed = result.get('failed', 0)
            
            total_processed += batch_total
            total_successful += batch_successful
            total_failed += batch_failed
            
            print(f"   Batch {batch_count} result: {result}")
            
            # If no jobs were processed, we're done
            if batch_total == 0:
                print("✅ No more jobs to process")
                break
                
            # Brief pause between batches
            if batch_total > 0:
                print("⏳ Waiting 5 seconds before next batch...")
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ Batch {batch_count} failed: {e}")
            break
    
    print("-" * 60)
    print(f"🎉 Scraping complete!")
    print(f"Total batches: {batch_count}")
    print(f"Total processed: {total_processed}")
    print(f"Successful: {total_successful}")
    print(f"Failed: {total_failed}")
    
    return {
        'batches': batch_count,
        'total': total_processed,
        'successful': total_successful,
        'failed': total_failed
    }


def check_final_status():
    """Check final status of all jobs"""
    jobs = get_all_jobs()
    successful_jobs = sum(1 for job in jobs if job['success'])
    jobs_with_desc = sum(1 for job in jobs if job['desc_length'] > 100 and job['success'])
    
    print("=" * 60)
    print("📊 Final Status Report:")
    print(f"  Total jobs: {len(jobs)}")
    print(f"  Successful jobs: {successful_jobs}")
    print(f"  Jobs with descriptions: {jobs_with_desc}")
    print(f"  Success rate: {(successful_jobs/len(jobs)*100):.1f}%")
    print(f"  Description rate: {(jobs_with_desc/successful_jobs*100 if successful_jobs > 0 else 0):.1f}%")
    
    # Show jobs that still don't have descriptions
    jobs_without_desc = [job for job in jobs if job['success'] and job['desc_length'] <= 100]
    if jobs_without_desc:
        print(f"\nJobs still without proper descriptions ({len(jobs_without_desc)}):")
        for job in jobs_without_desc[:5]:  # Show first 5
            print(f"  ID {job['raw_id']}: {job['url'][:70]}... (len: {job['desc_length']})")
    
    return {
        'total': len(jobs),
        'successful': successful_jobs,
        'with_descriptions': jobs_with_desc
    }


def main():
    """Main execution function"""
    print("🚀 Simple LinkedIn Jobs Re-scraper")
    print("=" * 60)
    
    # Step 1: Check initial status
    print("📊 Initial Status:")
    initial_jobs = get_all_jobs()
    initial_with_desc = sum(1 for job in initial_jobs if job['desc_length'] > 100 and job['success'])
    print(f"  Total jobs: {len(initial_jobs)}")
    print(f"  Jobs with descriptions: {initial_with_desc}")
    print(f"  Jobs without descriptions: {len(initial_jobs) - initial_with_desc}")
    
    # Step 2: Reset all jobs
    print("\n🔄 Resetting all jobs for re-scraping...")
    reset_all_jobs()
    
    # Step 3: Ensure all jobs are in linkedin_links with queued status  
    print("\n📝 Setting up jobs in linkedin_links table...")
    add_jobs_to_linkedin_links()
    
    # Step 4: Run the scraper until complete
    print("\n🤖 Running scraper batches...")
    scraper_result = run_scraper_until_complete()
    
    # Step 5: Check final results
    print("\n📈 Checking final results...")
    final_result = check_final_status()
    
    # Summary
    improvement = final_result['with_descriptions'] - initial_with_desc
    print(f"\n🎉 Re-scraping Complete!")
    print(f"  Improvement: +{improvement} jobs now have descriptions")
    print(f"  Final: {final_result['with_descriptions']}/{final_result['total']} jobs with complete data")
    
    return final_result


if __name__ == "__main__":
    main()