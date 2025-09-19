#!/usr/bin/env python3

import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def debug_linkedin_login_page():
    """Debug LinkedIn login page to see what elements are available"""
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    chrome_options = Options()
    chrome_config = config.get('chrome_options', {})
    
    # Set window size
    window_size = chrome_config.get('window_size', [1920, 1080])
    chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    
    # Add disable automation flags
    disable_flags = chrome_config.get('disable_automation_flags', [])
    for flag in disable_flags:
        chrome_options.add_argument(flag)
    
    # Set user agent
    user_agent = chrome_config.get('user_agent')
    if user_agent:
        chrome_options.add_argument(f"--user-agent={user_agent}")
    
    # Set user data directory for session persistence
    user_data_dir = chrome_config.get('user_data_dir')
    if user_data_dir:
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        
    profile_directory = chrome_config.get('profile_directory')
    if profile_directory:
        chrome_options.add_argument(f"--profile-directory={profile_directory}")
    
    # Additional stealth options
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2
    })
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Execute stealth scripts
        if user_agent:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        print("🔍 Navigating to LinkedIn login page...")
        driver.get("https://www.linkedin.com/login")
        
        print("⏱️  Waiting for page to load...")
        time.sleep(5)
        
        print(f"🌐 Current URL: {driver.current_url}")
        print(f"📄 Page Title: {driver.title}")
        
        # Check if we're on the expected login page
        if "login" not in driver.current_url.lower():
            print("⚠️  Not on login page - might be redirected!")
            print(f"Current URL: {driver.current_url}")
        
        # Try different selectors for the username/email field
        selectors_to_try = [
            ("By.ID", "username", lambda: driver.find_element(By.ID, "username")),
            ("By.NAME", "session_key", lambda: driver.find_element(By.NAME, "session_key")),
            ("By.CSS_SELECTOR", "input[name='session_key']", lambda: driver.find_element(By.CSS_SELECTOR, "input[name='session_key']")),
            ("By.CSS_SELECTOR", "input[id='username']", lambda: driver.find_element(By.CSS_SELECTOR, "input[id='username']")),
            ("By.CSS_SELECTOR", "input[type='email']", lambda: driver.find_element(By.CSS_SELECTOR, "input[type='email']")),
            ("By.XPATH", "//input[@placeholder='Email or phone']", lambda: driver.find_element(By.XPATH, "//input[@placeholder='Email or phone']")),
        ]
        
        print("\\n🔍 Testing different selectors for email/username field:")
        found_element = None
        
        for selector_type, selector_value, finder_func in selectors_to_try:
            try:
                element = finder_func()
                if element:
                    print(f"✅ {selector_type} '{selector_value}' - FOUND!")
                    print(f"   Element tag: {element.tag_name}")
                    print(f"   Element type: {element.get_attribute('type')}")
                    print(f"   Element name: {element.get_attribute('name')}")
                    print(f"   Element id: {element.get_attribute('id')}")
                    print(f"   Element placeholder: {element.get_attribute('placeholder')}")
                    print(f"   Element visible: {element.is_displayed()}")
                    print(f"   Element enabled: {element.is_enabled()}")
                    if not found_element:
                        found_element = element
                else:
                    print(f"❌ {selector_type} '{selector_value}' - Not found")
            except Exception as e:
                print(f"❌ {selector_type} '{selector_value}' - Exception: {str(e)}")
        
        # Try password field
        print("\\n🔍 Testing selectors for password field:")
        password_selectors = [
            ("By.ID", "password", lambda: driver.find_element(By.ID, "password")),
            ("By.NAME", "session_password", lambda: driver.find_element(By.NAME, "session_password")),
            ("By.CSS_SELECTOR", "input[type='password']", lambda: driver.find_element(By.CSS_SELECTOR, "input[type='password']")),
        ]
        
        for selector_type, selector_value, finder_func in password_selectors:
            try:
                element = finder_func()
                if element:
                    print(f"✅ {selector_type} '{selector_value}' - FOUND!")
                    print(f"   Element visible: {element.is_displayed()}")
                    print(f"   Element enabled: {element.is_enabled()}")
            except Exception as e:
                print(f"❌ {selector_type} '{selector_value}' - Exception: {str(e)}")
        
        # Get page source snippet to see what's actually on the page
        print("\\n📄 First 2000 characters of page source:")
        page_source = driver.page_source
        print(page_source[:2000])
        print("...")
        
        # Check for common LinkedIn anti-bot messages
        anti_bot_indicators = [
            "challenge", "blocked", "temporarily unavailable", 
            "security check", "unusual activity", "verify"
        ]
        
        page_text = page_source.lower()
        for indicator in anti_bot_indicators:
            if indicator in page_text:
                print(f"⚠️  Possible anti-bot detection: Found '{indicator}' in page")
        
        print("\\n⏱️  Keeping browser open for 10 seconds for manual inspection...")
        time.sleep(10)
        
    finally:
        driver.quit()
        print("🔚 Browser closed")

if __name__ == "__main__":
    debug_linkedin_login_page()
