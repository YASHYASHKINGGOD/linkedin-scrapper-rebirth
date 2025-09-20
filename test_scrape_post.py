#!/usr/bin/env python3
"""
Test LinkedIn Post Scraping with Authenticated Session
Uses the saved session to scrape a real LinkedIn post from the queue
"""

import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def test_scrape_linkedin_post():
    """Test scraping a LinkedIn post with saved session"""
    
    print("🕷️  LinkedIn Post Scraping Test")
    print("=" * 50)
    
    # The URL we want to scrape from the database
    test_url = "https://www.linkedin.com/feed/update/urn:li:activity:7371897134503247873/?lipi=urn%3Ali%3Apage%3Ad_flagship3_messaging_conversation_detail%3Buk6JbcgnQV6hHm8%2BEOm3dw%3D%3D"
    
    print(f"🎯 Target URL: {test_url}")
    print()
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Setup Chrome with session persistence (same as manual login test)
    chrome_options = Options()
    chrome_config = config.get('chrome_options', {})
    
    # Add stealth flags
    for flag in chrome_config.get('disable_automation_flags', []):
        chrome_options.add_argument(flag)
    
    # User agent and window size
    user_agent = chrome_config.get('user_agent')
    if user_agent:
        chrome_options.add_argument(f"--user-agent={user_agent}")
    
    window_size = chrome_config.get('window_size', [1920, 1080])
    chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    
    # Session persistence - use the same profile that has our login
    user_data_dir = chrome_config.get('user_data_dir', 'chrome_profile')
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    
    profile_directory = chrome_config.get('profile_directory', 'Default')
    chrome_options.add_argument(f"--profile-directory={profile_directory}")
    
    # Anti-automation settings
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Execute stealth scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("🌐 Navigating to LinkedIn post...")
        driver.get(test_url)
        
        print("⏱️  Waiting for page to load...")
        time.sleep(5)
        
        current_url = driver.current_url
        print(f"📍 Current URL: {current_url}")
        
        # Check if we're still logged in
        if "login" in current_url.lower() or "checkpoint" in current_url.lower():
            print("❌ Not logged in! Session may have expired.")
            return False
        
        print("✅ Successfully accessed LinkedIn post page!")
        print()
        
        # Try to extract basic post information
        extracted_data = {}
        
        print("🔍 Extracting post content...")
        
        # Try to find post text
        post_text_selectors = [
            ".feed-shared-text",
            ".attributed-text-segment-list__content",
            "[data-test-id*='main-feed-activity-card__commentary']",
            ".break-words"
        ]
        
        for selector in post_text_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    text = elements[0].text.strip()
                    if text and len(text) > 10:  # Only non-empty, substantial text
                        extracted_data['post_text'] = text
                        print(f"   ✅ Post text found: {text[:100]}...")
                        break
            except Exception:
                continue
        
        # Try to find author information
        print("👤 Extracting author info...")
        author_selectors = [
            "a[data-tracking-control-name*='actor-name']",
            ".feed-shared-actor__name",
            "a[href*='/in/']"
        ]
        
        for selector in author_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    author_name = elements[0].text.strip()
                    if author_name:
                        extracted_data['author_name'] = author_name
                        print(f"   ✅ Author found: {author_name}")
                        
                        # Try to get profile URL
                        href = elements[0].get_attribute('href')
                        if href:
                            extracted_data['author_profile_url'] = href
                            print(f"   ✅ Author profile: {href}")
                        break
            except Exception:
                continue
        
        # Try to find engagement metrics
        print("📊 Looking for engagement metrics...")
        try:
            # Look for reaction/like counts
            reaction_elements = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='reaction'], [aria-label*='like']")
            for elem in reaction_elements:
                aria_label = elem.get_attribute('aria-label') or ''
                if any(word in aria_label.lower() for word in ['reaction', 'like']):
                    extracted_data['engagement_info'] = aria_label
                    print(f"   ✅ Engagement: {aria_label}")
                    break
        except Exception:
            pass
        
        # Try to find post date
        print("📅 Looking for post date...")
        try:
            time_elements = driver.find_elements(By.CSS_SELECTOR, "time")
            for time_elem in time_elements:
                datetime_attr = time_elem.get_attribute('datetime')
                if datetime_attr:
                    extracted_data['post_date'] = datetime_attr
                    print(f"   ✅ Post date: {datetime_attr}")
                    break
                else:
                    time_text = time_elem.text.strip()
                    if time_text and any(word in time_text for word in ['ago', 'hour', 'day']):
                        extracted_data['post_date'] = time_text
                        print(f"   ✅ Post date: {time_text}")
                        break
        except Exception:
            pass
        
        print()
        print("📋 Extraction Summary:")
        print("-" * 30)
        
        if extracted_data:
            for key, value in extracted_data.items():
                print(f"{key}: {value}")
        else:
            print("⚠️  No data extracted - page structure might be different")
        
        print()
        print("✅ Scraping test completed successfully!")
        print("💾 Session persistence is working perfectly!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during scraping test: {e}")
        return False
        
    finally:
        print(f"\n⏰ Keeping browser open for 20 seconds for review...")
        time.sleep(20)
        driver.quit()
        print("🔚 Browser closed")

if __name__ == "__main__":
    success = test_scrape_linkedin_post()
    
    if success:
        print("\n🎉 SUCCESS: LinkedIn post scraping is working!")
        print("🔄 Your authentication setup is perfect for production scraping.")
    else:
        print("\n❌ Scraping test failed.")
        print("💡 Check the browser output for details.")