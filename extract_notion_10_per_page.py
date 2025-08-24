#!/usr/bin/env python3
"""
Extract first 10 LinkedIn links from each of the 3 Notion pages (30 total) for testing.
"""

import os
import csv
import json
from datetime import datetime
from typing import List, Dict
from src.extractor.notion.links import extract_linkedin_links_from_html

def process_snapshots_limited() -> List[Dict[str, str]]:
    """Process snapshots but limit to 10 links per page."""
    base_dir = "./storage/ingest/notion/20250820-094636/snapshots"
    
    # Snapshot info
    snapshots_info = [
        {
            "id": "f6de5eecab93", 
            "source_url": "https://diligent-actor-263.notion.site/13b8c7fca68e804aa0c3ca803aa07a3f?v=13b8c7fca68e817abca9000c95bbc26f",
            "page_name": "Diligent Actor Page 1"
        },
        {
            "id": "5e8ac4e3be26",
            "source_url": "https://diligent-actor-263.notion.site/15a8c7fca68e80d7b612e1ba7379dd8a?v=15a8c7fca68e8154b0c0000c7a9241c9",
            "page_name": "Diligent Actor Page 2"
        },
        {
            "id": "8c2aa30c7db7",
            "source_url": "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422",
            "page_name": "FOC Community"
        }
    ]
    
    all_links = []
    
    print(f"🚀 Extracting first 10 LinkedIn links from each of {len(snapshots_info)} Notion pages")
    
    for i, snapshot_info in enumerate(snapshots_info, 1):
        snapshot_path = os.path.join(base_dir, snapshot_info["id"])
        page_html_path = os.path.join(snapshot_path, "page.html")
        
        print(f"\n📂 Page {i}/3: {snapshot_info['page_name']}")
        print(f"   🔗 URL: {snapshot_info['source_url'][:80]}...")
        
        if not os.path.exists(page_html_path):
            print(f"   ❌ No HTML file found")
            continue
        
        try:
            with open(page_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Extract exactly 10 links from this page
            links = extract_linkedin_links_from_html(
                html_content, 
                snapshot_info["source_url"], 
                limit=10
            )
            
            # Add metadata
            for j, link in enumerate(links, 1):
                link["page_number"] = i
                link["page_name"] = snapshot_info["page_name"]
                link["link_number"] = j
                link["extracted_at"] = datetime.now().isoformat()
            
            print(f"   ✅ Extracted {len(links)} LinkedIn links")
            all_links.extend(links)
            
        except Exception as e:
            print(f"   ❌ Error processing page: {e}")
    
    return all_links

def save_test_results(links: List[Dict[str, str]]):
    """Save the test results to CSV."""
    if not links:
        print("❌ No links to save")
        return
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"./storage/notion_test_10_per_page_{timestamp}.csv"
    
    # Define CSV columns - include all fields that might be present
    fieldnames = [
        "page_number", "page_name", "link_number", "url", 
        "anchor_text", "row_context", "source_page_url", "extracted_at",
        "source", "captured_at"  # Additional fields from extraction function
    ]
    
    # Save to CSV
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(links)
    
    print(f"\n💾 RESULTS SAVED:")
    print(f"   📄 CSV file: {csv_filename}")
    print(f"   📊 Total links: {len(links)}")
    
    # Summary by page
    page_counts = {}
    for link in links:
        page = f"Page {link['page_number']}: {link['page_name']}"
        page_counts[page] = page_counts.get(page, 0) + 1
    
    print(f"\n📈 BREAKDOWN BY PAGE:")
    for page, count in page_counts.items():
        print(f"   • {page}: {count} links")
    
    # Sample of extracted links
    print(f"\n🔗 SAMPLE LINKS (first 3 from each page):")
    current_page = 0
    page_link_count = 0
    
    for link in links:
        if link['page_number'] != current_page:
            current_page = link['page_number']
            page_link_count = 0
            print(f"\n   📋 {link['page_name']}:")
        
        if page_link_count < 3:
            print(f"      {link['link_number']}. {link['url']}")
            if link['anchor_text']:
                print(f"         Text: {link['anchor_text'][:60]}...")
        page_link_count += 1
    
    return csv_filename

def main():
    """Main function."""
    print("🎯 NOTION LINKEDIN SCRAPER - TEST MODE")
    print("📋 Extracting first 10 links from each of 3 Notion pages")
    
    # Ensure storage directory exists
    os.makedirs("./storage", exist_ok=True)
    
    # Process with limits
    links = process_snapshots_limited()
    
    # Save and display results
    if links:
        csv_file = save_test_results(links)
        
        print(f"\n✅ SUCCESS!")
        print(f"   📊 Extracted {len(links)} total links (10 per page)")
        print(f"   💾 Saved to: {csv_file}")
        print(f"\n🔄 Ready for PostgreSQL integration once testing is complete!")
    else:
        print(f"\n❌ FAILED!")
        print("   No links were extracted")

if __name__ == "__main__":
    main()