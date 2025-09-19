#!/usr/bin/env python3
"""
Unified LinkedIn Post Scraper

Consolidates existing LinkedIn scraping logic into a clean, reusable interface.
Handles both individual posts and feeds with robust error handling and storage.

Usage:
    from apps.scraper_playwright.posts.scraper import LinkedInPostScraper
    
    scraper = LinkedInPostScraper()
    result = await scraper.scrape_post("https://linkedin.com/posts/...")
"""

import os
import json
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict
import re
import hashlib

# Playwright imports (with fallback for development)
try:
    from playwright.async_api import async_playwright, Page, Browser, TimeoutError
except ImportError:
    print("⚠️  Playwright not installed. Install with: pip install playwright")
    async_playwright = None
    Page = object
    Browser = object
    TimeoutError = Exception

# BeautifulSoup for HTML parsing
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("⚠️  BeautifulSoup not installed. Install with: pip install beautifulsoup4")
    BeautifulSoup = None


@dataclass
class ScrapedPost:
    """Data structure for a scraped LinkedIn post"""
    success: bool
    url: str
    canonical_url: Optional[str] = None
    
    # Content data
    author_name: Optional[str] = None
    author_profile_url: Optional[str] = None
    post_text: Optional[str] = None
    post_date: Optional[str] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    repost_count: Optional[int] = None
    
    # Technical metadata
    scrape_timestamp: Optional[str] = None
    html_length: Optional[int] = None
    screenshot_taken: bool = False
    
    # Storage paths (relative to storage root)
    raw_html_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    metadata_json_path: Optional[str] = None
    
    # Error information
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class LinkedInPostScraper:
    """Unified LinkedIn post scraper with robust error handling"""
    
    def __init__(self, storage_base: str = "./storage", headless: bool = True):
        self.storage_base = Path(storage_base)
        self.posts_storage = self.storage_base / "posts"
        self.posts_storage.mkdir(parents=True, exist_ok=True)
        
        self.headless = headless
        self.default_timeout = 30000  # 30 seconds
        self.scroll_timeout = 5000    # 5 seconds for scrolling
        
        # User agent for requests
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    
    def _generate_file_id(self, url: str, link_id: Optional[int] = None) -> str:
        """Generate unique file ID for storage"""
        if link_id:
            return f"link_{link_id}"
        else:
            # Use URL hash as fallback
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            return f"url_{url_hash}"
    
    def _get_storage_paths(self, link_id: Optional[int], url: str) -> Dict[str, Path]:
        """Get organized storage paths for scraped content"""
        file_id = self._generate_file_id(url, link_id)
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        
        base_dir = self.posts_storage / today / file_id
        base_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "html": base_dir / "content.html",
            "screenshot": base_dir / "screenshot.png", 
            "metadata": base_dir / "metadata.json",
            "base_dir": base_dir
        }
    
    async def _setup_browser(self) -> Browser:
        """Setup Playwright browser instance"""
        if not async_playwright:
            raise RuntimeError("Playwright not available")
        
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows'
            ]
        )
        return browser
    
    async def _setup_page(self, browser: Browser) -> Page:
        """Setup page with proper configuration"""
        page = await browser.new_page()
        page.set_default_timeout(self.default_timeout)
        
        await page.set_extra_http_headers({
            'User-Agent': self.user_agent
        })
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        return page
    
    def _extract_canonical_url(self, url: str) -> str:
        """Extract canonical LinkedIn post URL"""
        # Remove tracking parameters and normalize
        canonical = re.sub(r'[?&]utm_[^&]*', '', url)
        canonical = re.sub(r'[?&]trackingId=[^&]*', '', canonical)
        canonical = re.sub(r'[?&]lipi=[^&]*', '', canonical)
        canonical = canonical.rstrip('?&')
        return canonical
    
    async def _extract_post_data(self, page: Page, html_content: str) -> Dict[str, Any]:
        """Extract structured data from LinkedIn post page"""
        extracted = {}
        
        try:
            if not BeautifulSoup:
                print("⚠️  BeautifulSoup not available for content extraction")
                return extracted
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract author information
            author_elements = soup.select('[data-test-id*="author"], .feed-shared-actor__name')
            if author_elements:
                extracted['author_name'] = author_elements[0].get_text(strip=True)
            
            # Try to get author profile link
            author_links = soup.select('a[href*="/in/"]')
            if author_links:
                extracted['author_profile_url'] = author_links[0].get('href')
            
            # Extract post text content
            post_text_selectors = [
                '[data-test-id*="post-text"]',
                '.feed-shared-text',
                '.feed-shared-update-v2__description',
                '.break-words'
            ]
            
            for selector in post_text_selectors:
                elements = soup.select(selector)
                if elements:
                    extracted['post_text'] = elements[0].get_text(strip=True)
                    break
            
            # Extract engagement metrics (like, comment, repost counts)
            # These are often in buttons or spans with specific patterns
            reaction_elements = soup.find_all(text=re.compile(r'\\d+\\s+(like|comment|repost)', re.I))
            for element in reaction_elements:
                text = element.strip().lower()
                if 'like' in text:
                    likes_match = re.search(r'(\\d+)', text)
                    if likes_match:
                        extracted['like_count'] = int(likes_match.group(1))
                elif 'comment' in text:
                    comments_match = re.search(r'(\\d+)', text)
                    if comments_match:
                        extracted['comment_count'] = int(comments_match.group(1))
                elif 'repost' in text:
                    reposts_match = re.search(r'(\\d+)', text)
                    if reposts_match:
                        extracted['repost_count'] = int(reposts_match.group(1))
            
            # Try to extract post date
            time_elements = soup.select('time, [data-test-id*="time"], .feed-shared-actor__sub-description')
            if time_elements:
                for elem in time_elements:
                    datetime_attr = elem.get('datetime')
                    if datetime_attr:
                        extracted['post_date'] = datetime_attr
                        break
                    # Fallback to text content
                    time_text = elem.get_text(strip=True)
                    if any(word in time_text.lower() for word in ['ago', 'hour', 'day', 'week', 'month']):
                        extracted['post_date'] = time_text
                        break
            
        except Exception as e:
            print(f"   ⚠️  Error extracting post data: {e}")
        
        return extracted
    
    async def _scroll_and_load_content(self, page: Page) -> None:
        """Scroll page to load dynamic content"""
        try:
            # Wait for initial load
            await page.wait_for_load_state('domcontentloaded', timeout=self.default_timeout)
            await asyncio.sleep(2)
            
            # Scroll down to trigger lazy loading
            for i in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                
                # Try to click "See more" or expand buttons
                try:
                    see_more_buttons = await page.query_selector_all(
                        'button[aria-label*="more"], .feed-shared-text__see-more, [data-test-id*="see-more"]'
                    )
                    for button in see_more_buttons:
                        if await button.is_visible():
                            await button.click()
                            await asyncio.sleep(1)
                            break
                except Exception:
                    pass  # Continue if buttons not found or clickable
            
            # Scroll back up
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"   ⚠️  Error during scrolling: {e}")
    
    async def scrape_post(
        self, 
        url: str, 
        link_id: Optional[int] = None,
        trace_id: Optional[str] = None
    ) -> ScrapedPost:
        """
        Scrape a single LinkedIn post
        
        Args:
            url: LinkedIn post URL
            link_id: Optional database link ID
            trace_id: Optional trace ID for request correlation
            
        Returns:
            ScrapedPost with results and metadata
        """
        scrape_start = datetime.now(timezone.utc)
        trace_id = trace_id or str(uuid.uuid4())[:8]
        
        print(f"🕷️  [trace:{trace_id}] Scraping LinkedIn post: {url[:60]}...")
        
        result = ScrapedPost(
            success=False,
            url=url,
            canonical_url=self._extract_canonical_url(url),
            scrape_timestamp=scrape_start.isoformat()
        )
        
        browser = None
        try:
            # Get storage paths
            storage_paths = self._get_storage_paths(link_id, url)
            
            # Setup browser
            browser = await self._setup_browser()
            page = await self._setup_page(browser)
            
            print(f"   🌐 [trace:{trace_id}] Navigating to page...")
            await page.goto(url, timeout=self.default_timeout, wait_until='domcontentloaded')
            
            # Handle potential login walls or redirects
            current_url = page.url
            if 'linkedin.com/login' in current_url or 'linkedin.com/checkpoint' in current_url:
                result.error_message = "LinkedIn login wall encountered"
                result.error_type = "access_denied"
                print(f"   ❌ [trace:{trace_id}] Login wall detected")
                return result
            
            # Scroll and load content
            print(f"   📜 [trace:{trace_id}] Loading dynamic content...")
            await self._scroll_and_load_content(page)
            
            # Get page content
            html_content = await page.content()
            result.html_length = len(html_content)
            
            # Save HTML content
            with open(storage_paths["html"], 'w', encoding='utf-8') as f:
                f.write(html_content)
            result.raw_html_path = str(storage_paths["html"].relative_to(self.storage_base))
            
            # Take screenshot
            print(f"   📸 [trace:{trace_id}] Taking screenshot...")
            await page.screenshot(path=storage_paths["screenshot"], full_page=True)
            result.screenshot_path = str(storage_paths["screenshot"].relative_to(self.storage_base))
            result.screenshot_taken = True
            
            # Extract structured data
            print(f"   🔍 [trace:{trace_id}] Extracting post data...")
            extracted_data = await self._extract_post_data(page, html_content)
            
            # Update result with extracted data
            result.author_name = extracted_data.get('author_name')
            result.author_profile_url = extracted_data.get('author_profile_url')
            result.post_text = extracted_data.get('post_text')
            result.post_date = extracted_data.get('post_date')
            result.like_count = extracted_data.get('like_count')
            result.comment_count = extracted_data.get('comment_count')
            result.repost_count = extracted_data.get('repost_count')
            
            # Save metadata JSON
            metadata = result.to_dict()
            metadata['trace_id'] = trace_id
            metadata['scraping_duration_seconds'] = (
                datetime.now(timezone.utc) - scrape_start
            ).total_seconds()
            
            with open(storage_paths["metadata"], 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            result.metadata_json_path = str(storage_paths["metadata"].relative_to(self.storage_base))
            
            # Mark as successful
            result.success = True
            print(f"   ✅ [trace:{trace_id}] Successfully scraped post")
            
        except TimeoutError as e:
            result.error_message = f"Timeout while loading page: {e}"
            result.error_type = "timeout"
            print(f"   ❌ [trace:{trace_id}] Timeout error: {e}")
            
        except Exception as e:
            result.error_message = f"Scraping failed: {e}"
            result.error_type = "scraping_error"
            print(f"   ❌ [trace:{trace_id}] Scraping error: {e}")
            
        finally:
            if browser:
                await browser.close()
        
        return result
    
    async def scrape_multiple_posts(
        self, 
        urls: List[str], 
        concurrent_limit: int = 3
    ) -> List[ScrapedPost]:
        """
        Scrape multiple LinkedIn posts with concurrency control
        
        Args:
            urls: List of LinkedIn post URLs
            concurrent_limit: Maximum concurrent scrapers
            
        Returns:
            List of ScrapedPost results
        """
        print(f"🕷️  Scraping {len(urls)} posts (concurrent_limit={concurrent_limit})")
        
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def scrape_with_semaphore(url: str) -> ScrapedPost:
            async with semaphore:
                return await self.scrape_post(url)
        
        results = await asyncio.gather(
            *[scrape_with_semaphore(url) for url in urls],
            return_exceptions=True
        )
        
        # Handle any exceptions in results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ScrapedPost(
                    success=False,
                    url=urls[i],
                    error_message=str(result),
                    error_type="exception",
                    scrape_timestamp=datetime.now(timezone.utc).isoformat()
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        
        success_count = sum(1 for r in final_results if r.success)
        print(f"   ✅ Successfully scraped {success_count}/{len(urls)} posts")
        
        return final_results


async def main():
    """CLI entry point for testing the scraper"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LinkedIn Post Scraper")
    parser.add_argument("urls", nargs="+", help="LinkedIn post URLs to scrape")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode")
    parser.add_argument("--storage", type=str, default="./storage", help="Storage base directory")
    
    args = parser.parse_args()
    
    scraper = LinkedInPostScraper(storage_base=args.storage, headless=args.headless)
    
    if len(args.urls) == 1:
        result = await scraper.scrape_post(args.urls[0])
        print("\\n📊 Scraping Result:")
        print(json.dumps(result.to_dict(), indent=2))
    else:
        results = await scraper.scrape_multiple_posts(args.urls)
        print("\\n📊 Scraping Results:")
        for i, result in enumerate(results):
            print(f"\\n--- Post {i+1} ---")
            print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
