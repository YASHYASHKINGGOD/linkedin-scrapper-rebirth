#!/usr/bin/env python3

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import json

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def test_comment_extraction():
    driver = setup_driver()
    
    try:
        # Navigate to a post with comments
        url = "https://www.linkedin.com/posts/ramdev-saharan-213339151_productmanagement-hiring-startupjobs-activity-7366376046297817088-SoZQ?utm_source=share&utm_medium=member_android"
        print(f"Navigating to: {url}")
        driver.get(url)
        
        print("Please login manually and navigate to the post, then press Enter...")
        input("Press Enter when ready: ")
        
        # Wait for page to load
        time.sleep(5)
        
        print("\n=== SEARCHING FOR COMMENT CONTAINERS ===")
        
        # Try different XPath selectors
        comment_xpath_selectors = [
            "//div[contains(@class, 'comments-comment-item')]",
            "//article[contains(@data-urn, 'comment')]",
            "//div[contains(@class, 'comment') and not(contains(@class, 'comments-'))]",
            "//li[contains(@class, 'comment')]",
            "//div[contains(@class, 'social-details-social-activity')]//li",
        ]
        
        comment_elements = []
        for i, xpath_selector in enumerate(comment_xpath_selectors, 1):
            elements = driver.find_elements(By.XPATH, xpath_selector)
            print(f"{i}. XPath: {xpath_selector}")
            print(f"   Found: {len(elements)} elements")
            
            if elements and not comment_elements:
                comment_elements = elements
                print(f"   ✅ Using this selector!")
        
        if not comment_elements:
            print("❌ No comment containers found!")
            return
        
        print(f"\n=== ANALYZING {len(comment_elements)} COMMENT CONTAINERS ===")
        
        comments_data = []
        
        for i, comment_element in enumerate(comment_elements[:5], 1):  # Limit to first 5 for testing
            print(f"\n--- COMMENT {i} ---")
            
            # Get all text content from the comment element
            all_text = comment_element.get_attribute('textContent')
            print(f"Full text content: {repr(all_text[:200])}{'...' if len(all_text) > 200 else ''}")
            
            # Get innerHTML to see structure
            innerHTML = comment_element.get_attribute('innerHTML')
            print(f"HTML length: {len(innerHTML)} characters")
            
            # Try to find name
            name_found = False
            name_selectors = [
                ".//a[contains(@href, '/in/')]",
                ".//span[contains(@class, 'hoverable-link-text')]", 
                ".//span[@dir='ltr']",
                ".//*[contains(@class, 'name')]"
            ]
            
            for name_sel in name_selectors:
                name_elements = comment_element.find_elements(By.XPATH, name_sel)
                if name_elements:
                    name_text = name_elements[0].get_attribute('textContent').strip()
                    if name_text and len(name_text) < 50:  # Reasonable name length
                        print(f"Name found: {name_text}")
                        name_found = True
                        break
            
            if not name_found:
                print("Name: Not found")
            
            # Try to find actual comment text by parsing the full text
            if all_text:
                lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                print(f"Text lines ({len(lines)}):")
                for j, line in enumerate(lines[:10], 1):  # Show first 10 lines
                    print(f"  {j}: {repr(line)}")
                
                # Look for comment text (longer lines that aren't just names/dates)
                potential_comments = []
                for line in lines:
                    if (len(line) > 15 and 
                        not line.endswith('ago') and
                        not line.endswith('h') and
                        not line.endswith('d') and
                        line.lower() not in ['like', 'reply', 'react', 'report']):
                        potential_comments.append(line)
                
                if potential_comments:
                    print(f"Potential comment text: {potential_comments[0]}")
                else:
                    print("No comment text identified")
            
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        input("Press Enter to close browser...")
        driver.quit()

if __name__ == "__main__":
    test_comment_extraction()
