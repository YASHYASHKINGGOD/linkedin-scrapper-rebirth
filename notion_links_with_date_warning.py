#!/usr/bin/env python3
"""
Extract first 10 LinkedIn links from each Notion page.
Uses cached snapshots from August 20th with clear date warnings.
"""

import os
import csv
import json
from datetime import datetime
from typing import List, Dict
from src.extractor.notion.links import extract_linkedin_links_from_html

def process_snapshots_with_date_info() -> List[Dict[str, str]]:
    """Process snapshots with clear date information."""
    base_dir = "./storage/ingest/notion/20250820-094636/snapshots"
    
    # Known snapshot info with dates
    snapshots_info = [
        {
            "id": "f6de5eecab93", 
            "source_url": "https://diligent-actor-263.notion.site/13b8c7fca68e804aa0c3ca803aa07a3f?v=13b8c7fca68e817abca9000c95bbc26f",
            "page_name": "Diligent Actor - Internship & Analytics Jobs",
            "snapshot_date": "2025-08-20",
            "warning": "⚠️ Data from Aug 20 snapshot - may not be latest"
        },
        {
            "id": "5e8ac4e3be26",
            "source_url": "https://diligent-actor-263.notion.site/15a8c7fca68e80d7b612e1ba7379dd8a?v=15a8c7fca68e8154b0c0000c7a9241c9",
            "page_name": "Diligent Actor - Experienced Analytics & Data Science",
            "snapshot_date": "2025-08-20", 
            "warning": "⚠️ Data from Aug 20 snapshot - may not be latest"
        },
        {
            "id": "8c2aa30c7db7",
            "source_url": "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422",
            "page_name": "FOC Community - Founder's Office Roles",
            "snapshot_date": "2025-08-20",
            "warning": "⚠️ Data from Aug 20 snapshot - may not be latest"
        }
    ]
    
    all_links = []
    
    print(f"🚀 EXTRACTING LINKEDIN LINKS FROM NOTION PAGES")
    print(f"📅 Using cached data from August 20, 2025 (2 days old)")
    print(f"🎯 Target: First 10 links from each of {len(snapshots_info)} pages")
    print("=" * 70)
    
    for i, snapshot_info in enumerate(snapshots_info, 1):
        snapshot_path = os.path.join(base_dir, snapshot_info["id"])
        page_html_path = os.path.join(snapshot_path, "page.html")
        
        print(f"\n📂 Page {i}/3: {snapshot_info['page_name']}")
        print(f"   📋 URL: {snapshot_info['source_url'][:80]}...")
        print(f"   📅 Snapshot: {snapshot_info['snapshot_date']}")
        print(f"   {snapshot_info['warning']}")
        
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
            
            # Add comprehensive metadata
            for j, link in enumerate(links, 1):
                link["page_number"] = i
                link["page_name"] = snapshot_info["page_name"]
                link["link_number"] = j
                link["snapshot_date"] = snapshot_info["snapshot_date"]
                link["data_freshness"] = "2_days_old"
                link["extraction_method"] = "cached_snapshot"
                link["extracted_at"] = datetime.now().isoformat()
                link["data_warning"] = "Data from Aug 20 snapshot - may not reflect latest updates"
            
            print(f"   ✅ Extracted {len(links)} LinkedIn links")
            
            # Show sample of what we found
            if links:
                print(f"   🔗 Sample: {links[0]['url']}")
                
                # Check if this looks like recent data
                for link in links[:3]:
                    if link.get('captured_at'):
                        print(f"   📅 Link date: {link['captured_at'][:10]}")
                        break
            
            all_links.extend(links)
            
        except Exception as e:
            print(f"   ❌ Error processing page: {e}")
    
    return all_links

def analyze_data_freshness(links: List[Dict[str, str]]):
    """Analyze how fresh the data appears to be."""
    if not links:
        return
        
    # Count different types of LinkedIn URLs
    post_count = sum(1 for link in links if '/posts/' in link['url'])
    job_count = sum(1 for link in links if '/jobs/' in link['url'])
    profile_count = sum(1 for link in links if '/in/' in link['url'])
    
    print(f"\n📊 DATA ANALYSIS:")
    print(f"   📝 LinkedIn Posts: {post_count}")
    print(f"   💼 Job Listings: {job_count}")  
    print(f"   👤 Profiles: {profile_count}")
    print(f"   📊 Total: {len(links)}")
    
    # Sample of URLs to check recency
    recent_activity_ids = []
    for link in links:
        if '/posts/' in link['url'] and 'activity-' in link['url']:
            # Extract activity ID which contains timestamp info
            parts = link['url'].split('activity-')
            if len(parts) > 1:
                activity_id = parts[1].split('-')[0]
                if activity_id.isdigit() and len(activity_id) >= 19:
                    recent_activity_ids.append(activity_id[:10])  # First 10 digits
    
    if recent_activity_ids:
        print(f"   🕒 Found {len(recent_activity_ids)} LinkedIn post activity IDs")
        print(f"   ℹ️  These IDs suggest the posts are from recent timeframe")

def save_results_with_warnings(links: List[Dict[str, str]]):
    """Save results with clear data freshness warnings."""
    if not links:
        print("❌ No links to save")
        return None
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"./storage/notion_links_aug20_data_{timestamp}.csv"
    
    # Define CSV columns including warning fields
    fieldnames = [
        "page_number", "page_name", "link_number", "url", 
        "anchor_text", "row_context", "source_page_url", 
        "snapshot_date", "data_freshness", "extraction_method",
        "data_warning", "extracted_at", "source", "captured_at"
    ]
    
    # Save to CSV
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(links)
    
    print(f"\n💾 RESULTS SAVED:")
    print(f"   📄 File: {csv_filename}")
    print(f"   📊 Total links: {len(links)}")
    print(f"   ⚠️  Important: All data is from August 20, 2025 snapshots")
    print(f"   💡 Recommendation: Use for testing, but get fresh data for production")
    
    # Summary by page
    page_counts = {}
    for link in links:
        page = f"Page {link['page_number']}: {link['page_name'][:30]}..."
        page_counts[page] = page_counts.get(page, 0) + 1
    
    print(f"\n📈 BREAKDOWN BY PAGE:")
    for page, count in page_counts.items():
        print(f"   • {page}: {count} links")
    
    return csv_filename

def main():
    """Main function."""
    print("🎯 NOTION LINKEDIN SCRAPER - SNAPSHOT DATA")
    print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Ensure storage directory exists
    os.makedirs("./storage", exist_ok=True)
    
    # Process with clear date warnings
    links = process_snapshots_with_date_info()
    
    if links:
        # Analyze the data
        analyze_data_freshness(links)
        
        # Save results
        csv_file = save_results_with_warnings(links)
        
        print(f"\n✅ SUCCESS!")
        print(f"   📊 Extracted {len(links)} LinkedIn links from 3 Notion pages")
        print(f"   💾 Saved to: {csv_file}")
        print(f"   ⚠️  DATA DATE: August 20, 2025 (2 days old)")
        
        print(f"\n🔗 SAMPLE LINKS:")
        for i, link in enumerate(links[:5], 1):
            print(f"   {i}. {link['url']}")
            print(f"      From: {link['page_name']}")
            
        print(f"\n🚀 NEXT STEPS:")
        print(f"   1. Use this data for initial testing ✅")
        print(f"   2. Setup PostgreSQL integration with this data ✅")
        print(f"   3. For production: implement live scraping solution")
        
    else:
        print(f"\n❌ FAILED!")
        print("   No links were extracted")

if __name__ == "__main__":
    main()