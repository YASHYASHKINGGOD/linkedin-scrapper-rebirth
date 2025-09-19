#!/usr/bin/env python3
"""
Display the CSV output in a formatted way
"""

import csv
import json

def display_post_csv():
    print("=" * 80)
    print("📄 LINKEDIN POST CSV OUTPUT")
    print("=" * 80)
    
    with open('outputs/linkedin_post_20250828_134525_post.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            print(f"🔗 POST URL:")
            print(f"   {row['post_url']}")
            print()
            
            print(f"👤 AUTHOR INFORMATION:")
            print(f"   Name: {row['post_author']}")
            print(f"   Title: {row['author_title']}")
            print(f"   Profile URL: {row['author_profile_url']}")
            print()
            
            print(f"📅 POST METADATA:")
            print(f"   Date Posted: {row['date_posted']}")
            print(f"   Comment Count: {row['comment_count']}")
            print(f"   Image URLs: {row['image_urls'] or 'None'}")
            print(f"   Scraped At: {row['scraped_at']}")
            print(f"   Scraper Version: {row['scraper_version']}")
            print()
            
            print(f"📝 POST TEXT:")
            post_text = row['post_text']
            # Format the post text nicely
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

def display_comments_csv():
    print("=" * 80)
    print("💬 LINKEDIN COMMENTS CSV OUTPUT")
    print("=" * 80)
    
    with open('outputs/linkedin_post_20250828_134525_comments.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        comments = list(reader)
        
        if comments:
            for i, comment in enumerate(comments, 1):
                print(f"COMMENT {i}:")
                print(f"   Commentor: {comment['commentor']}")
                print(f"   Title: {comment['commentor_title']}")
                print(f"   Text: {comment['comment_text']}")
                print()
        else:
            print("❌ No comments found in the CSV file")
            print("   (Comments section was not loaded during scraping)")

if __name__ == "__main__":
    display_post_csv()
    display_comments_csv()
