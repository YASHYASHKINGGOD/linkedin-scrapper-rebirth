#!/usr/bin/env python3
"""
Scrape the LATEST LinkedIn links from live Notion pages.
Gets first 10 links from each of the 3 pages (30 total).
"""

import os
import csv
import json
import asyncio
from datetime import datetime
from typing import List, Dict
from src.extractor.notion.client import NotionScraper, NotionConfig
from src.extractor.notion.links import extract_linkedin_links_from_html

# The 3 current Notion pages 
NOTION_PAGES = [
    {
        "url": "https://diligent-actor-263.notion.site/13b8c7fca68e804aa0c3ca803aa07a3f?v=13b8c7fca68e817abca9000c95bbc26f",
        "name": "Diligent Actor - Internships & Jobs Page 1"
    },
    {
        "url": "https://diligent-actor-263.notion.site/15a8c7fca68e80d7b612e1ba7379dd8a?v=15a8c7fca68e8154b0c0000c7a9241c9",
        "name": "Diligent Actor - Experienced Analytics & Data Science Page 2" 
    },
    {
        "url": "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422",
        "name": "FOC Community - Founder's Office Roles"
    }
]

async def scrape_live_notion_page(page_info: dict, page_number: int) -> List[Dict[str, str]]:
    """Scrape a single live Notion page for LinkedIn links."""
    print(f"\n🔍 Scraping Page {page_number}/3: {page_info['name']}")
    print(f"   📋 URL: {page_info['url'][:80]}...")
    
    # Configure for reliable scraping
    config = NotionConfig(
        headless=True,  # Run headless for production
        timeout=45000,  # 45 seconds timeout
        wait_for_content=10000,  # Wait 10 seconds for content to load
        delay_between_requests=3.0  # Respectful 3-second delay
    )
    
    try:
        async with NotionScraper(config) as scraper:
            print(f"   🚀 Launching browser...")
            
            # Fetch the page
            html_content = await scraper.fetch_page(page_info['url'])
            
            print(f"   📄 Retrieved {len(html_content)} characters of HTML")
            
            # Save HTML for debugging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = f"./storage/live_notion_page_{page_number}_{timestamp}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 Saved HTML to {debug_file}")
            
            # Extract LinkedIn links
            links = extract_linkedin_links_from_html(html_content, page_info['url'], limit=10)
            
            # Add metadata
            for i, link in enumerate(links, 1):
                link["page_number"] = page_number
                link["page_name"] = page_info['name']
                link["link_number"] = i
                link["scraped_at"] = datetime.now().isoformat()
                link["scrape_method"] = "live_playwright"
            
            print(f"   ✅ Extracted {len(links)} LinkedIn links")
            
            if len(links) > 0:
                print(f"   🔗 Sample: {links[0]['url']}")
            
            return links
            
    except Exception as e:
        print(f"   ❌ Error scraping page: {e}")
        return []

async def scrape_all_live_pages() -> List[Dict[str, str]]:
    """Scrape all 3 live Notion pages concurrently."""
    print("🚀 LIVE NOTION SCRAPER - Getting Latest Links")
    print("=" * 60)
    
    all_links = []
    
    # Scrape pages one by one to be respectful to the server
    for i, page_info in enumerate(NOTION_PAGES, 1):
        links = await scrape_live_notion_page(page_info, i)
        all_links.extend(links)
        
        # Add delay between pages
        if i < len(NOTION_PAGES):
            print(f"   ⏱️  Waiting 5 seconds before next page...")
            await asyncio.sleep(5)
    
    return all_links

def save_latest_results(links: List[Dict[str, str]]):
    """Save the latest results to CSV."""
    if not links:
        print("❌ No links extracted")
        return None
    
    # Generate timestamp for filename  
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"./storage/latest_notion_links_{timestamp}.csv"
    
    # Define CSV columns
    fieldnames = [
        "page_number", "page_name", "link_number", "url", 
        "anchor_text", "row_context", "source_page_url", 
        "scraped_at", "scrape_method", "source", "captured_at"
    ]
    
    # Save to CSV
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(links)
    
    print(f"\n💾 LATEST RESULTS SAVED:")
    print(f"   📄 File: {csv_filename}")
    print(f"   📊 Total links: {len(links)}")
    
    # Summary by page
    page_counts = {}
    for link in links:
        page_key = f"Page {link['page_number']}"
        page_counts[page_key] = page_counts.get(page_key, 0) + 1
    
    print(f"\n📈 BREAKDOWN:")
    for page, count in page_counts.items():
        print(f"   • {page}: {count} links")
    
    # Show sample of latest links
    print(f"\n🔗 LATEST LINKS SAMPLE:")
    for i, link in enumerate(links[:5], 1):
        print(f"   {i}. {link['url']}")
        print(f"      From: {link['page_name']}")
        if 'captured_at' in link:
            print(f"      Time: {link['captured_at']}")
        print()
    
    return csv_filename

async def main():
    """Main async function."""
    print("🎯 SCRAPING LATEST NOTION LINKS")
    print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Target: First 10 links from each of {len(NOTION_PAGES)} pages")
    
    # Ensure storage directory exists
    os.makedirs("./storage", exist_ok=True)
    
    try:
        # Scrape all pages
        latest_links = await scrape_all_live_pages()
        
        # Save results
        if latest_links:
            csv_file = save_latest_results(latest_links)
            
            print(f"\n✅ SUCCESS!")
            print(f"   🎯 Got {len(latest_links)} fresh LinkedIn links")
            print(f"   💾 Saved to: {csv_file}")
            print(f"   🔄 Ready for PostgreSQL storage!")
        else:
            print(f"\n❌ FAILED!")
            print("   No links were extracted from any page")
            
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

def run_scraper():
    """Run the async scraper."""
    asyncio.run(main())

if __name__ == "__main__":
    run_scraper()