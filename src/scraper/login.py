"""
LinkedIn Login Integration for Playwright Scraper
"""
import json
import os
import time
import random
from typing import Optional, Tuple
from playwright.sync_api import Page, Browser, BrowserContext


def load_linkedin_credentials() -> dict:
    """Load LinkedIn credentials from config.json"""
    config_path = "./config.json"
    if not os.path.exists(config_path):
        raise FileNotFoundError("config.json not found")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    credentials = config.get('linkedin_credentials', {})
    if not credentials.get('email') or not credentials.get('password'):
        raise ValueError("LinkedIn credentials not found in config.json")
    
    return credentials


def human_type(page: Page, selector: str, text: str, delay_range: tuple = (0.05, 0.15)):
    """Type text with human-like delays"""
    element = page.locator(selector)
    element.click()
    element.clear()
    
    for char in text:
        element.type(char)
        time.sleep(random.uniform(*delay_range))


def linkedin_login(page: Page, email: str, password: str) -> Tuple[bool, str]:
    """
    Perform LinkedIn login using Playwright
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        print("🔐 Starting LinkedIn login process...")
        
        # Navigate to LinkedIn login page
        login_url = "https://www.linkedin.com/login"
        print(f"Navigating to {login_url}")
        page.goto(login_url, wait_until="domcontentloaded")
        
        # Random delay after navigation
        time.sleep(random.uniform(1.5, 3.0))
        
        # Wait for login form to load
        page.wait_for_selector("#username", timeout=10000)
        print("✅ Login form loaded")
        
        # Fill in email
        print("Filling in email...")
        human_type(page, "#username", email)
        time.sleep(random.uniform(0.5, 1.0))
        
        # Fill in password
        print("Filling in password...")
        human_type(page, "#password", password)
        time.sleep(random.uniform(0.5, 1.0))
        
        # Click login button
        print("Clicking login button...")
        login_button = page.locator("button[type='submit']")
        login_button.click()
        
        # Wait for navigation
        print("Waiting for login to complete...")
        time.sleep(random.uniform(3.0, 5.0))
        
        # Check if login was successful
        current_url = page.url
        print(f"Current URL after login: {current_url}")
        
        # Success indicators
        success_patterns = [
            '/feed', '/mynetwork', '/jobs', '/messaging', 
            '/notifications', '/in/', 'linkedin.com/feed'
        ]
        
        login_successful = any(pattern in current_url.lower() for pattern in success_patterns)
        
        if login_successful:
            print("✅ Login successful!")
            return True, "Login successful"
        
        # Check for common issues
        page_content = page.content().lower()
        
        if 'challenge' in page_content or 'verification' in page_content:
            message = "⚠️ Login requires verification (2FA/CAPTCHA). Complete manually and try again."
            print(message)
            return False, message
        elif 'error' in page_content or 'incorrect' in page_content:
            message = "❌ Login failed - possibly incorrect credentials"
            print(message)
            return False, message
        else:
            message = f"🤔 Login status unclear. Current URL: {current_url}"
            print(message)
            return False, message
            
    except Exception as e:
        message = f"❌ Login failed with error: {str(e)}"
        print(message)
        return False, message


def setup_authenticated_context(browser: Browser) -> Tuple[BrowserContext, bool, str]:
    """
    Set up a browser context with LinkedIn authentication
    
    Returns:
        Tuple of (context, login_success, message)
    """
    # Create persistent context for session storage
    user_data_dir = "./chrome_profile"
    os.makedirs(user_data_dir, exist_ok=True)
    
    context = browser.new_context(
        user_data_dir=user_data_dir,
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="en-US",
        timezone_id="UTC",
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    
    page = context.new_page()
    
    # Check if already logged in
    print("🔍 Checking existing login status...")
    page.goto("https://www.linkedin.com/feed", wait_until="domcontentloaded")
    time.sleep(2)
    
    current_url = page.url
    if '/feed' in current_url or '/mynetwork' in current_url:
        print("✅ Already logged in!")
        return context, True, "Already authenticated"
    
    # Need to login
    print("🔐 Authentication required...")
    try:
        credentials = load_linkedin_credentials()
        success, message = linkedin_login(page, credentials['email'], credentials['password'])
        return context, success, message
    except Exception as e:
        return context, False, f"Failed to load credentials: {str(e)}"


def check_login_required(page: Page) -> bool:
    """
    Check if the current page requires login
    
    Returns:
        True if login is required, False if already authenticated
    """
    current_url = page.url
    
    # If we're on a login page or being redirected to login
    if 'login' in current_url or 'challenge' in current_url:
        return True
    
    # If we can access feed or other authenticated pages
    success_patterns = ['/feed', '/mynetwork', '/jobs', '/messaging', '/in/']
    if any(pattern in current_url for pattern in success_patterns):
        return False
    
    # Check page content for login indicators
    try:
        # Try to find elements that indicate we need to log in
        login_indicators = page.locator("text=Sign in").count() > 0 or page.locator("text=Join now").count() > 0
        return login_indicators
    except:
        return True  # Assume login required if we can't check