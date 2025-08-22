#!/usr/bin/env python3
"""
Robust Notion scraper with multiple fallback strategies.
"""

import os
import csv
import json
import asyncio
import requests
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# The 3 current Notion pages 
NOTION_PAGES = [
    {
        "url": "https://diligent-actor-263.notion.site/13b8c7fca68e804aa0c3ca803aa07a3f?v=13b8c7fca68e817abca9000c95bbc26f",
        "name": "Diligent Actor - Page 1"
    },
    {
        "url": "https://diligent-actor-263.notion.site/15a8c7fca68e80d7b612e1ba7379dd8a?v=15a8c7fca68e8154b0c0000c7a9241c9",
        "name": "Diligent Actor - Page 2" 
    },
    {
        "url": "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422",
        "name": "FOC Community"
    }
]

def scrape_with_requests(url: str, timeout: int = 30) -> Optional[str]:
    """Try scraping with simple requests first."""
    print(f"   📡 Trying requests method...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        print(f"   ✅ Requests method worked! Got {len(response.text)} characters")
        return response.text
        
    except Exception as e:
        print(f"   ❌ Requests method failed: {e}")
        return None

async def scrape_with_playwright_simple(url: str) -> Optional[str]:
    """Try scraping with Playwright with simpler settings."""
    print(f"   🎭 Trying Playwright with simpler settings...")
    
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            # Just go to the page with a longer timeout but simpler wait
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')
            
            # Wait a bit for content to load
            await asyncio.sleep(8)
            
            # Get content
            content = await page.content()
            
            await browser.close()
            
            print(f"   ✅ Playwright simple method worked! Got {len(content)} characters")
            return content
            
    except Exception as e:
        print(f"   ❌ Playwright simple method failed: {e}")
        return None

def extract_linkedin_links_simple(html_content: str, source_url: str, limit: int = 10) -> List[Dict[str, str]]:
    """Extract LinkedIn links using BeautifulSoup."""
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    seen_urls = set()
    
    # Look for all links that contain linkedin.com
    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        
        if not href or 'linkedin.com' not in href.lower():
            continue
            
        # Clean up the URL
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = 'https://linkedin.com' + href
            
        # Remove tracking parameters but keep the base URL
        if '?' in href and ('/posts/' in href or '/jobs/' in href):
            href = href.split('?')[0]
            
        # Skip duplicates
        if href in seen_urls:
            continue
        seen_urls.add(href)
        
        # Get link text
        link_text = link.get_text(strip=True)
        
        # Get context from parent
        context = ""
        parent = link.parent
        if parent:
            context = parent.get_text(strip=True)[:200]
        
        link_data = {
            "url": href,
            "anchor_text": link_text,
            "row_context": context,
            "source_page_url": source_url,
            "captured_at": datetime.now().isoformat(),
            "source": "notion"
        }
        
        links.append(link_data)
        
        if len(links) >= limit:
            break
    
    return links

async def scrape_single_page(page_info: dict, page_number: int) -> List[Dict[str, str]]:
    """Scrape a single page with multiple fallback methods."""
    print(f"\n🔍 Scraping Page {page_number}/3: {page_info['name']}")
    print(f"   🌐 URL: {page_info['url'][:80]}...")
    
    html_content = None
    
    # Method 1: Try simple requests first
    html_content = scrape_with_requests(page_info['url'])
    
    # Method 2: If requests fails, try Playwright
    if not html_content:
        html_content = await scrape_with_playwright_simple(page_info['url'])
    
    # If we got content, process it
    if html_content:
        # Save HTML for debugging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = f"./storage/robust_page_{page_number}_{timestamp}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"   💾 Saved HTML to {debug_file}")
        
        # Extract LinkedIn links
        links = extract_linkedin_links_simple(html_content, page_info['url'], limit=10)
        
        # Add metadata
        for i, link in enumerate(links, 1):
            link["page_number"] = page_number
            link["page_name"] = page_info['name']
            link["link_number"] = i
            link["scraped_at"] = datetime.now().isoformat()
        
        print(f"   ✅ Found {len(links)} LinkedIn links")
        
        if links:
            print(f"   🔗 Sample: {links[0]['url']}")
        
        return links
    else:
        print(f"   ❌ All methods failed for this page")
        return []

async def main():
    """Main function."""
    print("🚀 ROBUST NOTION SCRAPER")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 Attempting multiple methods to get latest links")
    print("=" * 60)
    
    os.makedirs("./storage", exist_ok=True)
    
    all_links = []
    
    for i, page_info in enumerate(NOTION_PAGES, 1):
        try:
            links = await scrape_single_page(page_info, i)
            all_links.extend(links)
            
            # Be respectful - wait between pages
            if i < len(NOTION_PAGES):
                print(f"   ⏱️  Waiting 3 seconds...")
                await asyncio.sleep(3)
                
        except Exception as e:
            print(f"   💥 Error on page {i}: {e}")
    
    # Save results
    if all_links:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"./storage/robust_notion_links_{timestamp}.csv"
        
        fieldnames = [
            "page_number", "page_name", "link_number", "url", 
            "anchor_text", "row_context", "source_page_url", 
            "scraped_at", "captured_at", "source"
        ]
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_links)
        
        print(f"\n✅ SUCCESS!")
        print(f"   📊 Total links: {len(all_links)}")
        print(f"   💾 Saved to: {csv_filename}")
        
        # Show breakdown
        page_counts = {}
        for link in all_links:
            page = f"Page {link['page_number']}"
            page_counts[page] = page_counts.get(page, 0) + 1
        
        for page, count in page_counts.items():
            print(f"   • {page}: {count} links")
            
        # Show samples
        print(f"\n🔗 Sample links:")
        for i, link in enumerate(all_links[:3], 1):
            print(f"   {i}. {link['url']}")
            
    else:
        print(f"\n❌ No links extracted from any page")

if __name__ == "__main__":
    asyncio.run(main())