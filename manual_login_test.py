#!/usr/bin/env python3
"""
Manual LinkedIn Login Test - Extended Browser Session
Allows time for manual verification challenges (2FA/CAPTCHA)
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

def manual_login_test():
    """Extended login test with manual intervention support"""
    
    print("🔐 LinkedIn Manual Login Test")
    print("=" * 50)
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Setup Chrome with session persistence
    chrome_options = Options()
    chrome_config = config.get('chrome_options', {})
    
    # Add stealth flags
    for flag in chrome_config.get('disable_automation_flags', []):
        chrome_options.add_argument(flag)
    
    # User agent and window size
    user_agent = chrome_config.get('user_agent')
    if user_agent:
        chrome_options.add_argument(f"--user-agent={user_agent}")
    
    window_size = chrome_config.get('window_size', [1920, 1080])
    chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    
    # Session persistence - this is KEY for saving login state
    user_data_dir = chrome_config.get('user_data_dir', 'chrome_profile')
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    
    profile_directory = chrome_config.get('profile_directory', 'Default')
    chrome_options.add_argument(f"--profile-directory={profile_directory}")
    
    # Anti-automation settings
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Execute stealth scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("🌐 Navigating to LinkedIn login page...")
        driver.get("https://www.linkedin.com/login")
        
        print("⏱️  Waiting for page to load...")
        time.sleep(3)
        
        print(f"📍 Current URL: {driver.current_url}")
        
        # Check if already logged in from previous session
        if "login" not in driver.current_url.lower():
            print("✅ Already logged in from saved session!")
            print(f"Current URL: {driver.current_url}")
            print("\n🎉 SUCCESS: Session persistence worked!")
            return True
        
        # Try to fill credentials automatically
        try:
            print("🔍 Looking for login form...")
            
            # Wait for username field
            username_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            
            # Fill credentials
            credentials = config['linkedin_credentials']
            print("✍️  Filling in credentials...")
            
            username_field.clear()
            username_field.send_keys(credentials['email'])
            time.sleep(1)
            
            password_field.clear()
            password_field.send_keys(credentials['password'])
            time.sleep(1)
            
            # Click submit
            submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
            submit_button.click()
            print("📤 Login form submitted")
            
            # Wait for response
            time.sleep(5)
            
        except Exception as e:
            print(f"⚠️  Could not auto-fill credentials: {e}")
            print("Please fill in credentials manually in the browser window")
        
        # Check current status
        current_url = driver.current_url
        print(f"\n📍 Current URL: {current_url}")
        
        if "checkpoint" in current_url or "challenge" in current_url:
            print("\n🔒 LinkedIn verification challenge detected!")
            print("👀 The browser window should be visible.")
            print("✋ Please complete the verification challenge manually.")
            print("   This might be:")
            print("   - CAPTCHA puzzle")
            print("   - Email verification code")
            print("   - Phone verification")
            print("   - Security questions")
            
            print("\n⏰ Waiting 2 minutes for you to complete verification...")
            print("   (The browser will stay open)")
            
            # Wait with progress indicator
            for i in range(120):  # 2 minutes
                time.sleep(1)
                if i % 10 == 0:  # Check every 10 seconds
                    current_url = driver.current_url
                    if any(pattern in current_url.lower() for pattern in ['feed', 'mynetwork', 'jobs', '/in/']):
                        print(f"\n✅ SUCCESS! Login completed at {current_url}")
                        break
                    print(f"   Waiting... {120-i}s remaining (current: {current_url})")
        
        # Final check
        final_url = driver.current_url
        success_patterns = ['feed', 'mynetwork', 'jobs', '/in/', 'messaging']
        login_successful = any(pattern in final_url.lower() for pattern in success_patterns)
        
        if login_successful:
            print(f"\n🎉 SUCCESS: Logged in successfully!")
            print(f"Final URL: {final_url}")
            print("\n💾 Session will be saved for future use")
            return True
        else:
            print(f"\n⚠️  Login status unclear. Final URL: {final_url}")
            print("You may need to complete additional verification steps.")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during login test: {e}")
        return False
        
    finally:
        print(f"\n⏰ Keeping browser open for 30 more seconds for review...")
        time.sleep(30)
        driver.quit()
        print("🔚 Browser closed")

if __name__ == "__main__":
    success = manual_login_test()
    
    if success:
        print("\n✅ Login test completed successfully!")
        print("🔄 You can now run the scrapers - they should use the saved session.")
    else:
        print("\n❌ Login test did not complete successfully.")
        print("💡 Try running this script again, or check your credentials.")