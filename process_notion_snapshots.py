#!/usr/bin/env python3
"""
Process existing Notion snapshot HTML files to extract LinkedIn links.
"""

import os
import csv
import json
from datetime import datetime
from typing import List, Dict
from src.extractor.notion.links import extract_linkedin_links_from_html

def process_snapshot_directory(snapshot_dir: str, source_url: str = "unknown") -> List[Dict[str, str]]:
    """Process a snapshot directory and extract LinkedIn links."""
    page_html_path = os.path.join(snapshot_dir, "page.html")
    
    if not os.path.exists(page_html_path):
        print(f"   ❌ No page.html found in {snapshot_dir}")
        return []
    
    try:
        with open(page_html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        print(f"   📄 Loaded HTML: {len(html_content)} characters")
        
        # Extract links with higher limit since this is cached data
        links = extract_linkedin_links_from_html(html_content, source_url, limit=20)
        
        # Add snapshot metadata
        for link in links:
            link["extraction_method"] = "snapshot"
            link["snapshot_dir"] = snapshot_dir
        
        return links
        
    except Exception as e:
        print(f"   ❌ Error processing snapshot: {e}")
        return []

def process_all_snapshots() -> List[Dict[str, str]]:
    """Process all existing Notion snapshots."""
    base_dir = "./storage/ingest/notion/20250820-094636/snapshots"
    
    if not os.path.exists(base_dir):
        print(f"❌ Snapshot directory not found: {base_dir}")
        return []
    
    all_links = []
    snapshot_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    
    print(f"🔍 Found {len(snapshot_dirs)} snapshot directories")
    
    # Map known snapshot IDs to their source URLs from the run.json
    known_urls = [
        "https://diligent-actor-263.notion.site/13b8c7fca68e804aa0c3ca803aa07a3f?v=13b8c7fca68e817abca9000c95bbc26f",
        "https://diligent-actor-263.notion.site/15a8c7fca68e80d7b612e1ba7379dd8a?v=15a8c7fca68e8154b0c0000c7a9241c9",
        "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422"
    ]
    
    for i, snapshot_id in enumerate(snapshot_dirs):
        snapshot_path = os.path.join(base_dir, snapshot_id)
        source_url = known_urls[i] if i < len(known_urls) else "unknown"
        
        print(f"\n📂 Processing snapshot {i+1}/{len(snapshot_dirs)}: {snapshot_id}")
        print(f"   🔗 Source URL: {source_url}")
        
        links = process_snapshot_directory(snapshot_path, source_url)
        
        if links:
            print(f"   ✅ Found {len(links)} LinkedIn links")
            all_links.extend(links)
        else:
            print(f"   ⚠️  No LinkedIn links found")
    
    return all_links

def save_results(links: List[Dict[str, str]]):
    """Save results to CSV and JSON."""
    if not links:
        print("No links to save")
        return
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"./storage/notion_snapshot_links_{timestamp}.csv"
    json_filename = f"./storage/notion_snapshot_links_{timestamp}.json"
    
    # Prepare fieldnames
    fieldnames = [
        "url", "source", "source_page_url", "anchor_text", "row_context", 
        "captured_at", "extraction_method", "snapshot_dir"
    ]
    
    # Save to CSV
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(links)
    
    # Save to JSON
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(links, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 SAVED RESULTS:")
    print(f"   CSV: {csv_filename}")
    print(f"   JSON: {json_filename}")
    
    # Summary by source
    source_counts = {}
    for link in links:
        source = link.get('source_page_url', 'unknown')[:50] + '...'
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total links: {len(links)}")
    print(f"   Unique sources: {len(source_counts)}")
    
    for source, count in source_counts.items():
        print(f"   • {source}: {count} links")
    
    # Preview links
    print(f"\n🔗 PREVIEW (first 5 links):")
    for i, link in enumerate(links[:5], 1):
        print(f"   {i}. {link['url']}")
        print(f"      Text: {link['anchor_text'][:80]}...")
        if link['row_context']:
            print(f"      Context: {link['row_context'][:100]}...")

def main():
    """Main function."""
    print("🚀 Processing existing Notion snapshots...")
    
    # Ensure storage directory exists
    os.makedirs("./storage", exist_ok=True)
    
    # Process all snapshots
    all_links = process_all_snapshots()
    
    # Save results
    save_results(all_links)

if __name__ == "__main__":
    main()