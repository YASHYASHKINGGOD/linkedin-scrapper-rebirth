#!/usr/bin/env python3
"""
Direct LinkedIn Jobs Re-scraper
===============================

This script directly processes all jobs from linkedin_jobs_raw table to ensure
complete job details including descriptions are extracted using the updated scraper.
"""

import os
import time
import json
import psycopg
from datetime import datetime, timezone
from src.scraper.linkedin_job_scraper import LinkedInJobScraperService


def get_all_jobs_from_raw_table():
    """Get all job URLs from linkedin_jobs_raw table"""
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
            'current_success': row[3],
            'desc_length': row[4]
        })
    
    cur.close()
    conn.close()
    return jobs


def reset_all_jobs():
    """Reset all jobs in linkedin_jobs_raw for complete re-scraping"""
    conn = psycopg.connect('postgresql://postgres:postgres@localhost:5432/data_lake')
    cur = conn.cursor()
    
    # Reset success flag so all jobs will be re-scraped
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
    
    return updated_count


def scrape_job_directly(scraper_service, job_info):
    """Scrape a single job and update linkedin_jobs_raw directly"""
    url = job_info['url']
    raw_id = job_info['raw_id']
    link_id = job_info['link_id']
    
    print(f"   🌐 Scraping job {raw_id}: {url}")
    
    # Use the scraper's context to scrape the job
    with scraper_service.get_browser_context() as (context, page):
        try:
            result = scraper_service.scrape_single_job(link_id, url, context, page)
            
            if result['success']:
                # Update linkedin_jobs_raw with the new results
                update_job_in_raw_table(raw_id, result)
                print(f"   ✅ Job {raw_id} completed - extracted {sum(1 for field in [result.get('role_title'), result.get('company_name'), result.get('location'), result.get('posted_time'), result.get('description_text')] if field)}/5 core fields")
                return True
            else:
                # Update with failed result
                update_job_in_raw_table(raw_id, result)
                print(f"   ❌ Job {raw_id} failed: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            error_result = {
                'success': False,
                'job_id': link_id,
                'url': url,
                'error': str(e),
                'scraped_at': datetime.now(timezone.utc).isoformat()
            }
            update_job_in_raw_table(raw_id, error_result)
            print(f"   ❌ Job {raw_id} exception: {e}")
            return False


def update_job_in_raw_table(raw_id, result):
    """Update job result directly in linkedin_jobs_raw table"""
    conn = psycopg.connect('postgresql://postgres:postgres@localhost:5432/data_lake')
    cur = conn.cursor()
    
    # Prepare extracted_data JSONB
    extracted_data = {
        "role_title": result.get('role_title'),
        "company_name": result.get('company_name'),
        "location": result.get('location'),
        "posted_time": result.get('posted_time'),
        "description_text": result.get('description_text'),
        "key_responsibilities": result.get('key_responsibilities', []),
        "requirements": result.get('requirements', []),
        "status": result.get('status'),
        "scraper_version": result.get('scraper_version', 'linkedin-job-scraper-v2.0-updated'),
        "scraped_at": result.get('scraped_at'),
        "error": result.get('error') if not result.get('success') else None
    }
    
    # Update the existing row
    cur.execute("""
        UPDATE linkedin_jobs_raw 
        SET extracted_data = %s,
            scraped_at = %s,
            success = %s,
            raw_html_path = %s,
            screenshot_path = %s
        WHERE id = %s
    """, (
        json.dumps(extracted_data),
        datetime.now(timezone.utc),
        result.get('success', False),
        result.get('html_path'),
        result.get('screenshot_path'),
        raw_id
    ))
    
    conn.commit()
    cur.close()
    conn.close()


class DirectJobsRescraper:
    """Direct re-scraper for linkedin_jobs_raw table"""
    
    def __init__(self):
        # Set environment variables  
        os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/data_lake'
        os.environ['LINKEDIN_EMAIL'] = 'bhatiyash456@gmail.com'
        os.environ['LINKEDIN_PASSWORD'] = 'Bhati@4567'
        
        self.scraper = LinkedInJobScraperService()
    
    def add_context_manager_to_scraper(self):
        """Add a context manager method to the scraper service"""
        from contextlib import contextmanager
        from playwright.sync_api import sync_playwright
        import random
        
        @contextmanager
        def get_browser_context(self):
            """Get browser context for scraping"""
            chrome_profile_dir = self.config.get('chrome_options', {}).get('user_data_dir', './chrome_profile')
            
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=chrome_profile_dir,
                    headless=True,
                    viewport={"width": random.randint(1280, 1440), "height": random.randint(800, 950)},
                    user_agent=self.config.get('chrome_options', {}).get('user_agent',
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                    locale="en-US",
                    timezone_id="UTC",
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                
                page = context.new_page()
                
                # Check login status
                page.goto("https://www.linkedin.com", timeout=60000)
                page.wait_for_timeout(3000)
                
                if not self.check_login_status(page):
                    credentials = self.config.get('linkedin_credentials', {})
                    email = credentials.get('email') or os.environ.get('LINKEDIN_EMAIL')
                    password = credentials.get('password') or os.environ.get('LINKEDIN_PASSWORD')
                    
                    if not self.login_to_linkedin(page, email, password):
                        context.close()
                        raise Exception("LinkedIn login failed")
                
                try:
                    yield context, page
                finally:
                    context.close()
        
        # Bind the method to the scraper instance
        import types
        self.scraper.get_browser_context = types.MethodType(get_browser_context, self.scraper)
    
    def run_complete_rescrape(self):
        """Run complete re-scrape of all jobs in linkedin_jobs_raw"""
        
        # Add context manager to scraper
        self.add_context_manager_to_scraper()
        
        print("🚀 Starting complete re-scrape of all LinkedIn jobs...")
        print("=" * 60)
        
        # Get all jobs
        all_jobs = get_all_jobs_from_raw_table()
        print(f"Found {len(all_jobs)} jobs to process")
        
        # Show current status
        with_desc = sum(1 for job in all_jobs if job['desc_length'] > 100)
        without_desc = len(all_jobs) - with_desc
        print(f"Current status: {with_desc} with descriptions, {without_desc} without")
        print("-" * 60)
        
        # Reset all jobs for complete re-scraping
        reset_count = reset_all_jobs()
        print(f"Reset {reset_count} jobs for re-scraping")
        print("-" * 60)
        
        # Process each job
        successful = 0
        failed = 0
        
        for i, job in enumerate(all_jobs, 1):
            print(f"🔄 Processing job {i}/{len(all_jobs)}")
            
            try:
                if scrape_job_directly(self.scraper, job):
                    successful += 1
                else:
                    failed += 1
                    
                # Brief delay between jobs
                if i < len(all_jobs):
                    time.sleep(2)
                    
            except Exception as e:
                print(f"   ❌ Job {job['raw_id']} failed with exception: {e}")
                failed += 1
        
        # Final summary
        print("=" * 60)
        print("🎉 Complete re-scraping finished!")
        print(f"Total processed: {len(all_jobs)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/len(all_jobs)*100):.1f}%")
        
        # Check final status
        final_jobs = get_all_jobs_from_raw_table()
        final_with_desc = sum(1 for job in final_jobs if job['desc_length'] > 100 and job['current_success'])
        print(f"")
        print(f"Final status: {final_with_desc}/{len(final_jobs)} jobs with complete descriptions")
        
        return {
            'total': len(all_jobs),
            'successful': successful,
            'failed': failed,
            'final_with_descriptions': final_with_desc
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Direct re-scraper for linkedin_jobs_raw table")
    parser.add_argument("--stats-only", action="store_true", help="Show stats without running scraper")
    
    args = parser.parse_args()
    
    if args.stats_only:
        jobs = get_all_jobs_from_raw_table()
        with_desc = sum(1 for job in jobs if job['desc_length'] > 100 and job['current_success'])
        without_desc = len(jobs) - with_desc
        
        print("Current LinkedIn Jobs Raw Stats:")
        print(f"  Total jobs: {len(jobs)}")
        print(f"  With descriptions: {with_desc}")
        print(f"  Without descriptions: {without_desc}")
        
        # Show some examples
        print("\nSample jobs without descriptions:")
        no_desc_jobs = [job for job in jobs if job['desc_length'] <= 100][:5]
        for job in no_desc_jobs:
            print(f"  ID {job['raw_id']}: {job['url'][:80]}... (desc_len: {job['desc_length']})")
    else:
        rescraper = DirectJobsRescraper()
        rescraper.run_complete_rescrape()