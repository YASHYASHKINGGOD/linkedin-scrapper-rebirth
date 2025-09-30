#!/usr/bin/env python3
"""
Test script to verify LinkedIn job description expansion functionality
"""

import os
import json
import logging
from src.scraper.linkedin_job_scraper import LinkedInJobScraperService
from playwright.sync_api import sync_playwright

# Enable debug logging to see expansion details
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_expansion_on_sample_job():
    """Test description expansion on a sample LinkedIn job URL"""
    
    # Sample LinkedIn job URL (replace with a real one for testing)
    test_job_url = "https://www.linkedin.com/jobs/view/4294002810/"  # Rakuten India job from the HTML sample
    
    # Load configuration
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error("config.json not found. Please create it with LinkedIn credentials.")
        return
    
    # Get credentials
    credentials = config.get('linkedin_credentials', {})
    email = credentials.get('email')
    password = credentials.get('password')
    
    if not email or not password:
        logger.error("LinkedIn credentials not found in config.json")
        return
        
    chrome_profile_dir = config.get('chrome_options', {}).get('user_data_dir', './chrome_profile')
    
    logger.info(f"🧪 Testing description expansion on: {test_job_url}")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=chrome_profile_dir,
            headless=False,  # Run with UI for debugging
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        scraper = LinkedInJobScraperService()
        
        try:
            # Check login status
            logger.info("🔍 Checking LinkedIn login status...")
            page.goto("https://www.linkedin.com", timeout=60000)
            page.wait_for_timeout(3000)
            
            if not scraper.check_login_status(page):
                logger.info("🔐 Not logged in, attempting login...")
                if not scraper.login_to_linkedin(page, email, password):
                    logger.error("❌ LinkedIn login failed")
                    return
            else:
                logger.info("✅ Already logged in!")
            
            # Navigate to the test job URL
            logger.info(f"🌐 Navigating to test job: {test_job_url}")
            page.goto(test_job_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            # Test the description extraction with expansion
            logger.info("🔬 Testing description extraction and expansion...")
            description = scraper._desc_text(page)
            
            if description:
                logger.info(f"✅ Description extracted successfully!")
                logger.info(f"📏 Final description length: {len(description)} characters")
                logger.info(f"🔤 First 200 characters: {description[:200]}...")
                
                # Check for common indicators of truncation
                if "..." in description or len(description) < 500:
                    logger.warning("⚠️  Description might still be truncated!")
                else:
                    logger.info("✅ Description appears to be fully expanded!")
                
                # Save the description to a file for manual inspection
                with open("test_description_output.txt", "w", encoding="utf-8") as f:
                    f.write(f"URL: {test_job_url}\n")
                    f.write(f"Length: {len(description)} characters\n")
                    f.write(f"Content:\n{description}")
                logger.info("📄 Description saved to test_description_output.txt")
            else:
                logger.error("❌ No description extracted!")
            
            # Take a screenshot for manual verification
            page.screenshot(path="test_expansion_screenshot.png", full_page=True)
            logger.info("📸 Screenshot saved to test_expansion_screenshot.png")
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
        finally:
            # Keep browser open for a moment to inspect manually
            logger.info("🔍 Keeping browser open for 10 seconds for manual inspection...")
            page.wait_for_timeout(10000)
            context.close()

if __name__ == "__main__":
    test_expansion_on_sample_job()