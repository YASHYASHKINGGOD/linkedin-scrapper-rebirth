#!/usr/bin/env python3
"""
September Comprehensive LinkedIn Scraper
Scrapes all 40 September URLs with detailed extraction for both jobs and social posts.

Features:
- Handles both job URLs (/jobs/view/) and social post URLs (/posts/)
- Uses database queue management for robust processing
- Comprehensive extraction with multiple selectors and fallbacks
- Production-ready with logging, error handling, and progress tracking
- Generates detailed CSV report with all scraped data
"""

import os
import sys
import time
import json
import logging
import csv
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

import psycopg
from playwright.sync_api import sync_playwright

# Database configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/data_lake"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./storage/september_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SeptemberComprehensiveScraper:
    """Comprehensive LinkedIn scraper for September URLs"""
    
    def __init__(self, database_url: str = DATABASE_URL, headless: bool = False):
        self.database_url = database_url
        self.headless = headless
        self.scraped_count = 0
        self.failed_count = 0
        self.results = []
        
        # Output paths
        self.output_dir = Path("./storage/september_scraping")
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = self.output_dir / f"september_comprehensive_results_{timestamp}.csv"
        self.html_dir = self.output_dir / "html"
        self.screenshots_dir = self.output_dir / "screenshots"
        self.html_dir.mkdir(exist_ok=True)
        self.screenshots_dir.mkdir(exist_ok=True)
        
        logger.info(f"🚀 September Comprehensive Scraper initialized")
        logger.info(f"   📊 Database: {self.database_url}")
        logger.info(f"   📁 Output CSV: {self.csv_path}")
        logger.info(f"   🕷️  Headless mode: {self.headless}")

    def get_september_urls(self) -> List[Dict[str, Any]]:
        """Get September URLs from the database"""
        with psycopg.connect(self.database_url) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, url, category, sheet_name, date_in_source
                FROM linkedin_links
                WHERE date_in_source LIKE '%Sep%' 
                   OR date_in_source LIKE '%September%'
                ORDER BY id
            """)
            
            urls = []
            for row in cursor.fetchall():
                urls.append({
                    'id': row[0],
                    'url': row[1],
                    'category': row[2] or 'unknown',
                    'sheet_name': row[3] or 'unknown',
                    'date_in_source': row[4] or 'unknown'
                })
            
            logger.info(f"📋 Found {len(urls)} September URLs in database")
            return urls

    def login_to_linkedin(self, page) -> bool:
        """Login to LinkedIn with credentials from config"""
        try:
            logger.info("🔐 Starting LinkedIn login...")
            
            # Try to load credentials from config.json
            config_path = "config.json"
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    creds = config.get("linkedin_credentials", {})
                    email = creds.get("email")
                    password = creds.get("password")
            else:
                # Fallback to environment variables
                email = os.environ.get("LINKEDIN_EMAIL")
                password = os.environ.get("LINKEDIN_PASSWORD")
            
            if not email or not password:
                logger.error("❌ LinkedIn credentials not found. Please set in config.json or environment variables.")
                return False
            
            page.goto("https://www.linkedin.com/login", timeout=60000)
            page.wait_for_timeout(2000)
            
            # Fill credentials
            page.fill("#username", email)
            page.wait_for_timeout(1000)
            page.fill("#password", password)
            page.wait_for_timeout(1000)
            
            # Submit login
            page.click("button[type='submit']")
            page.wait_for_timeout(5000)
            
            # Check login success
            current_url = page.url.lower()
            if any(pattern in current_url for pattern in ['feed', 'mynetwork', '/in/', 'messaging']):
                logger.info("✅ Login successful!")
                return True
            else:
                logger.error(f"❌ Login failed - current URL: {page.url}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Login failed: {e}")
            return False

    def extract_text_safe(self, page, selectors: List[str]) -> str:
        """Safely extract text using multiple selectors with fallbacks"""
        for selector in selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    text = element.inner_text().strip()
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def expand_content(self, page):
        """Try to expand truncated content by clicking see more buttons"""
        see_more_selectors = [
            "button[data-testid='expandable-text-button']",
            "button:has-text('See more')",
            "button:has-text('see more')",
            "button:has-text('… more')",
            "button.show-more-less-html__button--more",
            "button[aria-expanded='false']"
        ]
        
        for selector in see_more_selectors:
            try:
                button = page.query_selector(selector)
                if button and button.is_visible():
                    logger.debug(f"🔄 Expanding content with: {selector}")
                    button.click()
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

    def scrape_job_post(self, page, url: str) -> Dict[str, Any]:
        """Scrape LinkedIn job posting"""
        data = {
            'url': url,
            'type': 'job',
            'scraped_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Navigate to job page
            page.goto(url, timeout=60000)
            page.wait_for_timeout(3000)
            
            # Expand job description
            self.expand_content(page)
            
            # Job title
            data['title'] = self.extract_text_safe(page, [
                "h1.job-details-jobs-unified-top-card__job-title",
                "h1.jobs-unified-top-card__job-title",
                ".topcard__title",
                "h1"
            ])
            
            # Company name
            data['company'] = self.extract_text_safe(page, [
                ".job-details-jobs-unified-top-card__company-name a",
                ".jobs-unified-top-card__company-name a",
                ".topcard__org-name-link",
                "a[href*='/company/']"
            ])
            
            # Location
            data['location'] = self.extract_text_safe(page, [
                ".job-details-jobs-unified-top-card__bullet",
                ".jobs-unified-top-card__bullet",
                ".topcard__flavor--bullet"
            ])
            
            # Posted time
            data['posted_time'] = self.extract_text_safe(page, [
                ".job-details-jobs-unified-top-card__posted-date",
                ".jobs-unified-top-card__posted-date",
                ".posted-time-ago__text"
            ])
            
            # Job description
            desc_selectors = [
                "[data-testid='expandable-text-box']",
                ".jobs-box__html-content",
                "#job-details",
                ".jobs-description-content__text",
                ".jobs-description__content"
            ]
            data['description'] = self.extract_text_safe(page, desc_selectors)
            
            # Employment type
            data['employment_type'] = self.extract_text_safe(page, [
                "button:has-text('Full-time')",
                "button:has-text('Part-time')",
                "button:has-text('Contract')",
                "button:has-text('Internship')"
            ])
            
            # Experience level
            data['experience_level'] = self.extract_text_safe(page, [
                "*:has-text('Entry level')",
                "*:has-text('Mid-Senior level')",
                "*:has-text('Senior level')",
                "*:has-text('Executive')"
            ])
            
            # Salary information
            salary_selectors = [
                "*:has-text('₹')",
                "*:has-text('$')",
                "*:has-text('LPA')",
                "*:has-text('per year')",
                "*:has-text('per month')"
            ]
            data['salary_info'] = self.extract_text_safe(page, salary_selectors)
            
            # Applicant count
            data['applicant_count'] = self.extract_text_safe(page, [
                "*:has-text('applicants')",
                "*:has-text('applications')"
            ])
            
            # Company LinkedIn URL
            try:
                company_link = page.query_selector("a[href*='/company/']")
                if company_link:
                    href = company_link.get_attribute('href')
                    if href and href.startswith('/'):
                        data['company_linkedin_url'] = f"https://www.linkedin.com{href}"
                    else:
                        data['company_linkedin_url'] = href
            except Exception:
                data['company_linkedin_url'] = ""
            
            # Extract skills/requirements from description
            description_text = data.get('description', '').lower()
            skills_found = []
            common_skills = [
                'python', 'java', 'javascript', 'react', 'node.js', 'sql', 'aws', 'azure',
                'product management', 'data analysis', 'machine learning', 'ai', 'agile',
                'scrum', 'leadership', 'communication', 'project management', 'marketing'
            ]
            
            for skill in common_skills:
                if skill in description_text:
                    skills_found.append(skill)
            
            data['skills_mentioned'] = ', '.join(skills_found) if skills_found else ""
            
            logger.info(f"✅ Job scraped: {data.get('title', 'Unknown')} at {data.get('company', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"❌ Error scraping job {url}: {e}")
            data['error'] = str(e)
        
        return data

    def scrape_social_post(self, page, url: str) -> Dict[str, Any]:
        """Scrape LinkedIn social post"""
        data = {
            'url': url,
            'type': 'post',
            'scraped_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Navigate to post page
            page.goto(url, timeout=60000)
            page.wait_for_timeout(3000)
            
            # Expand post content
            self.expand_content(page)
            
            # Post author
            data['author'] = self.extract_text_safe(page, [
                ".feed-shared-actor__name",
                "a[href*='/in/'] span[aria-hidden='false']",
                ".update-components-actor__name",
                "a[data-test-id='actor-link']"
            ])
            
            # Author title/description
            data['author_title'] = self.extract_text_safe(page, [
                ".feed-shared-actor__description",
                ".update-components-actor__description",
                "p.text-color-text-low-emphasis"
            ])
            
            # Post content
            content_selectors = [
                "[data-test-id='main-feed-activity-card__commentary']",
                ".feed-shared-text",
                ".update-components-text",
                ".attributed-text-segment-list__content"
            ]
            data['content'] = self.extract_text_safe(page, content_selectors)
            
            # Posted time
            data['posted_time'] = self.extract_text_safe(page, [
                "time",
                ".feed-shared-actor__sub-description time",
                ".update-components-actor__sub-description time"
            ])
            
            # Engagement metrics
            try:
                # Likes
                like_selectors = [
                    "button[aria-label*='reaction']",
                    "button:has-text('Like')",
                    ".social-counts-reactions__count-value"
                ]
                data['likes'] = self.extract_text_safe(page, like_selectors)
                
                # Comments
                comment_selectors = [
                    "button[aria-label*='comment']",
                    "button:has-text('Comment')",
                    ".social-counts-comments__count-value"
                ]
                data['comments_count'] = self.extract_text_safe(page, comment_selectors)
                
                # Shares/Reposts
                share_selectors = [
                    "button[aria-label*='repost']",
                    "button:has-text('Repost')",
                    ".social-counts-shares__count-value"
                ]
                data['shares'] = self.extract_text_safe(page, share_selectors)
                
            except Exception as e:
                logger.debug(f"Could not extract engagement metrics: {e}")
                data['likes'] = ""
                data['comments_count'] = ""
                data['shares'] = ""
            
            # Extract hiring keywords from post content
            content_text = data.get('content', '').lower()
            hiring_keywords = [
                'hiring', 'job opening', 'we are hiring', "we're hiring", 'position available',
                'join our team', 'now hiring', 'career opportunity', 'job opportunity',
                'product manager', 'software engineer', 'data scientist', 'marketing manager'
            ]
            
            found_keywords = []
            for keyword in hiring_keywords:
                if keyword in content_text:
                    found_keywords.append(keyword)
            
            data['hiring_keywords'] = ', '.join(found_keywords) if found_keywords else ""
            data['is_hiring_post'] = 'hiring' in content_text
            
            # Try to extract company mentioned in post
            if 'hiring' in content_text:
                # Look for company patterns in the post content
                import re
                company_patterns = [
                    r'at\s+([A-Z][a-zA-Z\s&]+?)[\s,\.]',
                    r'join\s+([A-Z][a-zA-Z\s&]+?)[\s,\.]',
                    r'(@[a-zA-Z\s&]+?)[\s,\.]'
                ]
                
                for pattern in company_patterns:
                    matches = re.findall(pattern, data.get('content', ''))
                    if matches:
                        data['company_mentioned'] = matches[0].strip()
                        break
                else:
                    data['company_mentioned'] = ""
            else:
                data['company_mentioned'] = ""
            
            logger.info(f"✅ Post scraped: {data.get('author', 'Unknown')} - {len(data.get('content', ''))} chars")
            
        except Exception as e:
            logger.error(f"❌ Error scraping post {url}: {e}")
            data['error'] = str(e)
        
        return data

    def save_artifacts(self, page, url: str, link_id: int):
        """Save HTML and screenshot"""
        try:
            # Save HTML
            html_path = self.html_dir / f"{link_id}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page.content())
            
            # Save screenshot
            screenshot_path = self.screenshots_dir / f"{link_id}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            
            return str(html_path), str(screenshot_path)
        except Exception as e:
            logger.warning(f"⚠️ Could not save artifacts for {url}: {e}")
            return "", ""

    def scrape_url(self, page, url_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape a single URL (job or post)"""
        url = url_data['url']
        link_id = url_data['id']
        category = url_data['category']
        
        logger.info(f"🕷️ Scraping [{category}] {url}")
        
        try:
            # Determine URL type and scrape accordingly
            if '/jobs/view/' in url or category == 'jobs':
                result = self.scrape_job_post(page, url)
            elif '/posts/' in url or category == 'posts':
                result = self.scrape_social_post(page, url)
            else:
                # Try to determine from URL structure
                if 'jobs' in url:
                    result = self.scrape_job_post(page, url)
                else:
                    result = self.scrape_social_post(page, url)
            
            # Add metadata
            result.update({
                'link_id': link_id,
                'sheet_name': url_data['sheet_name'],
                'date_in_source': url_data['date_in_source'],
                'success': True
            })
            
            # Save artifacts
            html_path, screenshot_path = self.save_artifacts(page, url, link_id)
            result.update({
                'html_path': html_path,
                'screenshot_path': screenshot_path
            })
            
            self.scraped_count += 1
            
        except Exception as e:
            logger.error(f"❌ Failed to scrape {url}: {e}")
            result = {
                'url': url,
                'link_id': link_id,
                'success': False,
                'error': str(e),
                'scraped_at': datetime.now(timezone.utc).isoformat()
            }
            self.failed_count += 1
        
        # Add delay between scrapes
        time.sleep(2)
        return result

    def save_results_to_csv(self):
        """Save all results to CSV file"""
        if not self.results:
            logger.warning("⚠️ No results to save")
            return
        
        # Get all possible field names
        all_fields = set()
        for result in self.results:
            all_fields.update(result.keys())
        
        # Sort fields for better organization
        core_fields = ['link_id', 'url', 'type', 'success', 'sheet_name', 'date_in_source']
        job_fields = ['title', 'company', 'location', 'posted_time', 'description', 'employment_type', 
                     'experience_level', 'salary_info', 'applicant_count', 'company_linkedin_url', 
                     'skills_mentioned']
        post_fields = ['author', 'author_title', 'content', 'posted_time', 'likes', 'comments_count', 
                      'shares', 'hiring_keywords', 'is_hiring_post', 'company_mentioned']
        meta_fields = ['html_path', 'screenshot_path', 'scraped_at', 'error']
        
        # Organize field order
        ordered_fields = []
        for field_group in [core_fields, job_fields, post_fields, meta_fields]:
            for field in field_group:
                if field in all_fields and field not in ordered_fields:
                    ordered_fields.append(field)
        
        # Add any remaining fields
        for field in sorted(all_fields):
            if field not in ordered_fields:
                ordered_fields.append(field)
        
        # Write CSV
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=ordered_fields)
            writer.writeheader()
            writer.writerows(self.results)
        
        logger.info(f"📊 Results saved to: {self.csv_path}")

    def run(self):
        """Run the comprehensive scraping process"""
        logger.info("🚀 Starting September comprehensive scraping...")
        
        # Get URLs from database
        urls = self.get_september_urls()
        if not urls:
            logger.error("❌ No September URLs found in database")
            return
        
        logger.info(f"📋 Processing {len(urls)} URLs...")
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            try:
                # Login to LinkedIn
                if not self.login_to_linkedin(page):
                    logger.error("❌ Failed to login to LinkedIn")
                    return
                
                # Process each URL
                for i, url_data in enumerate(urls, 1):
                    logger.info(f"\n📍 Progress: {i}/{len(urls)}")
                    result = self.scrape_url(page, url_data)
                    self.results.append(result)
                    
                    # Save intermediate results every 10 scrapes
                    if i % 10 == 0:
                        self.save_results_to_csv()
                        logger.info(f"💾 Intermediate save completed at {i}/{len(urls)}")
                
                # Final save
                self.save_results_to_csv()
                
            finally:
                browser.close()
        
        # Print final statistics
        self.print_final_stats()

    def print_final_stats(self):
        """Print comprehensive final statistics"""
        total_urls = len(self.results)
        successful = sum(1 for r in self.results if r.get('success', False))
        failed = total_urls - successful
        
        # Count by type
        job_count = sum(1 for r in self.results if r.get('type') == 'job')
        post_count = sum(1 for r in self.results if r.get('type') == 'post')
        
        # Count hiring posts
        hiring_posts = sum(1 for r in self.results if r.get('is_hiring_post', False))
        
        logger.info(f"\n🎉 SEPTEMBER SCRAPING COMPLETED!")
        logger.info(f"=" * 60)
        logger.info(f"📊 Total URLs processed: {total_urls}")
        logger.info(f"✅ Successful: {successful}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"📈 Success rate: {(successful/total_urls)*100:.1f}%" if total_urls > 0 else "0%")
        logger.info(f"")
        logger.info(f"📋 Breakdown by type:")
        logger.info(f"   💼 Jobs: {job_count}")
        logger.info(f"   📝 Posts: {post_count}")
        logger.info(f"   🎯 Hiring posts: {hiring_posts}")
        logger.info(f"")
        logger.info(f"📁 Output files:")
        logger.info(f"   📊 CSV: {self.csv_path}")
        logger.info(f"   📄 HTML: {self.html_dir}")
        logger.info(f"   📸 Screenshots: {self.screenshots_dir}")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="September Comprehensive LinkedIn Scraper")
    parser.add_argument("--database-url", type=str, help="Database URL")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    
    args = parser.parse_args()
    
    database_url = args.database_url or DATABASE_URL
    
    scraper = SeptemberComprehensiveScraper(
        database_url=database_url,
        headless=args.headless
    )
    
    scraper.run()


if __name__ == "__main__":
    main()