#!/usr/bin/env python3
"""
Live Notion Scraper - Extract fresh LinkedIn links from current Notion pages.
Addresses data freshness concerns by scraping live pages instead of cached snapshots.
"""

import os
import csv
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
from src.extractor.notion.links import extract_linkedin_links_from_html

class LiveNotionScraper:
    """Live scraper for Notion pages with enhanced JavaScript handling."""
    
    def __init__(self):
        self.pages_info = [
            {
                "id": "diligent_actor_internship",
                "url": "https://diligent-actor-263.notion.site/13b8c7fca68e804aa0c3ca803aa07a3f?v=13b8c7fca68e817abca9000c95bbc26f",
                "name": "Diligent Actor - Internship & Analytics Jobs"
            },
            {
                "id": "diligent_actor_experienced", 
                "url": "https://diligent-actor-263.notion.site/15a8c7fca68e80d7b612e1ba7379dd8a?v=15a8c7fca68e8154b0c0000c7a9241c9",
                "name": "Diligent Actor - Experienced Analytics & Data Science"
            },
            {
                "id": "foc_community_founders",
                "url": "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422", 
                "name": "FOC Community - Founder's Office Roles"
            }
        ]
        
    async def setup_browser(self) -> Browser:
        """Setup Playwright browser with stealth configuration."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        return browser
    
    async def wait_for_content_load(self, page: Page, page_info: Dict) -> bool:
        """Wait for Notion page content to fully load."""
        try:
            print(f"   ⏳ Waiting for page content to load...")
            
            # Wait for initial page load
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            # Wait for Notion-specific elements
            await page.wait_for_selector('div[role="application"]', timeout=20000)
            
            # Additional wait for dynamic content
            await asyncio.sleep(3)
            
            # Check if we have actual content (not just loading skeleton)
            content_selectors = [
                'a[href*="linkedin.com"]',  # LinkedIn links
                'div[data-block-id]',       # Notion blocks
                'table',                     # Database view
                '.notion-table-view'        # Table view specific
            ]
            
            for selector in content_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        print(f"   ✅ Found content: {selector}")
                        return True
                except:
                    continue
                    
            print(f"   ⚠️  Content selectors not found, proceeding anyway...")
            return True
            
        except Exception as e:
            print(f"   ❌ Timeout waiting for content: {e}")
            return False
    
    async def scrape_page(self, browser: Browser, page_info: Dict) -> List[Dict]:
        """Scrape a single Notion page for LinkedIn links."""
        print(f"\n🔄 Scraping: {page_info['name']}")
        print(f"   🔗 URL: {page_info['url']}")
        
        page = await browser.new_page()
        
        # Set user agent and viewport
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        try:
            # Navigate to page
            print(f"   📍 Navigating to page...")
            await page.goto(page_info['url'], timeout=30000, wait_until='domcontentloaded')
            
            # Wait for content to load
            content_loaded = await self.wait_for_content_load(page, page_info)
            
            if not content_loaded:
                print(f"   ⚠️  Content may not be fully loaded, extracting anyway...")
            
            # Get page HTML
            html_content = await page.content()
            
            # Save debug HTML for inspection
            debug_path = f"./storage/live_debug_{page_info['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 Debug HTML saved: {debug_path}")
            
            # Extract LinkedIn links
            links = extract_linkedin_links_from_html(
                html_content, 
                page_info['url'],
                limit=10
            )
            
            # Add metadata
            current_time = datetime.now().isoformat()
            for i, link in enumerate(links, 1):
                link.update({
                    'page_id': page_info['id'],
                    'page_name': page_info['name'],
                    'link_number': i,
                    'scraped_at': current_time,
                    'scraping_method': 'live_playwright',
                    'data_freshness': 'current',
                    'extraction_source': 'live_page'
                })
            
            print(f"   ✅ Extracted {len(links)} LinkedIn links")
            if links:
                print(f"   🔗 Sample: {links[0]['url']}")
            
            return links
            
        except Exception as e:
            print(f"   ❌ Error scraping page: {e}")
            return []
            
        finally:
            await page.close()
    
    async def scrape_all_pages(self) -> List[Dict]:
        """Scrape all Notion pages for LinkedIn links."""
        print("🚀 LIVE NOTION SCRAPER - FRESH DATA EXTRACTION")
        print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Target: First 10 fresh links from each of {len(self.pages_info)} pages")
        print("=" * 70)
        
        browser = await self.setup_browser()
        all_links = []
        
        try:
            for page_info in self.pages_info:
                links = await self.scrape_page(browser, page_info)
                all_links.extend(links)
                
                # Small delay between pages
                await asyncio.sleep(2)
                
        finally:
            await browser.close()
        
        return all_links
    
    def save_fresh_results(self, links: List[Dict]) -> Optional[str]:
        """Save fresh results to CSV with current timestamp."""
        if not links:
            print("❌ No fresh links to save")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"./storage/notion_links_live_{timestamp}.csv"
        
        # Define comprehensive CSV columns
        fieldnames = [
            'page_id', 'page_name', 'link_number', 'url', 
            'anchor_text', 'row_context', 'source_page_url',
            'scraped_at', 'scraping_method', 'data_freshness', 
            'extraction_source', 'source', 'captured_at'
        ]
        
        # Save to CSV
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(links)
        
        print(f"\n💾 FRESH RESULTS SAVED:")
        print(f"   📄 File: {csv_filename}")
        print(f"   📊 Total links: {len(links)}")
        print(f"   🔄 Data freshness: CURRENT (just scraped)")
        
        # Breakdown by page
        page_counts = {}
        for link in links:
            page = f"{link['page_name'][:40]}..."
            page_counts[page] = page_counts.get(page, 0) + 1
        
        print(f"\n📈 BREAKDOWN BY PAGE:")
        for page, count in page_counts.items():
            print(f"   • {page}: {count} links")
        
        return csv_filename

async def main():
    """Main function."""
    # Ensure storage directory exists
    os.makedirs("./storage", exist_ok=True)
    
    # Create and run scraper
    scraper = LiveNotionScraper()
    links = await scraper.scrape_all_pages()
    
    if links:
        csv_file = scraper.save_fresh_results(links)
        
        print(f"\n✅ SUCCESS!")
        print(f"   📊 Extracted {len(links)} fresh LinkedIn links")
        print(f"   💾 Saved to: {csv_file}")
        print(f"   🔄 Data is CURRENT (just scraped)")
        
        print(f"\n🔗 SAMPLE FRESH LINKS:")
        for i, link in enumerate(links[:5], 1):
            print(f"   {i}. {link['url']}")
            print(f"      From: {link['page_name']}")
        
        # Analyze link types
        posts = sum(1 for link in links if '/posts/' in link['url'])
        jobs = sum(1 for link in links if '/jobs/' in link['url']) 
        profiles = sum(1 for link in links if '/in/' in link['url'])
        
        print(f"\n📊 FRESH DATA ANALYSIS:")
        print(f"   📝 LinkedIn Posts: {posts}")
        print(f"   💼 Job Listings: {jobs}")
        print(f"   👤 Profiles: {profiles}")
        
    else:
        print(f"\n❌ FAILED!")
        print("   No fresh links were extracted")

if __name__ == "__main__":
    asyncio.run(main())