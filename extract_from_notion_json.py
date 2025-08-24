#!/usr/bin/env python3
"""
Extract LinkedIn links from Notion's serverSidePrefetchData JSON.
This avoids the need for browser automation by parsing the data directly.
"""

import os
import re
import json
import csv
import requests
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

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

def extract_json_from_html(html_content: str) -> Optional[dict]:
    """Extract the serverSidePrefetchData JSON from Notion HTML."""
    try:
        # Look for the script tag with serverSidePrefetchData
        pattern = r'__notion_html_async\.push\("serverSidePrefetchData",(.+?)\)'
        match = re.search(pattern, html_content, re.DOTALL)
        
        if match:
            json_str = match.group(1)
            # Clean up and parse the JSON
            data = json.loads(json_str)
            return data
        else:
            print("   ⚠️  No serverSidePrefetchData found")
            return None
            
    except Exception as e:
        print(f"   ❌ Error parsing JSON: {e}")
        return None

def extract_links_from_notion_data(data: dict, source_url: str, limit: int = 10) -> List[Dict[str, str]]:
    """Extract LinkedIn links from Notion's data structure."""
    links = []
    seen_urls = set()
    
    try:
        # Navigate through the Notion data structure
        record_map = data.get("recordMap", {})
        blocks = record_map.get("block", {})
        
        for block_id, block_data in blocks.items():
            if not isinstance(block_data, dict):
                continue
                
            value = block_data.get("value", {})
            if not isinstance(value, dict):
                continue
                
            # Look for properties that might contain URLs
            properties = value.get("properties", {})
            if not isinstance(properties, dict):
                continue
            
            # Check all properties for LinkedIn URLs
            for prop_key, prop_value in properties.items():
                if not isinstance(prop_value, list):
                    continue
                    
                # Notion stores rich text as nested arrays
                for item in prop_value:
                    if not isinstance(item, list):
                        continue
                    
                    for subitem in item:
                        if isinstance(subitem, str) and 'linkedin.com' in subitem.lower():
                            # Found a LinkedIn URL
                            url = subitem.strip()
                            
                            # Clean and normalize the URL
                            if url.startswith('//'):
                                url = 'https:' + url
                            elif url.startswith('/'):
                                url = 'https://linkedin.com' + url
                            
                            # Remove tracking parameters
                            if '?' in url and ('/posts/' in url or '/jobs/' in url or '/in/' in url):
                                url = url.split('?')[0]
                            
                            if url not in seen_urls:
                                seen_urls.add(url)
                                
                                link_data = {
                                    "url": url,
                                    "anchor_text": url,
                                    "row_context": f"Found in block {block_id}",
                                    "source_page_url": source_url,
                                    "captured_at": datetime.now().isoformat(),
                                    "source": "notion_json",
                                    "block_id": block_id
                                }
                                
                                links.append(link_data)
                                
                                if len(links) >= limit:
                                    return links
        
        # If we didn't find enough in properties, also check formatted text
        if len(links) < limit:
            # Look in the collection data if it exists
            collection = record_map.get("collection", {})
            for coll_id, coll_data in collection.items():
                if not isinstance(coll_data, dict):
                    continue
                    
                # Sometimes links are stored in the collection schema or description
                schema = coll_data.get("value", {}).get("schema", {})
                for field_id, field_data in schema.items():
                    if isinstance(field_data, dict):
                        name = field_data.get("name", "")
                        if 'linkedin' in name.lower():
                            # This might be a LinkedIn field
                            pass
        
        return links
        
    except Exception as e:
        print(f"   ❌ Error extracting from data: {e}")
        return []

def scrape_page_for_json(page_info: dict, page_number: int) -> List[Dict[str, str]]:
    """Scrape a single page and extract LinkedIn links from JSON data."""
    print(f"\n🔍 Page {page_number}/3: {page_info['name']}")
    print(f"   🌐 URL: {page_info['url'][:80]}...")
    
    # Headers to look like a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        # Fetch the page
        print(f"   📡 Fetching page...")
        response = requests.get(page_info['url'], headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"   ✅ Got {len(response.text)} characters")
        
        # Save for debugging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = f"./storage/json_debug_page_{page_number}_{timestamp}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"   💾 Saved to {debug_file}")
        
        # Extract JSON data
        print(f"   🔍 Extracting JSON data...")
        notion_data = extract_json_from_html(response.text)
        
        if notion_data:
            print(f"   ✅ Found Notion data structure")
            
            # Extract LinkedIn links from the JSON
            links = extract_links_from_notion_data(notion_data, page_info['url'], limit=10)
            
            # Add metadata
            for i, link in enumerate(links, 1):
                link["page_number"] = page_number
                link["page_name"] = page_info['name']
                link["link_number"] = i
                link["extracted_at"] = datetime.now().isoformat()
            
            print(f"   ✅ Extracted {len(links)} LinkedIn links from JSON")
            return links
        else:
            print(f"   ❌ Could not extract Notion JSON data")
            return []
            
    except Exception as e:
        print(f"   ❌ Error scraping page: {e}")
        return []

def main():
    """Main function."""
    print("🎯 NOTION JSON EXTRACTOR")
    print("📅 Extracting LinkedIn links from Notion's JSON data")
    print("=" * 60)
    
    os.makedirs("./storage", exist_ok=True)
    
    all_links = []
    
    for i, page_info in enumerate(NOTION_PAGES, 1):
        links = scrape_page_for_json(page_info, i)
        all_links.extend(links)
        
        # Be respectful - wait between pages
        if i < len(NOTION_PAGES):
            print(f"   ⏱️  Waiting 2 seconds...")
            import time
            time.sleep(2)
    
    # Save results
    if all_links:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"./storage/notion_json_links_{timestamp}.csv"
        
        fieldnames = [
            "page_number", "page_name", "link_number", "url", 
            "anchor_text", "row_context", "source_page_url", 
            "extracted_at", "captured_at", "source", "block_id"
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
        for i, link in enumerate(all_links[:5], 1):
            print(f"   {i}. {link['url']}")
            print(f"      From: {link['page_name']}")
            
    else:
        print(f"\n❌ No links extracted from any page")

if __name__ == "__main__":
    main()