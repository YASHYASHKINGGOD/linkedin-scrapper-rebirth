#!/usr/bin/env python3
"""
FOC Community Full Page Scraper with Effective Scrolling
Scrolls through the entire FOC Community page to capture all LinkedIn links
"""

import os
import csv
import json
import asyncio
from datetime import datetime
from typing import List, Dict
from playwright.async_api import async_playwright, Page, Browser
from src.extractor.notion.links import extract_linkedin_links_from_html

class FOCFullPageScraper:
    """Full page scraper for FOC Community with proper scrolling."""
    
    def __init__(self):
        self.foc_url = "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422"
        self.page_name = "FOC Community - Founder's Office Roles"
        
    async def setup_browser(self) -> Browser:
        """Setup browser for effective scrolling."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,  # Keep headless for speed
            args=[
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        return browser
    
    async def scroll_entire_page(self, page: Page) -> int:
        """Scroll through entire page to load all content."""
        print("   📜 Starting complete page scroll...")
        
        # Wait for initial page load
        await page.wait_for_load_state('domcontentloaded', timeout=45000)
        await asyncio.sleep(3)
        
        # Track scrolling progress
        scroll_count = 0
        prev_height = 0
        stable_count = 0
        
        # Get initial metrics
        current_height = await page.evaluate("document.body.scrollHeight")
        link_count = await page.evaluate('document.querySelectorAll("a[href*=\\"linkedin.com\\"]").length')
        
        print(f"   📊 Initial state: Height {current_height}, LinkedIn links {link_count}")
        
        while scroll_count < 30:  # Reasonable limit
            # Scroll down by viewport height
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1)
            
            # Additional scroll methods
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
            # Check for changes
            new_height = await page.evaluate("document.body.scrollHeight")
            new_link_count = await page.evaluate('document.querySelectorAll("a[href*=\\"linkedin.com\\"]").length')
            
            if new_height > current_height or new_link_count > link_count:
                print(f"   📈 Scroll {scroll_count + 1}: Height {new_height} (+{new_height - current_height}), Links {new_link_count} (+{new_link_count - link_count})")
                current_height = new_height
                link_count = new_link_count
                stable_count = 0
            else:
                stable_count += 1
                if stable_count >= 5:  # No changes for 5 attempts
                    print(f"   ✅ Page content stable after {scroll_count + 1} scrolls")
                    break
            
            scroll_count += 1
            
            # Brief pause every 10 scrolls
            if scroll_count % 10 == 0:
                print(f"   ⏸️  Brief pause at scroll {scroll_count}")
                await asyncio.sleep(2)
        
        # Final scroll to top to ensure all content is captured
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(2)
        
        # Get final count
        final_links = await page.evaluate('document.querySelectorAll("a[href*=\\"linkedin.com\\"]").length')
        print(f"   🏁 Final result: {final_links} LinkedIn links found after {scroll_count} scrolls")
        
        return final_links
    
    async def scrape_complete_foc_page(self) -> List[Dict]:
        """Scrape the complete FOC Community page with scrolling."""
        print("🚀 FOC COMMUNITY COMPLETE PAGE SCRAPER")
        print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Goal: Extract ALL LinkedIn links from FOC Community page")
        print(f"🔗 URL: {self.foc_url}")
        print("📜 Using systematic scrolling to capture complete content")
        print("=" * 70)
        
        browser = await self.setup_browser()
        
        try:
            page = await browser.new_page()
            
            # Set reasonable timeouts
            page.set_default_timeout(60000)
            
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("   🌐 Loading FOC Community page...")
            await page.goto(self.foc_url, timeout=60000)
            
            # Scroll through entire page
            total_links = await self.scroll_entire_page(page)
            
            print("   📄 Extracting complete page HTML...")
            html_content = await page.content()
            
            # Save complete HTML for debugging
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            debug_path = f"./storage/foc_complete_{timestamp}.html"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 Complete HTML saved: {debug_path}")
            
            # Extract all LinkedIn links
            all_links = extract_linkedin_links_from_html(
                html_content, 
                self.foc_url,
                limit=None  # Get everything
            )
            
            print(f"   🔗 Extracted {len(all_links)} LinkedIn links from HTML")
            
            # Add metadata to all links
            current_time = datetime.now().isoformat()
            for i, link in enumerate(all_links, 1):
                link.update({
                    'link_number': i,
                    'page_name': self.page_name,
                    'scraped_at': current_time,
                    'scraping_method': 'full_page_scroll',
                    'total_scrolls': total_links,
                    'source_page': 'FOC Community'
                })
            
            # Analyze link types
            posts = sum(1 for link in all_links if '/posts/' in link['url'])
            jobs = sum(1 for link in all_links if '/jobs/' in link['url'])
            profiles = sum(1 for link in all_links if '/in/' in link['url'])
            
            print(f"   📊 Link breakdown: {posts} posts, {jobs} jobs, {profiles} profiles")
            print(f"   ✅ Complete extraction successful!")
            
            return all_links
            
        except Exception as e:
            print(f"   ❌ Scraping error: {e}")
            return []
            
        finally:
            await browser.close()
    
    def save_complete_results(self, links: List[Dict]) -> str:
        """Save complete FOC results to CSV."""
        if not links:
            print("❌ No links to save")
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"./storage/foc_complete_links_{timestamp}.csv"
        
        # Comprehensive CSV columns
        fieldnames = [
            'link_number', 'url', 'anchor_text', 'row_context', 'source_page_url',
            'scraped_at', 'scraping_method', 'total_scrolls', 'source_page',
            'source', 'captured_at'
        ]
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(links)
        
        print(f"\n💾 FOC COMPLETE RESULTS SAVED:")
        print(f"   📄 File: {csv_filename}")
        print(f"   📊 Total FOC links: {len(links)}")
        
        # Detailed analysis
        link_types = {}
        domains = {}
        
        for link in links:
            url = link.get('url', '')
            
            # Categorize by link type
            if '/posts/' in url:
                link_types['LinkedIn Posts'] = link_types.get('LinkedIn Posts', 0) + 1
            elif '/jobs/view/' in url:
                link_types['LinkedIn Jobs'] = link_types.get('LinkedIn Jobs', 0) + 1
            elif '/in/' in url:
                link_types['LinkedIn Profiles'] = link_types.get('LinkedIn Profiles', 0) + 1
            else:
                link_types['Other LinkedIn'] = link_types.get('Other LinkedIn', 0) + 1
        
        print(f"\n📊 COMPLETE LINK TYPE BREAKDOWN:")
        for link_type, count in link_types.items():
            print(f"   • {link_type}: {count} links")
        
        # Show sample URLs for each type
        print(f"\n🔗 SAMPLE URLS BY TYPE:")
        samples_shown = {}
        for link in links[:15]:  # First 15 links
            url = link.get('url', '')
            if '/jobs/view/' in url and 'LinkedIn Jobs' not in samples_shown:
                print(f"   💼 Job: {url}")
                samples_shown['LinkedIn Jobs'] = True
            elif '/posts/' in url and 'LinkedIn Posts' not in samples_shown:
                print(f"   📝 Post: {url}")
                samples_shown['LinkedIn Posts'] = True
            elif '/in/' in url and 'LinkedIn Profiles' not in samples_shown:
                print(f"   👤 Profile: {url}")
                samples_shown['LinkedIn Profiles'] = True
        
        return csv_filename

async def main():
    """Main scraper execution."""
    os.makedirs("./storage", exist_ok=True)
    
    scraper = FOCFullPageScraper()
    complete_links = await scraper.scrape_complete_foc_page()
    
    if complete_links:
        csv_file = scraper.save_complete_results(complete_links)
        
        print(f"\n✅ COMPLETE SUCCESS!")
        print(f"   📊 Found {len(complete_links)} total LinkedIn links")
        print(f"   💾 Complete CSV: {csv_file}")
        print(f"   📜 Used full-page scrolling to capture everything")
        
        print(f"\n🎯 NEXT STEPS:")
        print(f"   1. Review the complete CSV for all FOC Community links")
        print(f"   2. Filter for August-specific content if needed")
        print(f"   3. Extract detailed job info (company, role, location)")
        
    else:
        print(f"\n❌ COMPLETE SCRAPING FAILED")
        print("   No links were extracted from FOC Community page")

if __name__ == "__main__":
    asyncio.run(main())