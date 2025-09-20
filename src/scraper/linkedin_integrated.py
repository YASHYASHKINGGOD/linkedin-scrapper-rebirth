"""
Integrated LinkedIn Scraper with Authentication
Combines Selenium login + Playwright scraping for optimal performance
"""
import json
import os
import time
import random
from typing import Dict, Any, Optional
from pathlib import Path

# Selenium for login
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as SeleniumOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Playwright for fast scraping
from playwright.sync_api import sync_playwright


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json"""
    config_path = "./config.json"
    if not os.path.exists(config_path):
        raise FileNotFoundError("config.json not found")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return config


def selenium_login_session() -> Optional[Dict[str, str]]:
    """
    Use Selenium to login and extract cookies for Playwright
    Returns cookie dictionary or None if login fails
    """
    config = load_config()
    credentials = config.get('linkedin_credentials', {})
    
    if not credentials.get('email') or not credentials.get('password'):
        raise ValueError("LinkedIn credentials not found in config.json")
    
    print("🔐 Starting LinkedIn login with Selenium...")
    
    # Setup Selenium Chrome driver
    opts = SeleniumOptions()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--headless=new")  # Run headless for login
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    
    try:
        # Anti-detection
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(5)
        driver.set_page_load_timeout(45)
        
        # Navigate to login
        driver.get("https://www.linkedin.com/login")
        time.sleep(random.uniform(1.5, 2.5))
        
        # Wait for login form
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "username")))
        
        # Fill credentials
        driver.find_element(By.ID, "username").send_keys(credentials["email"])
        driver.find_element(By.ID, "password").send_keys(credentials["password"])
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Wait for login to complete
        time.sleep(random.uniform(2.0, 3.0))
        
        # Check if login successful
        current_url = driver.current_url
        success_indicators = ["feed", "/in/", "mynetwork", "jobs", "messaging", "notifications"]
        
        if not any(indicator in current_url for indicator in success_indicators):
            print("❌ Login failed or requires verification")
            print(f"Current URL: {current_url}")
            
            # Check for CAPTCHA/verification
            page_source = driver.page_source.lower()
            if 'challenge' in page_source or 'verification' in page_source:
                print("⚠️ CAPTCHA/2FA required. Please complete manually.")
                return None
            
            raise RuntimeError("Login failed or requires verification")
        
        print("✅ Login successful!")
        
        # Extract cookies
        cookies = driver.get_cookies()
        cookie_dict = {}
        for cookie in cookies:
            cookie_dict[cookie['name']] = cookie['value']
        
        print(f"🍪 Extracted {len(cookies)} cookies")
        return cookie_dict
        
    finally:
        driver.quit()


def scrape_with_authenticated_playwright(url: str, cookies: Dict[str, str]) -> Dict[str, Any]:
    """
    Use Playwright with authenticated session to scrape LinkedIn
    """
    print(f"🎭 Starting Playwright scrape: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Create context with cookies
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="UTC",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        
        # Add LinkedIn cookies
        linkedin_cookies = []
        for name, value in cookies.items():
            linkedin_cookies.append({
                'name': name,
                'value': value,
                'domain': '.linkedin.com',
                'path': '/'
            })
        
        context.add_cookies(linkedin_cookies)
        page = context.new_page()
        
        # Navigate with authentication
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(random.uniform(2.0, 4.0))
        
        # Check if we're logged in
        current_url = page.url
        if 'login' in current_url or 'challenge' in current_url:
            print("❌ Authentication failed - redirected to login")
            return {"ok": False, "error": "Authentication failed"}
        
        # Extract data based on URL type
        if '/jobs/view/' in url:
            return extract_job_data(page, url)
        elif '/posts/' in url or '/feed/update/' in url:
            return extract_post_data(page, url)
        else:
            return {"ok": False, "error": f"Unsupported URL type: {url}"}


def extract_job_data(page, url: str) -> Dict[str, Any]:
    """Extract job data using Playwright (same logic as existing scraper)"""
    try:
        # Expand description if collapsed
        try:
            btn = page.query_selector(".show-more-less-html__button--more")
            if btn:
                btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass
        
        # Extract job details
        def _first_text(selectors):
            for sel in selectors:
                try:
                    el = page.query_selector(sel)
                    if el:
                        txt = el.inner_text().strip()
                        if txt:
                            return txt
                except Exception:
                    continue
            return ""
        
        def _txt(selector):
            el = page.query_selector(selector)
            return el.inner_text().strip() if el else ""
        
        role = _first_text([
            "h1.top-card-layout__title",
            "h1.topcard__title",
            ".topcard__title",
            ".sub-nav-cta__header",
            "section.top-card-layout h1",
        ])
        
        if not role:
            # Fallback to title parsing
            try:
                title = page.title().strip()
                for sep in [" - ", " | ", " • "]:
                    if sep in title:
                        role = title.split(sep)[0].strip()
                        break
            except Exception:
                pass
        
        company = _first_text([
            "a.topcard__org-name-link",
            ".sub-nav-cta__optional-url", 
            ".top-card-layout__second-subline a",
        ])
        
        location = _txt(".topcard__flavor-row .topcard__flavor--bullet") or _txt(".sub-nav-cta__meta-text")
        posted = _txt(".posted-time-ago__text")
        status = _txt("figure.closed-job .closed-job__flavor--closed")
        
        # Description
        desc_el = page.query_selector(".description__text .show-more-less-html__markup")
        if not desc_el:
            desc_el = page.query_selector(".description__text")
        desc_text = desc_el.inner_text().strip() if desc_el else ""
        
        # Save artifacts
        html = page.content()
        timestamp = int(time.time())
        
        # Create storage directories
        storage_dir = f"./storage/scrape/{timestamp}"
        os.makedirs(f"{storage_dir}/html", exist_ok=True)
        os.makedirs(f"{storage_dir}/shots", exist_ok=True)
        
        html_path = f"{storage_dir}/html/{timestamp}.html"
        screenshot_path = f"{storage_dir}/shots/{timestamp}.png"
        
        # Save files
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        page.screenshot(path=screenshot_path, full_page=True)
        
        return {
            "ok": True,
            "url": url,
            "role_title": role,
            "company_name": company,
            "location": location,
            "posted_time": posted,
            "description_text": desc_text,
            "status": status,
            "html_path": html_path,
            "screenshot_path": screenshot_path,
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "url": url
        }


def extract_post_data(page, url: str) -> Dict[str, Any]:
    """Extract post data using Playwright"""
    try:
        # Wait for post to load
        page.wait_for_timeout(3000)
        
        # Try to find the post content
        def _txt(selector):
            el = page.query_selector(selector)
            return el.inner_text().strip() if el else ""
        
        # Extract basic post info
        author_name = _txt(".update-components-actor__name") or _txt("[data-test-id*='actor-name']")
        author_title = _txt(".update-components-actor__description") 
        post_text = _txt(".feed-shared-text") or _txt("[data-test-id*='post-text']")
        
        # Save artifacts
        html = page.content()
        timestamp = int(time.time())
        
        storage_dir = f"./storage/scrape/{timestamp}"
        os.makedirs(f"{storage_dir}/html", exist_ok=True)
        os.makedirs(f"{storage_dir}/shots", exist_ok=True)
        
        html_path = f"{storage_dir}/html/{timestamp}.html"
        screenshot_path = f"{storage_dir}/shots/{timestamp}.png"
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        page.screenshot(path=screenshot_path, full_page=True)
        
        return {
            "ok": True,
            "url": url,
            "author_name": author_name,
            "author_title": author_title,
            "post_content": post_text,
            "html_path": html_path,
            "screenshot_path": screenshot_path,
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "url": url
        }


def scrape_linkedin_with_login(url: str) -> Dict[str, Any]:
    """
    Main function: Login with Selenium, scrape with Playwright
    """
    try:
        # Step 1: Login and get cookies
        cookies = selenium_login_session()
        if not cookies:
            return {"ok": False, "error": "Failed to authenticate with LinkedIn"}
        
        # Step 2: Scrape with authenticated session
        result = scrape_with_authenticated_playwright(url, cookies)
        
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": f"Scraping failed: {str(e)}",
            "url": url
        }


# Compatibility wrapper for existing orchestration
def scrape_single_job(url: str, headed: bool = False) -> Dict[str, Any]:
    """Wrapper for existing orchestration system"""
    return scrape_linkedin_with_login(url)


def scrape_single_post(url: str, headed: bool = False) -> Dict[str, Any]:
    """Wrapper for post scraping"""
    return scrape_linkedin_with_login(url)