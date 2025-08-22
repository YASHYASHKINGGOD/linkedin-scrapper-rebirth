#!/usr/bin/env python3
"""
Debug script to check what HTML we get from Notion pages.
"""

from src.extractor.notion.client import NotionScraper

def debug_notion_page(url: str):
    """Debug what we get from a Notion page."""
    print(f"\n🔍 Debugging Notion page: {url}")
    
    with NotionScraper() as scraper:
        try:
            html_content = scraper.fetch_page(url)
            
            print(f"✅ Successfully fetched page")
            print(f"📄 HTML length: {len(html_content)} characters")
            
            # Save HTML for inspection
            filename = f"./storage/debug_notion_page.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"💾 Saved HTML to {filename}")
            
            # Check for common patterns
            linkedin_count = html_content.lower().count('linkedin')
            href_count = html_content.count('href=')
            
            print(f"🔗 Found 'linkedin' mentions: {linkedin_count}")
            print(f"🔗 Found href attributes: {href_count}")
            
            # Look for specific patterns
            if 'data-' in html_content:
                print("✅ Found data attributes (likely dynamic content)")
            if 'javascript' in html_content.lower():
                print("⚠️  Found JavaScript (content may be dynamically loaded)")
            if 'notion-' in html_content:
                print("✅ Found Notion-specific classes")
                
            # Show first 1000 chars
            print(f"\n📖 First 1000 characters of HTML:")
            print(html_content[:1000])
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Test with first Notion page
    test_url = "https://diligent-actor-263.notion.site/13b8c7fca68e804aa0c3ca803aa07a3f?v=13b8c7fca68e817abca9000c95bbc26f"
    debug_notion_page(test_url)