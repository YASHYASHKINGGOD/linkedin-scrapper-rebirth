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

def analyze_comments_structure(driver, post_url):
    driver.get(post_url)
    time.sleep(3)
    
    print("=== ANALYZING COMMENT STRUCTURE ===")
    
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
    
    # Now let's analyze the comment structure in detail
    print("\n=== DETAILED COMMENT ANALYSIS ===")
    
    # Look for individual comment containers
    comment_containers = []
    
    # Try different selectors to find comment containers
    container_selectors = [
        "div[class*='comments-comment-item']",
        "li[class*='comment']", 
        "article[class*='comment']",
        "div[data-id*='comment']",
        "section[class*='comment']",
        "div[class*='comment'][class*='artdeco']",
        "div.comments-comment-item__main-content"
    ]
    
    for selector in container_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            print(f"\n🎯 Found {len(elements)} elements with selector: {selector}")
            comment_containers = elements[:10]  # Take first 10 for analysis
            break
    
    if not comment_containers:
        print("\n🔍 No clear comment containers found. Let's look at general comment elements...")
        # Fallback: look for any div that might contain comments
        all_comment_divs = driver.find_elements(By.CSS_SELECTOR, "div[class*='comment']")
        print(f"Found {len(all_comment_divs)} divs with 'comment' in class name")
        
        # Filter to find ones that look like individual comments
        for div in all_comment_divs[:20]:
            text = div.text.strip()
            if text and 20 < len(text) < 500:  # Reasonable comment length
                # Check if it has author links
                author_links = div.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
                if author_links:
                    comment_containers.append(div)
                    if len(comment_containers) >= 6:
                        break
    
    print(f"\n📝 Analyzing {len(comment_containers)} comment containers...")
    
    for i, container in enumerate(comment_containers[:6]):
        print(f"\n--- COMMENT {i+1} ---")
        
        # Get all the text content
        full_text = container.text.strip()
        print(f"Full text: {full_text[:200]}...")
        
        # Look for author links
        author_links = container.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
        print(f"Found {len(author_links)} author links")
        
        for j, link in enumerate(author_links[:2]):
            link_text = link.text.strip()
            link_href = link.get_attribute("href")
            print(f"  Link {j+1}: '{link_text}' -> {link_href}")
        
        # Look for different text elements that might be the comment
        text_selectors = [
            "p",
            "span",
            "div[class*='comment-text']",
            "div[class*='attributed-text']",
            ".attributed-text-segment-list__content",
            ".comment__text"
        ]
        
        print("Text elements found:")
        for sel in text_selectors:
            text_elements = container.find_elements(By.CSS_SELECTOR, sel)
            if text_elements:
                print(f"  {sel}: {len(text_elements)} elements")
                for k, el in enumerate(text_elements[:2]):
                    el_text = el.text.strip()
                    if el_text and len(el_text) > 5:
                        print(f"    Element {k+1}: '{el_text[:100]}...'")
        
        # Try to extract structured data
        print("🧠 EXTRACTION ATTEMPT:")
        
        # Method 1: First link as author, remaining text as comment
        commentor = ""
        if author_links:
            commentor = author_links[0].text.strip().split('\n')[0]
        
        # Try to get comment text by removing author name from full text
        comment_text = full_text
        if commentor and comment_text.startswith(commentor):
            comment_text = comment_text[len(commentor):].strip()
        
        # Clean up comment text
        lines = comment_text.split('\n')
        clean_lines = []
        for line in lines:
            line = line.strip()
            if line and not any(skip in line.lower() for skip in [
                '• 3rd+', 'hours ago', 'minutes ago', 'like', 'reply', '👍', '❤️', 'see more'
            ]):
                clean_lines.append(line)
        
        final_comment = ' '.join(clean_lines[:3])  # Take first 3 meaningful lines
        
        print(f"  Extracted Author: '{commentor}'")
        print(f"  Extracted Comment: '{final_comment[:100]}...'")
        
        # Show the HTML structure for reference
        print(f"HTML structure:")
        html = container.get_attribute("outerHTML")
        print(f"  {html[:300]}...")

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
        
        analyze_comments_structure(driver, post_url)
        
    finally:
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()
