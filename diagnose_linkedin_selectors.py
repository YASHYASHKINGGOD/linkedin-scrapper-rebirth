#!/usr/bin/env python3
"""
LinkedIn Selector Diagnostic Tool

This script opens the LinkedIn post, saves the HTML, and helps identify 
the correct CSS selectors for extracting post data.
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
from pathlib import Path
import re

def diagnose_linkedin_selectors():
    """Diagnose current LinkedIn post structure and selectors"""
    
    print("🔍 LinkedIn Selector Diagnostic Tool")
    print("=" * 50)
    
    # The URL we're having trouble with
    test_url = "https://www.linkedin.com/feed/update/urn:li:activity:7371897134503247873/?lipi=urn%3Ali%3Apage%3Ad_flagship3_messaging_conversation_detail%3Buk6JbcgnQV6hHm8%2BEOm3dw%3D%3D"
    
    # Load config for session persistence
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Setup Chrome with session persistence (same as working login)
    chrome_options = Options()
    chrome_config = config.get('chrome_options', {})
    
    # Add stealth flags
    for flag in chrome_config.get('disable_automation_flags', []):
        chrome_options.add_argument(flag)
    
    user_agent = chrome_config.get('user_agent')
    if user_agent:
        chrome_options.add_argument(f"--user-agent={user_agent}")
    
    window_size = chrome_config.get('window_size', [1920, 1080])
    chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    
    # CRITICAL: Use saved session
    user_data_dir = chrome_config.get('user_data_dir', 'chrome_profile')
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    
    profile_directory = chrome_config.get('profile_directory', 'Default')
    chrome_options.add_argument(f"--profile-directory={profile_directory}")
    
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Execute stealth scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"🌐 Navigating to LinkedIn post...")
        driver.get(test_url)
        
        print("⏱️  Waiting for page to load...")
        time.sleep(8)  # Extended wait for full content load
        
        current_url = driver.current_url
        print(f"📍 Current URL: {current_url}")
        
        # Check authentication
        if "login" in current_url.lower():
            print("❌ Not authenticated! Please run manual_login_test.py first.")
            return False
        
        print("✅ Successfully authenticated and on post page!")
        print()
        
        # Save full HTML for analysis
        html_content = driver.page_source
        html_file = Path("diagnosis_output.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"💾 Full HTML saved to: {html_file}")
        
        # Try to scroll and expand content
        print("📜 Scrolling and expanding content...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(2)
        
        # Look for "see more" buttons
        see_more_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='more'], button[aria-expanded='false']")
        for btn in see_more_buttons:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    print(f"🔄 Clicking expand button: {btn.get_attribute('aria-label')}")
                    btn.click()
                    time.sleep(2)
                    break
            except:
                continue
        
        print()
        print("🔍 DIAGNOSTIC ANALYSIS:")
        print("=" * 40)
        
        # Test current selectors and find alternatives
        diagnose_post_content(driver)
        diagnose_author_info(driver)
        diagnose_metadata(driver)
        diagnose_overall_structure(driver)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        return False
        
    finally:
        print(f"\n⏰ Keeping browser open for 15 seconds for manual inspection...")
        time.sleep(15)
        driver.quit()
        print("🔚 Browser closed")

def diagnose_post_content(driver):
    """Diagnose post content extraction"""
    print("\n📝 POST CONTENT ANALYSIS:")
    print("-" * 25)
    
    # Current selectors that are failing
    current_selectors = [
        "p.attributed-text-segment-list__content",
        ".attributed-text-segment-list__content",
        "[data-test-id='main-feed-activity-card__commentary'] .attributed-text-segment-list__content"
    ]
    
    # Alternative selectors to try
    alternative_selectors = [
        ".feed-shared-text",
        ".feed-shared-text .break-words",
        ".feed-shared-update-v2__description",
        ".feed-shared-update-v2__description .break-words",
        "[data-test-id*='main-feed-activity-card__commentary']",
        "[data-test-id*='commentary'] .break-words",
        ".attributed-text-segment-list__content",
        "div[dir='ltr'][data-test-id*='commentary']",
        ".update-components-text",
        "p[dir='ltr']"
    ]
    
    print("Current selectors (FAILING):")
    for selector in current_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        text_found = ""
        if elements:
            text_found = elements[0].text.strip()[:50] + "..." if elements[0].text.strip() else "EMPTY"
        print(f"  {selector}: {len(elements)} elements, text='{text_found}'")
    
    print("\nAlternative selectors to try:")
    for selector in alternative_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                for i, elem in enumerate(elements[:3]):  # Check first 3 elements
                    text = elem.text.strip()
                    if text and len(text) > 20:  # Only show substantial text
                        print(f"  ✅ {selector}[{i}]: {len(text)} chars - '{text[:60]}...'")
                        break
                else:
                    print(f"  ⚠️  {selector}: {len(elements)} elements but no substantial text")
            else:
                print(f"  ❌ {selector}: 0 elements")
        except Exception as e:
            print(f"  💥 {selector}: ERROR - {e}")

def diagnose_author_info(driver):
    """Diagnose author information extraction"""
    print("\n👤 AUTHOR INFO ANALYSIS:")
    print("-" * 20)
    
    # Current selectors
    current_author_selectors = [
        "a[data-tracking-control-name='public_post_feed-actor-name']",
        "a[href*='/in/']",
        "*[class*='entity-lockup'] a"
    ]
    
    current_title_selectors = [
        "p.text-color-text-low-emphasis",
        "[data-test-id='main-feed-activity-card__entity-lockup'] p"
    ]
    
    # Alternative selectors
    alternative_author_selectors = [
        ".feed-shared-actor__name",
        ".feed-shared-actor__name a",
        "a[data-tracking-control-name*='actor-name']",
        "span[dir='ltr'] strong",
        ".update-components-actor__name",
        ".entity-lockup__title a",
        "h3 a[href*='/in/']"
    ]
    
    alternative_title_selectors = [
        ".feed-shared-actor__description",
        ".feed-shared-actor__sub-description", 
        ".entity-lockup__subtitle",
        ".update-components-actor__description",
        "p.text-body-small",
        "div[data-test-id*='entity-lockup'] p"
    ]
    
    print("Current AUTHOR selectors:")
    for selector in current_author_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            text = elements[0].text.strip()
            href = elements[0].get_attribute('href') if elements[0].tag_name == 'a' else 'N/A'
            print(f"  ✅ {selector}: '{text}' -> {href}")
        else:
            print(f"  ❌ {selector}: 0 elements")
    
    print("\nAlternative AUTHOR selectors:")
    for selector in alternative_author_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                text = elements[0].text.strip()
                if text and len(text) > 2:
                    href = elements[0].get_attribute('href') if elements[0].tag_name == 'a' else 'N/A'
                    print(f"  ✅ {selector}: '{text}' -> {href}")
        except:
            continue
    
    print("\nCurrent TITLE selectors:")
    for selector in current_title_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            text = elements[0].text.strip()
            print(f"  {'✅' if text else '⚠️'} {selector}: '{text}'")
        else:
            print(f"  ❌ {selector}: 0 elements")
    
    print("\nAlternative TITLE selectors:")
    for selector in alternative_title_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                text = elements[0].text.strip()
                if text and not any(word in text.lower() for word in ['ago', 'hour', 'day', 'week']):
                    print(f"  ✅ {selector}: '{text}'")
        except:
            continue

def diagnose_metadata(driver):
    """Diagnose metadata extraction (date, etc.)"""
    print("\n📅 METADATA ANALYSIS:")
    print("-" * 15)
    
    current_time_selectors = [
        "time",
        "time[datetime]",
        "[data-test-id='main-feed-activity-card__entity-lockup'] time"
    ]
    
    alternative_time_selectors = [
        "time[datetime]",
        ".feed-shared-actor__sub-description time",
        ".update-components-actor__sub-description time",
        "span[aria-label*='ago']",
        "*[class*='timestamp']",
        ".text-body-small time",
        "[data-test-id*='entity-lockup'] time"
    ]
    
    print("Current TIME selectors:")
    for selector in current_time_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            datetime_attr = elements[0].get_attribute('datetime')
            text = elements[0].text.strip()
            print(f"  ✅ {selector}: datetime='{datetime_attr}', text='{text}'")
        else:
            print(f"  ❌ {selector}: 0 elements")
    
    print("\nAlternative TIME selectors:")
    for selector in alternative_time_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                datetime_attr = elements[0].get_attribute('datetime')
                text = elements[0].text.strip()
                aria_label = elements[0].get_attribute('aria-label')
                if datetime_attr or text or aria_label:
                    print(f"  ✅ {selector}: datetime='{datetime_attr}', text='{text}', aria='{aria_label}'")
        except:
            continue

def diagnose_overall_structure(driver):
    """Diagnose overall page structure"""
    print("\n🏗️  OVERALL STRUCTURE ANALYSIS:")
    print("-" * 25)
    
    # Find main containers
    main_containers = [
        "article",
        ".main-feed-activity-card", 
        ".feed-shared-update-v2",
        ".update-components-update",
        "[data-test-id*='main-feed-activity-card']",
        "[data-activity-urn]"
    ]
    
    print("Main containers found:")
    for selector in main_containers:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            elem = elements[0]
            classes = elem.get_attribute('class')
            test_id = elem.get_attribute('data-test-id')
            urn = elem.get_attribute('data-activity-urn')
            print(f"  ✅ {selector}: class='{classes}' test-id='{test_id}' urn='{urn}'")
    
    # Check for data-test-id attributes (these are often most reliable)
    print("\nData-test-id attributes found:")
    test_id_elements = driver.find_elements(By.CSS_SELECTOR, "[data-test-id]")
    test_ids = set()
    for elem in test_id_elements[:20]:  # Limit output
        test_id = elem.get_attribute('data-test-id')
        if test_id and 'feed' in test_id.lower():
            test_ids.add(test_id)
    
    for test_id in sorted(test_ids):
        print(f"  📋 data-test-id='{test_id}'")

if __name__ == "__main__":
    success = diagnose_linkedin_selectors()
    
    if success:
        print("\n✅ Diagnosis completed!")
        print("📊 Check diagnosis_output.html for full HTML structure")
        print("🔧 Use the analysis above to update scraper selectors")
    else:
        print("\n❌ Diagnosis failed!")