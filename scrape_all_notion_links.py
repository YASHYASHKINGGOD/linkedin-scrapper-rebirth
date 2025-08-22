#!/usr/bin/env python3
"""
Scrape ALL LinkedIn links from all three Notion pages into a single CSV file.
No limits - extracts every LinkedIn link found on each page.
"""

import os
import csv
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
from src.extractor.notion.links import extract_linkedin_links_from_html

class AllLinksNotionScraper:
    """Scraper to extract ALL LinkedIn links from Notion pages."""
    
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
        """Setup Playwright browser."""
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
    
    async def wait_for_content_load(self, page: Page) -> bool:
        """Wait for Notion page content to fully load."""
        try:
            print(f"   ⏳ Loading page content...")
            await page.wait_for_load_state('networkidle', timeout=30000)
            await page.wait_for_selector('div[role="application"]', timeout=20000)
            await asyncio.sleep(3)
            return True
        except Exception as e:
            print(f"   ⚠️  Timeout: {e}")
            return False
    
    async def scrape_page_all_links(self, browser: Browser, page_info: Dict, page_number: int) -> List[Dict]:
        """Scrape ALL LinkedIn links from a single Notion page."""
        print(f"\n📄 Page {page_number}/3: {page_info['name']}")
        print(f"   🔗 URL: {page_info['url']}")
        
        page = await browser.new_page()
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        try:
            await page.goto(page_info['url'], timeout=30000, wait_until='domcontentloaded')
            await self.wait_for_content_load(page)
            
            html_content = await page.content()
            
            # Extract ALL LinkedIn links (no limit)
            links = extract_linkedin_links_from_html(
                html_content, 
                page_info['url'],
                limit=None  # Extract ALL links
            )
            
            # Add metadata to each link
            current_time = datetime.now().isoformat()
            for i, link in enumerate(links, 1):
                link.update({
                    'page_number': page_number,
                    'page_id': page_info['id'],
                    'page_name': page_info['name'],
                    'link_number': i,
                    'scraped_at': current_time,
                    'scraping_method': 'live_playwright_all',
                    'data_freshness': 'current'
                })
            
            print(f"   ✅ Extracted {len(links)} LinkedIn links")
            if links:
                # Show breakdown by link type
                posts = sum(1 for link in links if '/posts/' in link['url'])
                jobs = sum(1 for link in links if '/jobs/' in link['url'])
                profiles = sum(1 for link in links if '/in/' in link['url'])
                print(f"   📊 Posts: {posts}, Jobs: {jobs}, Profiles: {profiles}")
            
            return links
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
            
        finally:
            await page.close()
    
    async def scrape_all_pages(self) -> List[Dict]:
        """Scrape ALL LinkedIn links from all three Notion pages."""
        print("🚀 SCRAPING ALL LINKEDIN LINKS FROM ALL NOTION PAGES")
        print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Target: ALL LinkedIn links from {len(self.pages_info)} pages")
        print("=" * 70)
        
        browser = await self.setup_browser()
        all_links = []
        
        try:
            for i, page_info in enumerate(self.pages_info, 1):
                links = await self.scrape_page_all_links(browser, page_info, i)
                all_links.extend(links)
                await asyncio.sleep(2)  # Delay between pages
                
        finally:
            await browser.close()
        
        return all_links
    
    def save_all_links_csv(self, links: List[Dict]) -> Optional[str]:
        """Save all links to single CSV file."""
        if not links:
            print("❌ No links to save")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"./storage/all_notion_linkedin_links_{timestamp}.csv"
        
        # CSV columns
        fieldnames = [
            'page_number', 'page_id', 'page_name', 'link_number', 'url', 
            'anchor_text', 'row_context', 'source_page_url',
            'scraped_at', 'scraping_method', 'data_freshness', 
            'source', 'captured_at'
        ]
        
        # Save to CSV
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(links)
        
        print(f"\n💾 ALL LINKS SAVED TO SINGLE CSV:")
        print(f"   📄 File: {csv_filename}")
        print(f"   📊 Total links: {len(links)}")
        
        # Breakdown by page
        page_counts = {}
        for link in links:
            page_key = f"Page {link['page_number']}: {link['page_name'][:35]}..."
            page_counts[page_key] = page_counts.get(page_key, 0) + 1
        
        print(f"\n📈 BREAKDOWN BY PAGE:")
        for page, count in page_counts.items():
            print(f"   • {page}: {count} links")
        
        # Breakdown by link type across all pages
        all_posts = sum(1 for link in links if '/posts/' in link['url'])
        all_jobs = sum(1 for link in links if '/jobs/' in link['url'])
        all_profiles = sum(1 for link in links if '/in/' in link['url'])
        
        print(f"\n📊 TOTAL LINK TYPE BREAKDOWN:")
        print(f"   📝 LinkedIn Posts: {all_posts}")
        print(f"   💼 Job Listings: {all_jobs}")
        print(f"   👤 Profiles: {all_profiles}")
        print(f"   🔗 Total: {len(links)}")
        
        return csv_filename

async def main():
    """Main function."""
    # Ensure storage directory exists
    os.makedirs("./storage", exist_ok=True)
    
    # Create and run scraper for ALL links
    scraper = AllLinksNotionScraper()
    all_links = await scraper.scrape_all_pages()
    
    if all_links:
        csv_file = scraper.save_all_links_csv(all_links)
        
        print(f"\n✅ SUCCESS!")
        print(f"   📊 Extracted {len(all_links)} total LinkedIn links")
        print(f"   💾 Single CSV: {csv_file}")
        print(f"   🔄 All data is current (just scraped)")
        
        print(f"\n🔗 SAMPLE LINKS FROM EACH PAGE:")
        current_page = 0
        for link in all_links:
            if link['page_number'] != current_page:
                current_page = link['page_number']
                print(f"\n   Page {current_page} - {link['page_name']}:")
                print(f"   {link['url']}")
        
    else:
        print(f"\n❌ FAILED! No links extracted")

if __name__ == "__main__":
    asyncio.run(main())