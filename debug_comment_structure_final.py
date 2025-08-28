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

def analyze_comment_structure_detailed(driver, post_url):
    driver.get(post_url)
    time.sleep(3)
    
    print("=== ANALYZING COMMENT STRUCTURE IN DETAIL ===")
    
    # Click comments
    try:
        comment_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='comment']")
        if comment_buttons:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_buttons[0])
            time.sleep(1)
            comment_buttons[0].click()
            time.sleep(4)
            print("✅ Comments expanded")
        else:
            print("❌ No comment buttons found")
            return
    except Exception as e:
        print(f"❌ Failed to expand comments: {e}")
        return
    
    # Get comment containers
    comment_elements = driver.find_elements(By.CSS_SELECTOR, "article[data-id*='comment']")
    print(f"Found {len(comment_elements)} comment containers")
    
    # Analyze first few comments in extreme detail
    for i, comment_el in enumerate(comment_elements[:3]):
        print(f"\n{'='*50}")
        print(f"COMMENT {i+1} DETAILED ANALYSIS")
        print(f"{'='*50}")
        
        # Get full text
        full_text = comment_el.text.strip()
        print(f"Full text:\n{full_text}\n")
        
        # Analyze line by line
        lines = full_text.split('\n')
        print("LINE-BY-LINE ANALYSIS:")
        for j, line in enumerate(lines):
            line = line.strip()
            if line:
                print(f"Line {j+1}: '{line}'")
        
        # Look for author links in detail
        print(f"\nAUTHOR LINK ANALYSIS:")
        author_links = comment_el.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
        print(f"Found {len(author_links)} profile links:")
        
        for k, link in enumerate(author_links):
            link_text = link.text.strip()
            link_href = link.get_attribute("href")
            print(f"  Link {k+1}:")
            print(f"    Text: '{link_text}'")
            print(f"    Href: {link_href}")
            print(f"    Text lines: {link_text.split(chr(10))}")  # Split by newlines
        
        # Look for specific text elements
        print(f"\nTEXT ELEMENT ANALYSIS:")
        text_elements = comment_el.find_elements(By.CSS_SELECTOR, "span, p, div")
        meaningful_elements = []
        
        for el in text_elements:
            el_text = el.text.strip()
            if el_text and len(el_text) > 2:  # Only meaningful text
                meaningful_elements.append(el)
        
        print(f"Found {len(meaningful_elements)} meaningful text elements:")
        for k, el in enumerate(meaningful_elements[:5]):  # Show first 5
            el_text = el.text.strip()
            el_class = el.get_attribute("class") or ""
            el_tag = el.tag_name
            print(f"  Element {k+1}: <{el_tag} class='{el_class[:50]}...'>{el_text[:50]}...</{el_tag}>")
        
        # Try to identify the pattern
        print(f"\nPATTERN IDENTIFICATION:")
        
        # Based on known structure: Author Name, Job Title, Time, Comment Text
        potential_author = ""
        potential_comment = ""
        
        # Strategy: First meaningful link text is likely the author
        if author_links:
            first_link_text = author_links[0].text.strip()
            if first_link_text:
                # Get just the name part (first line)
                potential_author = first_link_text.split('\n')[0].strip()
                print(f"  Potential Author: '{potential_author}'")
        
        # Strategy: Look for comment text after time indicators
        found_time = False
        for line in lines:
            line = line.strip()
            # Check if this line is a time indicator
            if len(line) <= 10 and any(indicator in line for indicator in ['h', 'd', 'w', 'm', 'ago']):
                found_time = True
                continue
            
            # After finding time, look for actual comment
            if found_time and line and len(line) > 5:
                # Skip action buttons and metadata
                if line.lower() not in ['like', 'reply', 'share', 'send'] and not line.isdigit():
                    # Skip job titles and connection indicators
                    if not any(skip in line.lower() for skip in ['• 3rd+', '• 2nd', '• 1st', 'followers']):
                        # Skip known job title patterns
                        if not (any(word in line.lower() for word in ['manager', 'analyst', 'director', 'engineer']) and len(line) > 30):
                            # This might be the comment
                            if potential_author and not line.startswith(potential_author):
                                potential_comment = line
                                break
        
        print(f"  Identified Author: '{potential_author}'")
        print(f"  Identified Comment: '{potential_comment}'")
        
        # Show HTML structure for reference
        print(f"\nHTML STRUCTURE (first 500 chars):")
        html = comment_el.get_attribute("outerHTML")
        print(f"{html[:500]}...")

def main():
    with open("config.json", "r") as f:
        config = json.load(f)
    
    driver = setup_driver()
    
    try:
        login(driver, 
              config["linkedin_credentials"]["email"], 
              config["linkedin_credentials"]["password"])
        
        post_url = "https://www.linkedin.com/posts/rashmi-p-a83a28104_wearehiring-productmanager-productmanagement-activity-7366497243979309057-DelG?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
        
        analyze_comment_structure_detailed(driver, post_url)
        
    finally:
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()
