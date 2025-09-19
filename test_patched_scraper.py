#!/usr/bin/env python3
"""
Test script for the patched LinkedIn scraper
"""

import os
import time
from patched_scraper import LinkedInSeleniumScraper

def test_patched_scraper():
    """Test the patched scraper with the provided LinkedIn URL"""
    url = "https://www.linkedin.com/posts/rashmi-p-a83a28104_wearehiring-productmanager-productmanagement-activity-7366497243979309057-DelG?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
    
    if not os.path.exists("config.json"):
        print("❌ config.json missing")
        return False
    
    print("🚀 Starting patched LinkedIn scraper test")
    print(f"📍 URL: {url}")
    print("=" * 80)
    
    start_time = time.time()
    
    try:
        scraper = LinkedInSeleniumScraper()
        
        print("🔧 Initializing driver...")
        scraper.initialize_driver()
        
        print("🔑 Logging in...")
        ok, msg = scraper.login()
        if not ok:
            print(f"❌ Login failed: {msg}")
            return False
        print("✅ Login successful")
        
        print("📊 Scraping post data...")
        data = scraper.scrape_post(url)
        
        print("💾 Saving to CSV...")
        path = scraper.save_post_data_csv(data)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"\n🎉 SUCCESS! Data saved to: {path}")
        print("=" * 50)
        print("📊 DATA SUMMARY:")
        print(f"📝 Post author: {data.get('post_author', 'N/A')}")
        print(f"👤 Author title: {data.get('author_title', 'N/A')}")
        print(f"📅 Date posted: {data.get('date_posted', 'N/A')}")
        print(f"💬 Comments found: {len(data.get('comments', []))}")
        print(f"🖼️  Images found: {len(data.get('images', []))}")
        print(f"🔗 Links found: {len(data.get('links', []))}")
        
        # Show post text preview
        post_text = data.get('post_text', '')
        if post_text:
            preview = post_text[:200] + '...' if len(post_text) > 200 else post_text
            print(f"📖 Post preview: {preview}")
        else:
            print("📖 Post preview: [No content extracted]")
        
        # Show links
        links = data.get('links', [])
        if links:
            print(f"🔗 Links: {'; '.join(links)}")
        
        # Show some comments
        comments = data.get('comments', [])
        if comments:
            print(f"\n💬 Sample comments:")
            for i, comment in enumerate(comments[:3], 1):
                commentor = comment.get('commentor', 'Unknown')
                text = comment.get('comment_text', '')[:100] + '...' if len(comment.get('comment_text', '')) > 100 else comment.get('comment_text', '')
                print(f"  {i}. {commentor}: {text}")
        
        print(f"\n⏱️  Execution time: {execution_time:.2f} seconds")
        
        scraper.close_driver()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_patched_scraper()
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!")
