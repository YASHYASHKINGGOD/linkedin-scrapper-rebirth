#!/usr/bin/env python3
"""
Scrape ALL August LinkedIn links from all three Notion pages with infinite scroll.
Scrolls through entire pages to capture all August content, not just visible content.
"""

import os
import csv
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
from src.extractor.notion.links import extract_linkedin_links_from_html

class AugustLinksNotionScraper:
    """Scraper to extract ALL August LinkedIn links with scrolling support."""
    
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
        """Setup Playwright browser for scrolling."""
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
    
    async def scroll_and_load_all_content(self, page: Page) -> bool:
        """Scroll through the entire Notion page to load all content."""
        try:
            print(f"   📜 Scrolling to load all content...")
            
            # Initial wait for page load
            await page.wait_for_load_state('networkidle', timeout=30000)
            await page.wait_for_selector('div[role="application"]', timeout=20000)
            await asyncio.sleep(3)
            
            # Get initial page height
            prev_height = await page.evaluate("document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 50  # Prevent infinite loops
            
            while scroll_attempts < max_scrolls:
                print(f"   ⬇️  Scroll attempt {scroll_attempts + 1}/{max_scrolls}")
                
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # Wait for new content to load
                await asyncio.sleep(2)
                
                # Check if new content loaded
                new_height = await page.evaluate("document.body.scrollHeight")
                
                if new_height == prev_height:
                    # No new content, try a few more times to be sure
                    if scroll_attempts >= 3:
                        print(f"   ✅ Reached end of content after {scroll_attempts + 1} scrolls")
                        break
                else:
                    print(f"   📈 New content loaded (height: {prev_height} -> {new_height})")
                    prev_height = new_height
                    scroll_attempts = 0  # Reset counter when new content loads
                
                scroll_attempts += 1
            
            # Scroll back to top to ensure we capture everything
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            print(f"   ❌ Scrolling error: {e}")
            return False
    
    def filter_august_links(self, links: List[Dict], page_info: Dict) -> List[Dict]:
        """Filter links to only include August content."""
        august_links = []
        august_keywords = ['august', 'aug', '08/', '/08', '2024-08', '2025-08']
        
        for link in links:
            # Check if link contains August references
            is_august = False
            
            # Check URL for August patterns
            url_lower = link.get('url', '').lower()
            for keyword in august_keywords:
                if keyword in url_lower:
                    is_august = True
                    break
            
            # Check anchor text and context for August references
            if not is_august:
                text_content = (
                    (link.get('anchor_text', '') + ' ' + 
                     link.get('row_context', '')).lower()
                )
                for keyword in august_keywords:
                    if keyword in text_content:
                        is_august = True
                        break
            
            # For LinkedIn activity posts, check if they're from August timeframe
            if not is_august and '/posts/' in link.get('url', ''):
                # LinkedIn activity IDs starting with 736x are typically from August 2024
                if 'activity-736' in link.get('url', ''):
                    is_august = True
            
            if is_august:
                link['august_filter'] = 'matched'
                august_links.append(link)
        
        print(f"   📅 Filtered {len(august_links)} August links from {len(links)} total")
        return august_links
    
    async def scrape_page_august_links(self, browser: Browser, page_info: Dict, page_number: int) -> List[Dict]:
        """Scrape ALL August LinkedIn links from a single Notion page with scrolling."""
        print(f"\n📄 Page {page_number}/3: {page_info['name']}")
        print(f"   🔗 URL: {page_info['url']}")
        
        page = await browser.new_page()
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        try:
            await page.goto(page_info['url'], timeout=30000, wait_until='domcontentloaded')
            
            # Scroll through entire page to load all content
            scrolled = await self.scroll_and_load_all_content(page)
            
            if not scrolled:
                print(f"   ⚠️  Scrolling failed, extracting visible content only")
            
            # Get complete page HTML after scrolling
            html_content = await page.content()
            
            # Save debug HTML for inspection
            debug_path = f"./storage/august_debug_{page_info['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 Full page HTML saved: {debug_path}")
            
            # Extract ALL LinkedIn links from complete page
            all_links = extract_linkedin_links_from_html(
                html_content, 
                page_info['url'],
                limit=None  # No limit - get everything
            )
            
            print(f"   🔗 Total links found: {len(all_links)}")
            
            # Filter for August content only
            august_links = self.filter_august_links(all_links, page_info)
            
            # Add metadata to August links
            current_time = datetime.now().isoformat()
            for i, link in enumerate(august_links, 1):
                link.update({
                    'page_number': page_number,
                    'page_id': page_info['id'],
                    'page_name': page_info['name'],
                    'august_link_number': i,
                    'scraped_at': current_time,
                    'scraping_method': 'scrolling_playwright',
                    'data_freshness': 'august_filtered',
                    'total_links_on_page': len(all_links)
                })
            
            print(f"   ✅ August links extracted: {len(august_links)}")
            if august_links:
                # Show breakdown by link type
                posts = sum(1 for link in august_links if '/posts/' in link['url'])
                jobs = sum(1 for link in august_links if '/jobs/' in link['url'])
                profiles = sum(1 for link in august_links if '/in/' in link['url'])
                print(f"   📊 August Posts: {posts}, Jobs: {jobs}, Profiles: {profiles}")
            
            return august_links
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
            
        finally:
            await page.close()
    
    async def scrape_all_august_links(self) -> List[Dict]:
        """Scrape ALL August LinkedIn links from all three Notion pages."""
        print("🚀 SCRAPING ALL AUGUST LINKEDIN LINKS WITH SCROLLING")
        print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Target: ALL August LinkedIn links from {len(self.pages_info)} pages")
        print("📜 Using infinite scroll to capture complete page content")
        print("=" * 70)
        
        browser = await self.setup_browser()
        all_august_links = []
        
        try:
            for i, page_info in enumerate(self.pages_info, 1):
                august_links = await self.scrape_page_august_links(browser, page_info, i)
                all_august_links.extend(august_links)
                await asyncio.sleep(3)  # Longer delay between pages
                
        finally:
            await browser.close()
        
        return all_august_links
    
    def save_august_links_csv(self, links: List[Dict]) -> Optional[str]:
        """Save all August links to CSV file."""
        if not links:
            print("❌ No August links to save")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"./storage/august_notion_linkedin_links_{timestamp}.csv"
        
        # CSV columns with August-specific fields
        fieldnames = [
            'page_number', 'page_id', 'page_name', 'august_link_number', 'url', 
            'anchor_text', 'row_context', 'source_page_url', 'august_filter',
            'scraped_at', 'scraping_method', 'data_freshness', 'total_links_on_page',
            'source', 'captured_at'
        ]
        
        # Save to CSV
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(links)
        
        print(f"\n💾 ALL AUGUST LINKS SAVED TO CSV:")
        print(f"   📄 File: {csv_filename}")
        print(f"   📊 Total August links: {len(links)}")
        
        # Breakdown by page
        page_counts = {}
        for link in links:
            page_key = f"Page {link['page_number']}: {link['page_name'][:35]}..."
            page_counts[page_key] = page_counts.get(page_key, 0) + 1
        
        print(f"\n📈 AUGUST LINKS BY PAGE:")
        for page, count in page_counts.items():
            print(f"   • {page}: {count} August links")
        
        # Breakdown by link type
        august_posts = sum(1 for link in links if '/posts/' in link['url'])
        august_jobs = sum(1 for link in links if '/jobs/' in link['url'])
        august_profiles = sum(1 for link in links if '/in/' in link['url'])
        
        print(f"\n📊 AUGUST LINK TYPE BREAKDOWN:")
        print(f"   📝 LinkedIn Posts: {august_posts}")
        print(f"   💼 Job Listings: {august_jobs}")
        print(f"   👤 Profiles: {august_profiles}")
        print(f"   🔗 Total August Links: {len(links)}")
        
        return csv_filename

async def main():
    """Main function."""
    # Ensure storage directory exists
    os.makedirs("./storage", exist_ok=True)
    
    # Create and run August scraper with scrolling
    scraper = AugustLinksNotionScraper()
    august_links = await scraper.scrape_all_august_links()
    
    if august_links:
        csv_file = scraper.save_august_links_csv(august_links)
        
        print(f"\n✅ SUCCESS!")
        print(f"   📊 Extracted {len(august_links)} August LinkedIn links")
        print(f"   💾 Single CSV: {csv_file}")
        print(f"   📅 Focused on August 2024/2025 content only")
        
        print(f"\n🔗 SAMPLE AUGUST LINKS:")
        for i, link in enumerate(august_links[:8], 1):
            print(f"   {i}. {link['url']}")
            print(f"      From: {link['page_name']} (August content)")
        
        print(f"\n📜 SCROLLING SUMMARY:")
        print(f"   • Used infinite scroll to load complete pages")
        print(f"   • Filtered for August-specific content only")  
        print(f"   • Saved debug HTML files for inspection")
        
    else:
        print(f"\n❌ FAILED! No August links found")

if __name__ == "__main__":
    asyncio.run(main())