#!/usr/bin/env python3

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json

def debug_post_structure(url):
    # Setup Chrome options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    # Initialize driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"🔍 Loading post: {url}")
        driver.get(url)
        time.sleep(5)
        
        # Try to find and click "See more" buttons first
        see_more_selectors = [
            "button[aria-label*='more']",
            "button[aria-label*='See more']", 
            "button[data-test-id='see-more-button']",
            ".see-more",
            "button.update-components-text__see-more"
        ]
        
        for selector in see_more_selectors:
            try:
                see_more_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for button in see_more_buttons:
                    if button.is_displayed() and button.is_enabled():
                        print(f"✅ Clicking 'See more' button: {selector}")
                        button.click()
                        time.sleep(2)
                        break
            except Exception as e:
                print(f"❌ Failed to click see more with {selector}: {str(e)}")
                continue
        
        print("\n" + "="*80)
        print("🔍 DEBUGGING POST CONTENT EXTRACTION")
        print("="*80)
        
        # Test all possible post content selectors
        post_content_selectors = [
            # Original selectors
            ".feed-shared-update-v2__commentary .attributed-text-segment-list__content",
            ".update-components-text .attributed-text-segment-list__content", 
            
            # New selectors we added
            "p[data-test-id='main-feed-activity-card__commentary']",
            "div.update-components-text > span.break-words",
            "div.update-components-text span.break-words",
            ".update-components-text .break-words",
            
            # Additional potential selectors
            ".feed-shared-update-v2__commentary",
            ".update-components-text",
            "div[data-test-id='main-feed-activity-card__commentary']",
            ".feed-shared-text",
            ".attributed-text-segment-list",
            "span[dir='ltr']",
            
            # Very broad selectors
            ".feed-shared-update-v2 p",
            ".feed-shared-update-v2 span",
            ".update-components-text p",
            ".update-components-text span"
        ]
        
        for i, selector in enumerate(post_content_selectors, 1):
            print(f"\n{i:2d}. Testing selector: {selector}")
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"    Found {len(elements)} elements")
                
                for j, element in enumerate(elements[:3], 1):  # Show first 3 elements
                    try:
                        text = element.text.strip()
                        if text:
                            print(f"    Element {j}: '{text[:100]}{'...' if len(text) > 100 else ''}'")
                        else:
                            # Try innerHTML if text is empty
                            inner_html = element.get_attribute('innerHTML')
                            print(f"    Element {j}: (empty text) HTML: '{inner_html[:100]}{'...' if len(inner_html) > 100 else ''}'")
                    except Exception as e:
                        print(f"    Element {j}: Error getting text - {str(e)}")
                        
            except Exception as e:
                print(f"    ❌ Error: {str(e)}")
        
        print("\n" + "="*80)
        print("🔍 FULL DOM STRUCTURE ANALYSIS")
        print("="*80)
        
        # Get the main content container
        try:
            main_container = driver.find_element(By.CSS_SELECTOR, ".feed-shared-update-v2")
            print("\n📄 Main container HTML structure:")
            print("-" * 50)
            
            # Get all text-containing elements
            text_elements = main_container.find_elements(By.XPATH, ".//*[text()]")
            
            for i, elem in enumerate(text_elements[:10], 1):  # First 10 elements
                try:
                    tag = elem.tag_name
                    classes = elem.get_attribute('class') or ''
                    data_test_id = elem.get_attribute('data-test-id') or ''
                    text = elem.text.strip()
                    
                    if text and len(text) > 10:  # Only show substantial text
                        print(f"{i:2d}. <{tag} class='{classes}' data-test-id='{data_test_id}'>")
                        print(f"    Text: '{text[:100]}{'...' if len(text) > 100 else ''}'")
                        print()
                        
                except Exception as e:
                    print(f"    Error processing element {i}: {str(e)}")
                    
        except NoSuchElementException:
            print("❌ Could not find main container .feed-shared-update-v2")
        
        print("\n" + "="*80)
        print("🔍 LOOKING FOR SPECIFIC PATTERNS")
        print("="*80)
        
        # Look for specific text patterns that might indicate the post content
        patterns_to_search = [
            "hiring",
            "Product Manager", 
            "WOW Jobs",
            "product-manager",
            "Were hiring"
        ]
        
        for pattern in patterns_to_search:
            print(f"\n🔍 Searching for pattern: '{pattern}'")
            try:
                elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{pattern}')]")
                print(f"    Found {len(elements)} elements containing '{pattern}'")
                
                for j, elem in enumerate(elements[:3], 1):
                    try:
                        tag = elem.tag_name
                        classes = elem.get_attribute('class') or ''
                        text = elem.text.strip()
                        print(f"    Element {j}: <{tag} class='{classes}'>")
                        print(f"    Text: '{text[:150]}{'...' if len(text) > 150 else ''}'")
                        print()
                    except Exception as e:
                        print(f"    Error with element {j}: {str(e)}")
                        
            except Exception as e:
                print(f"    ❌ Error searching for '{pattern}': {str(e)}")
        
        print("\n" + "="*80)
        print("🔍 COMPLETE PAGE SOURCE ANALYSIS")
        print("="*80)
        
        # Search the page source for known text
        page_source = driver.page_source
        if "hiring" in page_source.lower():
            print("✅ Found 'hiring' in page source")
            
            # Find the context around "hiring"
            import re
            hiring_matches = re.finditer(r'.{0,100}hiring.{0,100}', page_source.lower())
            for i, match in enumerate(list(hiring_matches)[:3], 1):
                print(f"Match {i}: ...{match.group()}...")
        else:
            print("❌ 'hiring' not found in page source")
            
        if "product manager" in page_source.lower():
            print("✅ Found 'product manager' in page source")
        else:
            print("❌ 'product manager' not found in page source")
    
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    url = "https://www.linkedin.com/posts/artika-upadhyay-44391915_were-hiring-product-manager-aproduct-activity-7366380148369043457-EpkX?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
    debug_post_structure(url)
