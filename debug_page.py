#!/usr/bin/env python3
"""
Debug script to see what elements are available on the LinkedIn page
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

def debug_page():
    # Setup Chrome driver
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    wait = WebDriverWait(driver, 20)
    
    try:
        # Load config for login
        with open("config.json", "r") as f:
            config = json.load(f)
        
        print("🔑 Logging into LinkedIn...")
        driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        
        user = wait.until(EC.presence_of_element_located((By.ID, "username")))
        pw = wait.until(EC.presence_of_element_located((By.ID, "password")))
        
        creds = config["linkedin_credentials"]
        user.send_keys(creds["email"])
        pw.send_keys(creds["password"])
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)
        
        print("✅ Login successful, navigating to post...")
        url = "https://www.linkedin.com/posts/rashmi-p-a83a28104_wearehiring-productmanager-productmanagement-activity-7366497243979309057-DelG?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
        driver.get(url)
        time.sleep(3)
        
        print("🔍 Looking for elements...")
        
        # Check for various article selectors
        selectors_to_check = [
            "article",
            "article[data-activity-urn]", 
            "article.main-feed-activity-card",
            ".feed-shared-update-v2",
            ".main-feed-activity-card",
            "[data-test-id]",
            "[data-test-id*='main-feed']",
            "[data-test-id='main-feed-activity-card__entity-lockup']",
            "[data-test-id='main-feed-activity-card__commentary']"
        ]
        
        for selector in selectors_to_check:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"📊 {selector}: {len(elements)} elements found")
            if elements:
                for i, el in enumerate(elements[:2]):  # Show first 2 elements
                    tag = el.tag_name
                    class_attr = el.get_attribute("class") or ""
                    data_test_id = el.get_attribute("data-test-id") or ""
                    text_preview = (el.text or "")[:100] + "..." if len(el.text or "") > 100 else el.text or ""
                    print(f"  [{i}] {tag}, class='{class_attr[:50]}...', data-test-id='{data_test_id}', text='{text_preview}'")
        
        print("\n🔍 Looking for author-related elements...")
        author_selectors = [
            "a[data-tracking-control-name]",
            "a[data-tracking-control-name*='actor-name']",
            "a[data-tracking-control-name='public_post_feed-actor-name']",
            "a[href*='/in/']",
            "p.text-color-text-low-emphasis"
        ]
        
        for selector in author_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"📊 {selector}: {len(elements)} elements found")
            if elements:
                for i, el in enumerate(elements[:2]):
                    text = (el.text or "").strip()
                    href = el.get_attribute("href") or ""
                    print(f"  [{i}] text='{text}', href='{href[:50]}...'")
        
        print("\n🔍 Looking for content elements...")
        content_selectors = [
            "p.attributed-text-segment-list__content",
            ".attributed-text-segment-list__content",
            "[data-test-id='main-feed-activity-card__commentary']",
            "p[data-test-id='main-feed-activity-card__commentary']"
        ]
        
        for selector in content_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"📊 {selector}: {len(elements)} elements found")
            if elements:
                for i, el in enumerate(elements[:2]):
                    text_preview = (el.text or "")[:100] + "..." if len(el.text or "") > 100 else el.text or ""
                    print(f"  [{i}] text='{text_preview}'")
        
        print("\n🔍 Looking for comment elements...")
        comment_selectors = [
            "section.comment",
            ".comment",
            "a.comment__author",
            "p.comment__text"
        ]
        
        for selector in comment_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"📊 {selector}: {len(elements)} elements found")
        
        print("\n✅ Debug complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_page()
