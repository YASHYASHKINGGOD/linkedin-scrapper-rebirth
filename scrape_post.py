#!/usr/bin/env python3
"""
LinkedIn Post Scraper - Single Post Test
Simple script to scrape a single LinkedIn post and save results to JSON or CSV
"""

import sys
import json
import argparse
from selenium_scraper import LinkedInSeleniumScraper

def scrape_single_post(post_url: str, output_format: str = "json", single_csv: bool = False) -> bool:
    """
    Scrape a single LinkedIn post and save results
    
    Args:
        post_url: LinkedIn post URL to scrape
        output_format: Output format - "json", "csv", or "both"
        single_csv: If True and format includes CSV, save as single CSV with comments as JSON
        
    Returns:
        True if successful, False otherwise
    """
    print(f"🔍 Scraping LinkedIn post: {post_url}")
    print(f"📊 Output format: {output_format.upper()}")
    if single_csv and output_format in ['csv', 'both']:
        print(f"📄 Single CSV mode: ON (comments as JSON column)")
    print("=" * 80)
    
    try:
        with LinkedInSeleniumScraper() as scraper:
            # Initialize driver
            print("🚀 Initializing Chrome driver...")
            if not scraper.initialize_driver():
                print("❌ Failed to initialize driver")
                return False
            
            # Login
            print("🔑 Logging into LinkedIn...")
            success, message = scraper.login()
            if not success:
                print(f"❌ Login failed: {message}")
                return False
            print("✅ Successfully logged in")
            
            # Scrape the post
            print("📥 Scraping post data...")
            post_data = scraper.scrape_post(post_url)
            
            # Save results based on format
            print("💾 Saving results...")
            saved_files = []
            
            if output_format in ["json", "both"]:
                json_file = scraper.save_post_data(post_data)
                saved_files.append(f"JSON: {json_file}")
            
            if output_format in ["csv", "both"]:
                if single_csv:
                    single_csv_file, _ = scraper.save_post_data_csv(post_data, single_file=True)
                    saved_files.append(f"Single CSV: {single_csv_file}")
                else:
                    post_csv, comments_csv = scraper.save_post_data_csv(post_data, single_file=False)
                    saved_files.append(f"CSV Post: {post_csv}")
                    saved_files.append(f"CSV Comments: {comments_csv}")
            
            # Print summary
            print("\n🎉 SCRAPING COMPLETED SUCCESSFULLY!")
            print("=" * 50)
            for file_info in saved_files:
                print(f"📄 {file_info}")
            
            print("\n📊 DATA SUMMARY:")
            print(f"📝 Post author: {post_data.get('post_author', 'N/A')}")
            print(f"📅 Date posted: {post_data.get('date_posted', 'N/A')}")
            print(f"💬 Comments found: {len(post_data.get('comments', []))}")
            print(f"🖼️  Images found: {len(post_data.get('images', []))}")
            print(f"🔗 External links: {len(post_data.get('external_links', []))}")
            
            # Show first few lines of post text
            post_text = post_data.get('post_text', '')
            if post_text:
                preview = post_text[:150] + '...' if len(post_text) > 150 else post_text
                print(f"📖 Post preview: {preview}")
            
            return True
            
    except Exception as e:
        print(f"❌ Scraping failed with error: {e}")
        return False

def main():
    """Main function to handle command line arguments and run scraping"""
    
    # Default URL
    default_url = "https://www.linkedin.com/posts/neelkdoshi_productmanagement-internship-hiring-activity-7171804770750394372-HGMp?utm_source=share&utm_medium=member_desktop"
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="LinkedIn Post Scraper - Extract data from LinkedIn posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s https://www.linkedin.com/posts/username_activity-123
  %(prog)s --format csv https://www.linkedin.com/posts/username_activity-123
  %(prog)s --format both https://www.linkedin.com/posts/username_activity-123
  %(prog)s  # Uses default test URL
        """
    )
    
    parser.add_argument(
        "url",
        nargs="?",
        default=default_url,
        help="LinkedIn post URL to scrape (default: test URL)"
    )
    
    parser.add_argument(
        "--format", "-f",
        choices=["json", "csv", "both"],
        default="json",
        help="Output format: json, csv, or both (default: json)"
    )
    
    parser.add_argument(
        "--single-csv",
        action="store_true",
        dest="single_csv",
        help="Save CSV as single file with comments as JSON column (only applies when format includes csv)"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    post_url = args.url
    output_format = args.format
    
    # Show what we're using
    if post_url == default_url:
        print("Using default test URL...")
    
    # Validate URL
    if not post_url.startswith('https://www.linkedin.com/posts/'):
        print("❌ Error: Please provide a valid LinkedIn post URL")
        print("Example: https://www.linkedin.com/posts/username_activity-123456789")
        sys.exit(1)
    
    # Run scraping
    success = scrape_single_post(post_url, output_format, args.single_csv)
    
    if success:
        print(f"\n✅ All done! Check the outputs/ folder for your {output_format.upper()} data.")
        
        # Show usage hints for CSV
        if output_format in ["csv", "both"]:
            print("\n📊 CSV Files Generated:")
            print("  - *_post.csv: Main post data (one row)")
            print("  - *_comments.csv: Comments data (one row per comment)")
        
        sys.exit(0)
    else:
        print("\n❌ Scraping failed. Check scraper.log for detailed error information.")
        sys.exit(1)

if __name__ == "__main__":
    main()
