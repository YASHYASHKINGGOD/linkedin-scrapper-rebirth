#!/usr/bin/env python3
"""
Batch LinkedIn Post Scraper
Processes multiple LinkedIn posts and saves results to individual CSV files
"""

import json
import time
from pathlib import Path
from datetime import datetime
import csv
from linkedin_scraper_fixed_v2 import LinkedInSeleniumScraper

def batch_scrape_posts(urls, config_path="config.json", output_dir="outputs"):
    """
    Scrape multiple LinkedIn posts in batch
    """
    print(f"🚀 Starting batch scrape of {len(urls)} posts...")
    
    # Initialize scraper
    scraper = LinkedInSeleniumScraper(config_path=config_path)
    scraper.initialize_driver()
    
    # Login once for all posts
    ok, msg = scraper.login()
    if not ok:
        print(f"❌ Login failed: {msg}")
        scraper.close_driver()
        return []
    
    print("✅ Login successful - starting batch processing...")
    
    results = []
    failed_urls = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n📝 Processing post {i}/{len(urls)}")
        print(f"URL: {url}")
        
        try:
            # Scrape the post
            start_time = time.time()
            data = scraper.scrape_post(url)
            
            # Save individual CSV
            csv_file, _ = scraper.save_csvs(data)
            
            # Track results
            processing_time = time.time() - start_time
            result = {
                "url": url,
                "status": "success",
                "csv_file": csv_file,
                "processing_time": f"{processing_time:.2f}s",
                "post_author": data.get('post_author', 'N/A'),
                "comment_count": len(data.get('comments', [])),
                "scraped_at": data.get('scraped_at')
            }
            results.append(result)
            
            print(f"✅ Success: {csv_file}")
            print(f"📊 Author: {data.get('post_author', 'N/A')}, Comments: {len(data.get('comments', []))}, Time: {processing_time:.2f}s")
            
            # Small delay between requests
            if i < len(urls):  # Don't delay after last URL
                delay = 3
                print(f"⏱️  Waiting {delay}s before next post...")
                time.sleep(delay)
            
        except Exception as e:
            print(f"❌ Failed to scrape: {str(e)}")
            failed_urls.append({"url": url, "error": str(e)})
            results.append({
                "url": url,
                "status": "failed",
                "error": str(e),
                "scraped_at": datetime.now().isoformat()
            })
            continue
    
    # Close driver
    scraper.close_driver()
    
    # Create summary report
    create_batch_summary(results, failed_urls, output_dir)
    
    return results

def create_batch_summary(results, failed_urls, output_dir):
    """
    Create a summary report of the batch processing
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = output_path / f"batch_summary_{timestamp}.json"
    
    # Calculate stats
    successful = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") == "failed"]
    
    total_comments = sum(r.get("comment_count", 0) for r in successful)
    avg_processing_time = sum(float(r.get("processing_time", "0").replace("s", "")) for r in successful) / len(successful) if successful else 0
    
    summary = {
        "batch_summary": {
            "total_urls": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": f"{(len(successful)/len(results)*100):.1f}%" if results else "0%",
            "total_comments_extracted": total_comments,
            "average_processing_time": f"{avg_processing_time:.2f}s",
            "processed_at": datetime.now().isoformat()
        },
        "results": results,
        "failed_urls": failed_urls if failed_urls else []
    }
    
    # Save summary
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # Print summary to console
    print(f"\n{'='*60}")
    print(f"📊 BATCH PROCESSING SUMMARY")
    print(f"{'='*60}")
    print(f"Total URLs processed: {len(results)}")
    print(f"✅ Successful: {len(successful)} ({(len(successful)/len(results)*100):.1f}%)")
    print(f"❌ Failed: {len(failed)}")
    print(f"💬 Total comments extracted: {total_comments}")
    print(f"⏱️  Average processing time: {avg_processing_time:.2f}s")
    print(f"📄 Summary saved to: {summary_file}")
    
    if successful:
        print(f"\n📁 Individual CSV files saved:")
        for result in successful:
            print(f"   • {result.get('csv_file')}")
    
    if failed_urls:
        print(f"\n❌ Failed URLs:")
        for failed in failed_urls:
            print(f"   • {failed['url']} - {failed['error']}")

def main():
    # List of URLs to scrape
    urls = [
        "https://www.linkedin.com/posts/aarti-sharma-829939101_pharmahiring-productmanager-respiratoryportfolio-activity-7366345375827288065-gTTd?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/ramdev-saharan-213339151_productmanagement-hiring-startupjobs-activity-7366376046297817088-SoZQ?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/artika-upadhyay-44391915_were-hiring-product-manager-aproduct-activity-7366380148369043457-EpkX?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/manjusha-m-3b9009181_hiring-productmanagement-apm-activity-7366089082365493249-5MU8?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/snapeeds_hiring-productmanager-ai-activity-7366370506599526400-ASNZ?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/mohana-s-09134b275_retainiq-apply-for-associate-product-manager-activity-7366144939665129474-C4IM?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
    ]
    
    print(f"🎯 Batch LinkedIn Post Scraper")
    print(f"📋 Processing {len(urls)} LinkedIn posts...")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run batch scraping
    results = batch_scrape_posts(urls)
    
    print(f"\n🎉 Batch processing completed!")
    print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
