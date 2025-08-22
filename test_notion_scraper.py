#!/usr/bin/env python3
"""
Test script to scrape first 10 LinkedIn links from each Notion page and save to CSV.
"""

import csv
import json
from datetime import datetime
from typing import List, Dict
from src.extractor.notion import extract_linkedin_links_from_notion_page

# The 3 Notion pages from the previous run
NOTION_PAGES = [
    "https://diligent-actor-263.notion.site/13b8c7fca68e804aa0c3ca803aa07a3f?v=13b8c7fca68e817abca9000c95bbc26f",
    "https://diligent-actor-263.notion.site/15a8c7fca68e80d7b612e1ba7379dd8a?v=15a8c7fca68e8154b0c0000c7a9241c9", 
    "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422"
]

def scrape_all_pages(limit_per_page: int = 10) -> List[Dict[str, str]]:
    """Scrape LinkedIn links from all Notion pages."""
    all_links = []
    
    for i, page_url in enumerate(NOTION_PAGES, 1):
        print(f"\n🔍 Scraping page {i}/3: {page_url}")
        
        try:
            links = extract_linkedin_links_from_notion_page(page_url, limit=limit_per_page)
            print(f"   ✅ Found {len(links)} LinkedIn links")
            
            # Add metadata
            for link in links:
                link["page_number"] = i
                link["scraped_at"] = datetime.now().isoformat()
            
            all_links.extend(links)
            
        except Exception as e:
            print(f"   ❌ Error scraping page {i}: {e}")
    
    return all_links

def save_to_csv(links: List[Dict[str, str]], filename: str):
    """Save links to CSV file."""
    if not links:
        print("No links to save")
        return
    
    fieldnames = [
        "page_number", "url", "source", "source_page_url", 
        "anchor_text", "row_context", "scraped_at"
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(links)
    
    print(f"\n💾 Saved {len(links)} links to {filename}")

def main():
    """Main function to run the test scraper."""
    print("🚀 Starting Notion LinkedIn scraper test...")
    print(f"📋 Will scrape first 10 links from {len(NOTION_PAGES)} Notion pages")
    
    # Scrape all pages
    all_links = scrape_all_pages(limit_per_page=10)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"./storage/notion_linkedin_links_test_{timestamp}.csv"
    json_filename = f"./storage/notion_linkedin_links_test_{timestamp}.json"
    
    # Ensure storage directory exists
    import os
    os.makedirs("./storage", exist_ok=True)
    
    # Save results
    save_to_csv(all_links, csv_filename)
    
    # Also save as JSON for reference
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(all_links, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n📊 SUMMARY:")
    print(f"   Total links extracted: {len(all_links)}")
    print(f"   Pages scraped: {len(NOTION_PAGES)}")
    print(f"   CSV output: {csv_filename}")
    print(f"   JSON output: {json_filename}")
    
    # Preview first few links
    if all_links:
        print(f"\n🔗 Preview of first 3 links:")
        for i, link in enumerate(all_links[:3], 1):
            print(f"   {i}. {link['url']}")
            print(f"      Page: {link['page_number']}, Text: {link['anchor_text'][:50]}...")

if __name__ == "__main__":
    main()