#!/usr/bin/env python3
"""
Enhanced August LinkedIn scraper with improved scrolling and retry logic.
Handles large Notion pages by using aggressive scrolling and multiple extraction attempts.
"""

import os
import csv
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
from src.extractor.notion.links import extract_linkedin_links_from_html

class EnhancedAugustScraper:
    """Enhanced scraper with better scrolling for August content."""
    
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
        """Setup browser with longer timeouts."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,  # Visible for debugging
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
    
    async def aggressive_scroll_load(self, page: Page, max_attempts: int = 100) -> int:
        """Aggressively scroll and load content with multiple strategies."""
        print(f"   🔄 Starting aggressive scroll (max {max_attempts} attempts)")
        
        try:
            # Wait for initial load with longer timeout
            await page.wait_for_load_state('domcontentloaded', timeout=60000)
            await asyncio.sleep(5)
            
            scroll_count = 0
            no_change_count = 0
            prev_height = 0
            
            for attempt in range(max_attempts):
                # Get current content metrics
                current_height = await page.evaluate("document.body.scrollHeight")
                link_count = await page.evaluate("""
                    document.querySelectorAll('a[href*="linkedin.com"]').length
                """)
                
                if current_height != prev_height:
                    print(f"   📈 Attempt {attempt+1}: Height {current_height}, Links {link_count}")
                    prev_height = current_height
                    no_change_count = 0
                else:
                    no_change_count += 1
                
                # Multiple scroll strategies
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                
                # Alternative: Scroll by viewport
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(1)
                
                # Press End key to trigger more content
                await page.keyboard.press('End')
                await asyncio.sleep(1)
                
                # Click any "Load more" buttons if they exist
                try:
                    load_more = await page.query_selector('[data-testid="load-more"], .load-more, [aria-label*="load"], [aria-label*="Load"]')
                    if load_more:
                        await load_more.click()
                        print(f"   🔘 Clicked load more button")
                        await asyncio.sleep(3)
                except:
                    pass
                
                scroll_count += 1
                
                # Stop if no new content after several attempts
                if no_change_count >= 8:
                    print(f"   ✅ Content stable after {scroll_count} scrolls")
                    break
                
                # Brief pause between intense scrolling
                if attempt % 10 == 0 and attempt > 0:
                    print(f"   ⏸️  Brief pause at attempt {attempt}")
                    await asyncio.sleep(5)
            
            # Final scroll back to capture everything
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(3)
            
            final_height = await page.evaluate("document.body.scrollHeight")
            final_links = await page.evaluate("document.querySelectorAll('a[href*=\"linkedin.com\"]').length")
            
            print(f"   🏁 Final: Height {final_height}, LinkedIn links {final_links}")
            return final_links
            
        except Exception as e:
            print(f"   ❌ Scroll error: {e}")
            return 0
    
    def enhanced_august_filter(self, links: List[Dict]) -> List[Dict]:
        """Enhanced filtering for August content with broader criteria."""
        august_links = []
        
        # Expanded August patterns
        august_patterns = [
            'august', 'aug', '08/', '/08', '2024-08', '2025-08',
            'activity-736', 'activity-735', 'activity-737',  # LinkedIn activity IDs from August
            'aug2024', 'august2024', 'aug2025', 'august2025'
        ]
        
        for link in links:
            is_august = False
            match_reason = ""
            
            # Check URL patterns
            url_lower = link.get('url', '').lower()
            for pattern in august_patterns:
                if pattern in url_lower:
                    is_august = True
                    match_reason = f"URL contains '{pattern}'"
                    break
            
            # Check text content
            if not is_august:
                full_text = (
                    (link.get('anchor_text', '') + ' ' + link.get('row_context', '')).lower()
                )
                for pattern in august_patterns:
                    if pattern in full_text:
                        is_august = True
                        match_reason = f"Text contains '{pattern}'"
                        break
            
            # LinkedIn activity ID analysis (more specific)
            if not is_august and '/posts/' in link.get('url', ''):
                url = link.get('url', '')
                # Activity IDs from August 2024 typically start with 736x
                import re
                activity_match = re.search(r'activity-(\d+)', url)
                if activity_match:
                    activity_id = activity_match.group(1)
                    if activity_id.startswith(('7359', '7360', '7361', '7362', '7363', '7364')):
                        is_august = True
                        match_reason = f"LinkedIn activity ID suggests August 2024"
            
            if is_august:
                link['august_match_reason'] = match_reason
                august_links.append(link)
        
        print(f"   📅 Enhanced filter: {len(august_links)} August links from {len(links)} total")
        return august_links
    
    async def scrape_page_with_enhanced_scroll(self, browser: Browser, page_info: Dict, page_number: int) -> List[Dict]:
        """Scrape page with enhanced scrolling strategy."""
        print(f"\n📄 Page {page_number}/3: {page_info['name']}")
        print(f"   🔗 URL: {page_info['url']}")
        
        page = await browser.new_page()
        
        # Set longer timeouts
        page.set_default_timeout(120000)  # 2 minutes
        
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        try:
            print(f"   🌐 Navigating to page...")
            await page.goto(page_info['url'], timeout=120000, wait_until='domcontentloaded')
            
            # Enhanced scrolling
            final_link_count = await self.aggressive_scroll_load(page)
            
            print(f"   📄 Extracting HTML content...")
            html_content = await page.content()
            
            # Save full HTML for debugging
            debug_path = f"./storage/enhanced_august_{page_info['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 Full HTML saved: {debug_path}")
            
            # Extract all links
            all_links = extract_linkedin_links_from_html(
                html_content, 
                page_info['url'],
                limit=None
            )
            
            print(f"   🔗 Total LinkedIn links extracted: {len(all_links)}")
            
            # Enhanced August filtering
            august_links = self.enhanced_august_filter(all_links)
            
            # Add metadata
            current_time = datetime.now().isoformat()
            for i, link in enumerate(august_links, 1):
                link.update({
                    'page_number': page_number,
                    'page_id': page_info['id'],
                    'page_name': page_info['name'],
                    'august_link_number': i,
                    'scraped_at': current_time,
                    'scraping_method': 'enhanced_scrolling',
                    'total_links_found': len(all_links),
                    'scroll_link_count': final_link_count
                })
            
            print(f"   ✅ August links: {len(august_links)}")
            if august_links:
                posts = sum(1 for link in august_links if '/posts/' in link['url'])
                jobs = sum(1 for link in august_links if '/jobs/' in link['url'])
                profiles = sum(1 for link in august_links if '/in/' in link['url'])
                print(f"   📊 Posts: {posts}, Jobs: {jobs}, Profiles: {profiles}")
                
                # Show some match reasons
                reasons = {}
                for link in august_links[:5]:
                    reason = link.get('august_match_reason', 'unknown')
                    reasons[reason] = reasons.get(reason, 0) + 1
                print(f"   🎯 Sample match reasons: {dict(list(reasons.items())[:3])}")
            
            return august_links
            
        except Exception as e:
            print(f"   ❌ Page error: {e}")
            return []
            
        finally:
            await page.close()
    
    async def run_enhanced_august_scraping(self) -> List[Dict]:
        """Run the enhanced August scraping process."""
        print("🚀 ENHANCED AUGUST LINKEDIN SCRAPER")
        print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Target: ALL August LinkedIn links with aggressive scrolling")
        print(f"📜 Enhanced filtering and multiple scroll strategies")
        print("=" * 70)
        
        browser = await self.setup_browser()
        all_august_links = []
        
        try:
            for i, page_info in enumerate(self.pages_info, 1):
                august_links = await self.scrape_page_with_enhanced_scroll(browser, page_info, i)
                all_august_links.extend(august_links)
                
                # Longer delay between pages for stability
                if i < len(self.pages_info):
                    print(f"   ⏳ Waiting 10 seconds before next page...")
                    await asyncio.sleep(10)
                
        finally:
            await browser.close()
        
        return all_august_links
    
    def save_enhanced_results(self, links: List[Dict]) -> Optional[str]:
        """Save enhanced August results."""
        if not links:
            print("❌ No enhanced August links found")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"./storage/enhanced_august_notion_links_{timestamp}.csv"
        
        fieldnames = [
            'page_number', 'page_id', 'page_name', 'august_link_number', 'url',
            'anchor_text', 'row_context', 'source_page_url', 'august_match_reason',
            'scraped_at', 'scraping_method', 'total_links_found', 'scroll_link_count',
            'source', 'captured_at'
        ]
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(links)
        
        print(f"\n💾 ENHANCED AUGUST RESULTS SAVED:")
        print(f"   📄 File: {csv_filename}")
        print(f"   📊 Total August links: {len(links)}")
        
        # Analysis
        page_counts = {}
        reason_counts = {}
        
        for link in links:
            # Page breakdown
            page = f"Page {link['page_number']}"
            page_counts[page] = page_counts.get(page, 0) + 1
            
            # Reason breakdown
            reason = link.get('august_match_reason', 'unknown')
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        print(f"\n📈 ENHANCED RESULTS BY PAGE:")
        for page, count in page_counts.items():
            print(f"   • {page}: {count} August links")
        
        print(f"\n🎯 MATCH REASONS:")
        for reason, count in list(reason_counts.items())[:5]:
            print(f"   • {reason}: {count} links")
        
        return csv_filename

async def main():
    """Main enhanced scraper function."""
    os.makedirs("./storage", exist_ok=True)
    
    scraper = EnhancedAugustScraper()
    enhanced_links = await scraper.run_enhanced_august_scraping()
    
    if enhanced_links:
        csv_file = scraper.save_enhanced_results(enhanced_links)
        
        print(f"\n✅ ENHANCED SUCCESS!")
        print(f"   📊 Found {len(enhanced_links)} August LinkedIn links")
        print(f"   💾 Enhanced CSV: {csv_file}")
        print(f"   🔄 Used aggressive scrolling + enhanced filtering")
        
    else:
        print(f"\n❌ No August links found with enhanced scraping")

if __name__ == "__main__":
    asyncio.run(main())