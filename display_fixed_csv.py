#!/usr/bin/env python3
"""
Display the fixed CSV output in a formatted way
"""

import csv
import json

def display_fixed_csv():
    print("=" * 80)
    print("📄 FIXED LINKEDIN POST CSV OUTPUT - BUG FIXES APPLIED")
    print("=" * 80)
    
    with open('outputs/linkedin_post_20250828_135539.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            print(f"🔗 POST URL:")
            print(f"   {row['post_url']}")
            print()
            
            print(f"👤 AUTHOR INFORMATION:")
            print(f"   Name: {row['post_author']}")
            print(f"   Title: {row['author_title'] or '[NOT FOUND - Author title selector needs adjustment]'}")
            print(f"   Profile URL: {row['author_profile_url']}")
            print()
            
            print(f"📅 POST METADATA:")
            print(f"   Date Posted: {row['date_posted']}")
            print(f"   Comment Count: {row['comment_count']}")
            print(f"   Image URLs: {row['image_urls'] or 'None'}")
            print(f"   Scraped At: {row['scraped_at']}")
            print(f"   Scraper Version: {row['scraper_version']}")
            print()
            
            print(f"📝 POST TEXT (FIXED - No hashtags or comment contamination):")
            post_text = row['post_text']
            formatted_text = post_text.replace('\\n', '\n   ')
            print(f"   {formatted_text}")
            print()
            
            print(f"🔗 EXTERNAL LINKS ({len(row['links'].split('; ')) if row['links'] else 0} total):")
            if row['links']:
                links = row['links'].split('; ')
                for i, link in enumerate(links, 1):
                    if 'mailto:' in link:
                        print(f"   [{i:2d}] 📧 {link}")
                    elif 'linkedin.com/in/' in link:
                        print(f"   [{i:2d}] 👤 {link}")
                    elif 'linkedin.com/company/' in link:
                        print(f"   [{i:2d}] 🏢 {link}")
                    elif not link.startswith('https://www.linkedin.com'):
                        print(f"   [{i:2d}] 🌐 {link}")
                    else:
                        print(f"   [{i:2d}] 🔗 {link}")
            else:
                print("   None")
            print()
            
            print(f"💬 COMMENTS (NEW: JSON FORMAT in single CSV):")
            try:
                comments = json.loads(row['comments']) if row['comments'] else []
                if comments:
                    for i, comment in enumerate(comments, 1):
                        print(f"   Comment {i}:")
                        print(f"     Commentor: {comment.get('commentor', 'N/A')}")
                        print(f"     Comment: {comment.get('comment', 'N/A')}")
                        print()
                else:
                    print("   ❌ No comments found")
                    print("   (Comments section requires interaction to load)")
            except json.JSONDecodeError:
                print("   ❌ Invalid JSON in comments field")
            print()

if __name__ == "__main__":
    display_fixed_csv()
