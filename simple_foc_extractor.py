#!/usr/bin/env python3
"""
Simple and Reliable FOC Community Notion Extractor
Focus on getting the data without over-engineering
"""

import os
import csv
import asyncio
from datetime import datetime
from typing import List, Dict
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def extract_foc_data():
    """Simple extraction from FOC Community page."""
    
    print("🚀 SIMPLE FOC EXTRACTOR")
    print("📅 Time:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🎯 Extracting LinkedIn links from FOC Community")
    print("=" * 60)
    
    url = "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Non-headless to see what's happening
        page = await browser.new_page()
        
        # Set realistic browser settings
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        try:
            print("   🌐 Loading page...")
            # Load page with simple strategy
            await page.goto(url, timeout=120000)  # 2 minute timeout
            print("   ✅ Page loaded")
            
            # Wait a bit for initial content
            await asyncio.sleep(5)
            print("   ⏳ Waiting for content to load...")
            
            # Simple scroll to load more content
            for i in range(10):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                # Count links after each scroll
                link_count = await page.evaluate('document.querySelectorAll("a[href*=\\"linkedin.com\\"]").length')
                print(f"   📊 Scroll {i+1}: {link_count} LinkedIn links found")
                
                if i > 3 and link_count == 0:
                    print("   ⚠️  No LinkedIn links found after several scrolls")
                    break
            
            print("   📄 Getting page HTML...")
            html_content = await page.content()
            
            # Save HTML for inspection
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            html_file = f"./storage/foc_simple_{timestamp}.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 HTML saved to: {html_file}")
            
        except Exception as e:
            print(f"   ❌ Error loading page: {e}")
            return []
        
        finally:
            await browser.close()
    
    # Parse HTML
    print("   🔍 Parsing HTML for LinkedIn links...")
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Find all LinkedIn links
    linkedin_links = soup.find_all('a', href=lambda x: x and 'linkedin.com' in x.lower())
    print(f"   🔗 Found {len(linkedin_links)} LinkedIn links")
    
    # Extract data
    extracted_data = []
    for i, link in enumerate(linkedin_links):
        href = link.get('href', '').strip()
        
        # Clean URL
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = 'https://linkedin.com' + href
        
        # Get context
        link_text = link.get_text(strip=True)
        
        # Try to get row/context
        row_context = ""
        for parent_tag in ['tr', 'div', 'li']:
            parent = link.find_parent(parent_tag)
            if parent:
                context = parent.get_text(strip=True)
                if len(context) > 20:
                    row_context = context[:300]
                    break
        
        # Simple data extraction
        company = ""
        role = ""
        
        # Try to extract company and role from context
        if row_context:
            # Look for patterns like "Company - Role" or similar
            parts = re.split(r'[-–—|]', row_context)
            if len(parts) >= 2:
                company = parts[0].strip()
                role = parts[1].strip()
        
        record = {
            'link_number': i + 1,
            'url': href,
            'link_text': link_text,
            'company': company,
            'role': role,
            'context': row_context,
            'url_type': classify_url(href),
            'extracted_at': datetime.now().isoformat()
        }
        
        extracted_data.append(record)
    
    return extracted_data

def classify_url(url: str) -> str:
    """Simple URL classification."""
    url_lower = url.lower()
    if '/jobs/view/' in url_lower:
        return 'job'
    elif '/posts/' in url_lower:
        return 'post'
    elif '/in/' in url_lower:
        return 'profile'
    elif '/company/' in url_lower:
        return 'company'
    return 'other'

def save_data(data: List[Dict]) -> str:
    """Save extracted data to CSV."""
    if not data:
        print("❌ No data to save")
        return ""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = f"./storage/foc_simple_extract_{timestamp}.csv"
    
    fieldnames = ['link_number', 'url', 'link_text', 'company', 'role', 'context', 'url_type', 'extracted_at']
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"\n💾 DATA SAVED: {csv_file}")
    print(f"📊 Total records: {len(data)}")
    
    # Show breakdown
    url_types = {}
    for record in data:
        url_type = record.get('url_type', 'unknown')
        url_types[url_type] = url_types.get(url_type, 0) + 1
    
    print(f"\n📈 BREAKDOWN:")
    for url_type, count in url_types.items():
        print(f"   • {url_type}: {count}")
    
    # Show samples
    print(f"\n🔗 SAMPLE RECORDS:")
    for i, record in enumerate(data[:5]):
        company = record.get('company', 'N/A')[:30]
        role = record.get('role', 'N/A')[:30] 
        url_type = record.get('url_type', 'N/A')
        print(f"   {i+1}. {company} - {role} ({url_type})")
    
    return csv_file

async def main():
    """Main function."""
    os.makedirs("./storage", exist_ok=True)
    
    data = await extract_foc_data()
    
    if data:
        csv_file = save_data(data)
        print(f"\n✅ SUCCESS! Extracted {len(data)} records")
        print(f"💾 File: {csv_file}")
    else:
        print(f"\n❌ FAILED - No data extracted")

if __name__ == "__main__":
    asyncio.run(main())