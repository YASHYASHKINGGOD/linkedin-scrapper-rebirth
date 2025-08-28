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

def find_real_comments(driver, post_url):
    driver.get(post_url)
    time.sleep(3)
    
    print("=== FINDING REAL COMMENTS ===")
    
    # First click on comments to expand them
    try:
        comment_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='comment']")
        if comment_buttons:
            print(f"Found {len(comment_buttons)} comment buttons, clicking first one...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_buttons[0])
            time.sleep(1)
            comment_buttons[0].click()
            time.sleep(4)  # Wait for comments to fully load
            print("✅ Comments expanded")
        else:
            print("❌ No comment buttons found")
            return
    except Exception as e:
        print(f"❌ Failed to expand comments: {e}")
        return
    
    print("\n=== SEARCHING FOR ACTUAL COMMENT CONTAINERS ===")
    
    # Look for elements that contain both author info AND comment text
    # Let's try a different approach - look for elements with specific comment-related classes
    potential_selectors = [
        "article.comments-comment-item",
        "li.comments-comment-item", 
        "div.comments-comment-item__main-content",
        "div.comments-comment-item:not([class*='inline-show-more'])",
        "article[data-id*='comment']",
        "li[data-id*='comment']"
    ]
    
    real_comments = []
    
    for selector in potential_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        print(f"\n🔍 Testing selector: {selector}")
        print(f"   Found {len(elements)} elements")
        
        if elements:
            for i, el in enumerate(elements[:3]):
                text = el.text.strip()
                author_links = el.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
                
                print(f"   Element {i+1}:")
                print(f"     Text length: {len(text)}")
                print(f"     Author links: {len(author_links)}")
                print(f"     Text preview: {text[:100]}...")
                
                if author_links:
                    for j, link in enumerate(author_links):
                        link_text = link.text.strip()
                        print(f"       Author link {j+1}: '{link_text}'")
                
                # This looks like a real comment if:
                # 1. Has meaningful text (not just "..." or "CFBR")
                # 2. Has author links OR reasonable text content
                if (text and len(text) > 5 and 
                    (author_links or (len(text) > 20 and not text in ["CFBR", "Cfbr", "...", "Interested"]))):
                    print(f"   ⭐ LOOKS LIKE REAL COMMENT!")
                    real_comments.append((selector, el))
                    break
        
        if real_comments:
            print(f"\n✅ Found real comments with selector: {selector}")
            # Don't break yet, let's get all the comments from this selector
            for i, el in enumerate(elements[1:], 2):  # Start from element 2
                text = el.text.strip()
                author_links = el.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
                
                if text and len(text) > 10:
                    real_comments.append((selector, el))
                    if len(real_comments) >= 10:  # Get up to 10 comments
                        break
            break
    
    if not real_comments:
        print("\n🔍 No obvious comment containers found. Let's try a broader search...")
        
        # Try to find comments by looking at the comments section structure
        comments_sections = driver.find_elements(By.CSS_SELECTOR, "[data-test-id*='comment'], .comments-comments-list")
        print(f"Found {len(comments_sections)} comment sections")
        
        for section in comments_sections:
            # Look for individual items within this section
            items = section.find_elements(By.CSS_SELECTOR, "li, article, div")
            print(f"Section has {len(items)} items")
            
            for item in items[:10]:
                text = item.text.strip()
                author_links = item.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
                
                if (text and len(text) > 10 and len(text) < 1000 and 
                    (author_links or "cfbr" not in text.lower())):
                    print(f"🎯 Potential comment: '{text[:50]}...' (has {len(author_links)} author links)")
                    real_comments.append(("section_item", item))
                    if len(real_comments) >= 6:
                        break
            
            if real_comments:
                break
    
    print(f"\n📝 ANALYZING {len(real_comments)} REAL COMMENTS:")
    
    for i, (selector_used, comment_el) in enumerate(real_comments[:6]):
        print(f"\n--- REAL COMMENT {i+1} (found with: {selector_used}) ---")
        
        full_text = comment_el.text.strip()
        print(f"Full text: {full_text}")
        
        # Find author info
        author_links = comment_el.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
        commentor = ""
        
        if author_links:
            # Try to get the author name - look for the first meaningful link
            for link in author_links:
                link_text = link.text.strip()
                if link_text and len(link_text) > 2 and len(link_text.split()) <= 4:  # Reasonable name length
                    commentor = link_text.split('\n')[0]  # Take first line
                    break
        
        print(f"Author: '{commentor}'")
        
        # Extract comment text - different strategies
        comment_text = ""
        
        # Strategy 1: Look for specific comment text elements
        comment_text_selectors = [
            ".attributed-text-segment-list__content",
            ".comment__text",
            "p[class*='comment']",
            "span[class*='comment']"
        ]
        
        for sel in comment_text_selectors:
            text_els = comment_el.find_elements(By.CSS_SELECTOR, sel)
            if text_els:
                comment_text = text_els[0].text.strip()
                print(f"Found comment text with '{sel}': '{comment_text}'")
                break
        
        # Strategy 2: If no specific comment text found, clean the full text
        if not comment_text:
            comment_text = full_text
            
            # Remove author name if present
            if commentor and comment_text.startswith(commentor):
                comment_text = comment_text[len(commentor):].strip()
            
            # Clean up
            lines = comment_text.split('\n')
            clean_lines = []
            for line in lines:
                line = line.strip()
                if line and not any(skip in line.lower() for skip in [
                    '• 3rd+', 'hours ago', 'minutes ago', 'days ago', 'like', 'reply', 'see more'
                ]):
                    clean_lines.append(line)
            
            comment_text = ' '.join(clean_lines)
        
        print(f"Final comment: '{comment_text}'")
        
        # Show HTML for debugging
        print(f"HTML: {comment_el.get_attribute('outerHTML')[:200]}...")

def main():
    with open("config.json", "r") as f:
        config = json.load(f)
    
    driver = setup_driver()
    
    try:
        login(driver, 
              config["linkedin_credentials"]["email"], 
              config["linkedin_credentials"]["password"])
        
        post_url = "https://www.linkedin.com/posts/rashmi-p-a83a28104_wearehiring-productmanager-productmanagement-activity-7366497243979309057-DelG?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
        
        find_real_comments(driver, post_url)
        
    finally:
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()
