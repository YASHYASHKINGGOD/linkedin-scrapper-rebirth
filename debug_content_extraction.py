#!/usr/bin/env python3

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def test_content_extraction():
    # Setup Chrome
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        url = "https://www.linkedin.com/posts/artika-upadhyay-44391915_were-hiring-product-manager-aproduct-activity-7366380148369043457-EpkX?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
        print(f"🔍 Loading: {url}")
        driver.get(url)
        time.sleep(5)
        
        # Find the post root like the scraper does
        root_selectors = [
            ".feed-shared-update-v2",  # Standard feed post
            "article",                    # Fallback article elements
            "main",                       # Main content container
            "[data-test-id*='main-feed']", # Any main feed element
            "body"                        # Ultimate fallback - entire body
        ]
        
        root = None
        for selector in root_selectors:
            roots = driver.find_elements(By.CSS_SELECTOR, selector)
            if roots:
                print(f"✅ Using post root: {selector}")
                root = roots[0]
                break
        
        if not root:
            print("❌ No root found!")
            return
        
        # Expand content first
        print("\\n🔄 Expanding content...")
        show_more_selectors = [
            "button[aria-label*='more']",
            "button[aria-label*='see more']",
            "button[data-test-id='see-more-button']",
        ]
        
        for sel in show_more_selectors:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                if btn.is_displayed() and btn.is_enabled():
                    try:
                        btn.click()
                        print(f"✅ Clicked {sel}")
                        time.sleep(2)
                        break
                    except Exception as e:
                        print(f"Failed to click {sel}: {e}")
                        continue
        
        print("\\n" + "="*80)
        print("🔍 TESTING CONTENT EXTRACTION WITH UPDATED SELECTORS")
        print("="*80)
        
        # Test the exact selectors from our updated scraper
        content_selectors = [
            # Specific selector for posts like Artika's - highest priority
            "p[data-test-id='main-feed-activity-card__commentary']",
            ".feed-shared-text",
            "[data-test-id='main-feed-activity-card__commentary']",
            "[data-test-id*='commentary'] .attributed-text-segment-list__content", 
            ".update-components-text span.break-words",
            ".update-components-text",
            ".feed-shared-update-v2__commentary",
            ".feed-shared-update-v2__description .attributed-text-segment-list__content",
            ".feed-shared-update-v2__description",
            # Additional specific selector that was working in debug
            "p.attributed-text-segment-list__content"
        ]
        
        texts = []
        
        for i, selector in enumerate(content_selectors, 1):
            print(f"\\n{i:2d}. Testing: {selector}")
            elements = root.find_elements(By.CSS_SELECTOR, selector)
            print(f"    Found {len(elements)} elements")
            
            for j, el in enumerate(elements, 1):
                try:
                    # Check if inside comment with improved logic
                    try:
                        # Be more specific - look for actual comment containers, not just "comment" in class
                        parent_comment = el.find_element(By.XPATH, "./ancestor::*[contains(@class, 'comment') and not(contains(@class, 'commentary'))]")
                        # Also check for specific comment container patterns
                        comment_containers = [
                            "./ancestor::article[contains(@data-id, 'comment')]",
                            "./ancestor::*[contains(@class, 'comments-post-meta')]",
                            "./ancestor::section[contains(@class, 'comment')]"
                        ]
                        is_in_comment = False
                        for xpath in comment_containers:
                            try:
                                comment_container = el.find_element(By.XPATH, xpath)
                                if comment_container:
                                    is_in_comment = True
                                    break
                            except:
                                continue
                        
                        if parent_comment or is_in_comment:
                            print(f"    Element {j}: SKIPPED (inside comment)")
                            continue
                    except:
                        pass  # Not inside comment
                    
                    text = (el.get_attribute("innerText") or el.text or "").strip()
                    if text and len(text) > 15:
                        if not any(skip in text.lower() for skip in [
                            '• 3rd+', 'hours ago', 'minutes ago', 'days ago', 'weeks ago',
                            'like this', 'comment', 'repost', 'share', 'send',
                            'thanks for posting', 'cfbr', 'commenting for'
                        ]):
                            if text not in texts:
                                texts.append(text)
                                print(f"    Element {j}: ADDED - '{text[:100]}{'...' if len(text) > 100 else ''}'")
                            else:
                                print(f"    Element {j}: DUPLICATE - '{text[:100]}{'...' if len(text) > 100 else ''}'")
                        else:
                            print(f"    Element {j}: FILTERED - '{text[:50]}...' (contains skip pattern)")
                    else:
                        if text:
                            print(f"    Element {j}: TOO SHORT - '{text}'")
                        else:
                            print(f"    Element {j}: EMPTY")
                            
                except Exception as e:
                    print(f"    Element {j}: ERROR - {e}")
        
        print("\\n" + "="*80)
        print("📝 FINAL EXTRACTED TEXTS")
        print("="*80)
        
        if texts:
            for i, text in enumerate(texts, 1):
                print(f"{i}. {text}")
                print("-" * 50)
        else:
            print("❌ NO TEXT EXTRACTED!")
            
            # Let's try a much broader search
            print("\\n🔍 TRYING BROADER SEARCH IN ROOT...")
            all_elements = root.find_elements(By.CSS_SELECTOR, "*")
            hiring_elements = []
            
            for elem in all_elements:
                try:
                    text = elem.text.strip()
                    if text and "hiring" in text.lower():
                        hiring_elements.append((elem.tag_name, elem.get_attribute('class'), text))
                except:
                    continue
            
            print(f"Found {len(hiring_elements)} elements containing 'hiring':")
            for tag, cls, text in hiring_elements[:5]:
                print(f"  <{tag} class='{cls}'> - '{text[:100]}...'")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_content_extraction()
