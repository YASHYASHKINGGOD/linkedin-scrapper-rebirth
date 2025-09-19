#!/usr/bin/env python3
"""
Debug script to find comment elements on LinkedIn page
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

def debug_comments():
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
        time.sleep(5)
        
        # Try to click on comments to load them
        print("🔍 Looking for comments button...")
        comments_buttons = [
            "[data-test-id='social-actions__comments']",
            "button[aria-label*='comment']",
            "button[aria-label*='Comment']",
            ".social-actions-button",
            "[data-tracking-control-name*='comment']"
        ]
        
        for selector in comments_buttons:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"   {selector}: {len(elements)} elements found")
            if elements:
                try:
                    print(f"   Trying to click {selector}...")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elements[0])
                    time.sleep(1)
                    elements[0].click()
                    print(f"   ✅ Clicked successfully!")
                    time.sleep(3)
                    break
                except Exception as e:
                    print(f"   ❌ Click failed: {e}")
        
        print("\n🔍 Looking for comment elements after clicking...")
        
        # Check for various comment selectors
        comment_selectors = [
            "section.comment",
            ".comment",
            "div[class*='comment']",
            "article[class*='comment']",
            "[data-test-id*='comment']",
            ".comments-comment-item",
            "li[class*='comment']"
        ]
        
        for selector in comment_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"📊 {selector}: {len(elements)} elements found")
            if elements:
                for i, el in enumerate(elements[:3]):  # Show first 3
                    class_attr = el.get_attribute("class") or ""
                    tag = el.tag_name
                    text_preview = (el.text or "")[:100] + "..." if len(el.text or "") > 100 else el.text or ""
                    print(f"  [{i}] {tag}, class='{class_attr[:80]}...', text='{text_preview}'")
                    
                    # Try to find author and text within this element
                    try:
                        author_el = el.find_element(By.CSS_SELECTOR, "a.comment__author")
                        author_text = author_el.text or ""
                        print(f"      Author found: '{author_text[:30]}...'")
                    except:
                        print(f"      No author found with a.comment__author")
                    
                    try:
                        text_el = el.find_element(By.CSS_SELECTOR, "p.comment__text, p.attributed-text-segment-list__content.comment__text")
                        comment_text = text_el.text or ""
                        print(f"      Comment text found: '{comment_text[:50]}...'")
                    except:
                        print(f"      No comment text found")
                    print()
        
        print("\n🔍 Checking page source for 'comment' keyword...")
        page_source = driver.page_source.lower()
        comment_count = page_source.count("comment")
        print(f"'comment' appears {comment_count} times in page source")
        
        if comment_count > 0:
            # Find some example comment-related text
            import re
            comment_matches = re.findall(r'.{0,50}comment.{0,50}', page_source)
            print("Sample comment-related text:")
            for match in comment_matches[:5]:
                print(f"  {match}")
        
        print("\n✅ Debug complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_comments()
