#!/usr/bin/env python3
"""
Test script to scrape just one Notion page for debugging.
"""

from src.extractor.notion import extract_linkedin_links_from_notion_page

def test_single_page():
    """Test scraping a single Notion page."""
    # Test with the FOC community page (smallest one)
    test_url = "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422"
    
    print(f"🚀 Testing single Notion page scraper...")
    print(f"📋 URL: {test_url}")
    
    try:
        links = extract_linkedin_links_from_notion_page(test_url, limit=5)
        
        print(f"\n📊 RESULTS:")
        print(f"   Total links found: {len(links)}")
        
        if links:
            print(f"\n🔗 Found links:")
            for i, link in enumerate(links, 1):
                print(f"   {i}. {link['url']}")
                print(f"      Text: {link['anchor_text'][:100]}")
                print(f"      Context: {link['row_context'][:150]}...")
                print()
        else:
            print("   No LinkedIn links found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_single_page()