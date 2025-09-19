#!/usr/bin/env python3

import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def login(driver, email, password):
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)
    
    wait = WebDriverWait(driver, 10)
    user = wait.until(EC.presence_of_element_located((By.ID, "username")))
    pw = wait.until(EC.presence_of_element_located((By.ID, "password")))
    
    user.clear()
    user.send_keys(email)
    pw.clear() 
    pw.send_keys(password)
    
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(3)

def debug_title_selectors(driver, post_url):
    driver.get(post_url)
    time.sleep(3)
    
    # Get the post root
    root = driver.find_element(By.CSS_SELECTOR, ".feed-shared-update-v2")
    
    print("=== DEBUGGING AUTHOR TITLE SELECTORS ===")
    
    # Try various selectors and see what we find
    selectors_to_test = [
        "p.!text-xs.text-color-text-low-emphasis.leading-[1.33333].px-0.25.m-0.truncate",  # Original exact selector
        "p[class*='text-color-text-low-emphasis']",
        ".feed-shared-actor__description",
        ".feed-shared-actor__sub-description", 
        "p.text-color-text-low-emphasis",
        "span.text-color-text-low-emphasis",
        ".t-12.t-normal.break-words",
        ".feed-shared-actor__meta .t-12",
        ".feed-shared-actor .t-12",
        "p.truncate",
        "span.truncate"
    ]
    
    for i, selector in enumerate(selectors_to_test):
        try:
            elements = root.find_elements(By.CSS_SELECTOR, selector)
            print(f"\n{i+1}. Selector: {selector}")
            print(f"   Found {len(elements)} elements")
            
            for j, el in enumerate(elements[:3]):  # Show first 3
                text = (el.text or "").strip()
                classes = el.get_attribute("class") or ""
                tag = el.tag_name
                
                print(f"   Element {j+1}: <{tag} class='{classes}'>{text}</{tag}>")
                
                # Check if this looks like a job title
                if text and len(text) > 5 and len(text) < 100:
                    # Filter out obvious non-title text
                    if not any(skip in text.lower() for skip in [
                        'ago', 'hour', 'day', 'week', 'month', 'see more', 'like', 'comment'
                    ]):
                        print(f"   ⭐ POTENTIAL TITLE: '{text}'")
                        
        except Exception as e:
            print(f"   ❌ Error with selector: {e}")
    
    # Also let's look at the whole feed-shared-actor area
    print("\n=== FULL ACTOR AREA CONTENT ===")
    try:
        actor_area = root.find_element(By.CSS_SELECTOR, ".feed-shared-actor")
        print(f"Actor area full text:\n{actor_area.text}")
        print("\nActor area HTML:")
        print(actor_area.get_attribute("outerHTML")[:1000] + "...")
        
        # Get all p and span elements in actor area
        all_text_els = actor_area.find_elements(By.CSS_SELECTOR, "p, span")
        print(f"\nFound {len(all_text_els)} text elements in actor area:")
        for i, el in enumerate(all_text_els[:10]):
            text = (el.text or "").strip()
            classes = el.get_attribute("class") or ""
            if text:
                print(f"{i+1}. <{el.tag_name} class='{classes[:50]}...'>{text}</{el.tag_name}>")
                
    except Exception as e:
        print(f"❌ Error getting actor area: {e}")

def main():
    # Load config for credentials
    with open("config.json", "r") as f:
        config = json.load(f)
    
    driver = setup_driver()
    
    try:
        login(driver, 
              config["linkedin_credentials"]["email"], 
              config["linkedin_credentials"]["password"])
        
        post_url = "https://www.linkedin.com/posts/rashmi-p-a83a28104_wearehiring-productmanager-productmanagement-activity-7366497243979309057-DelG?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
        
        debug_title_selectors(driver, post_url)
        
    finally:
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()
