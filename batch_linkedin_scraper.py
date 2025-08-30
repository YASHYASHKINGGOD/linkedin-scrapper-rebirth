import csv
import json
import time
import logging
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import re

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('linkedin_batch_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BatchLinkedInScraper:
    def __init__(self, config=None):
        self.config = config or {}
        self.headless = self.config.get('scraping_settings', {}).get('headless', False)
        self.driver = None
        self.wait = None
        self.logged_in = False
        
    def setup_driver(self):
        """Initialize the Chrome driver with enhanced anti-detection settings"""
        chrome_options = Options()
        
        # Get Chrome options from config
        chrome_config = self.config.get('chrome_options', {})
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Set window size
        window_size = chrome_config.get('window_size', [1920, 1080])
        chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
        
        # Add all disable automation flags from config
        disable_flags = chrome_config.get('disable_automation_flags', [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage"
        ])
        for flag in disable_flags:
            chrome_options.add_argument(flag)
        
        # Set user agent
        user_agent = chrome_config.get('user_agent', 
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
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
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute stealth scripts
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
        self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        # Set timeouts from config
        scraping_settings = self.config.get('scraping_settings', {})
        timeout = scraping_settings.get('explicit_wait_timeout', 20)
        self.wait = WebDriverWait(self.driver, timeout)
        
        implicit_wait = scraping_settings.get('implicit_wait_timeout', 1)
        self.driver.implicitly_wait(implicit_wait)
        
        logger.info("Chrome driver initialized with enhanced stealth settings")
        
    def wait_for_angular_and_network_idle(self, timeout=30):
        """Wait for Angular to finish loading and network to be idle"""
        try:
            # Wait for Angular to be defined and ready
            self.driver.execute_async_script("""
                var callback = arguments[arguments.length - 1];
                var checkAngular = function() {
                    if (typeof window.angular !== 'undefined') {
                        if (window.angular.element(document.body).injector()) {
                            window.angular.element(document.body).injector().get('$http').pendingRequests.length === 0 ? callback() : setTimeout(checkAngular, 100);
                        } else {
                            setTimeout(checkAngular, 100);
                        }
                    } else {
                        // If Angular is not present, just wait a bit and continue
                        setTimeout(callback, 2000);
                    }
                };
                checkAngular();
            """)
            
            # Additional wait for network idle
            time.sleep(3)
            logger.info("Angular and network idle detected")
            return True
            
        except Exception as e:
            logger.warning(f"Angular wait failed: {e}, continuing with regular wait")
            time.sleep(5)
            return False
    
    def expand_see_more(self):
        """Click 'see more' buttons to expand post content"""
        try:
            see_more_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                "button[aria-label*='see more'], button[data-tracking-control-name*='see-more'], .feed-shared-inline-show-more-text__see-more-less-toggle")
            
            for button in see_more_buttons:
                try:
                    if button.is_displayed() and button.is_enabled():
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(1)
                        logger.info("Expanded 'see more' content")
                except Exception as e:
                    logger.debug(f"Could not click see more button: {e}")
                    continue
        except Exception as e:
            logger.debug(f"No see more buttons found: {e}")
    
    def check_if_logged_in(self):
        """Check if user is already logged into LinkedIn"""
        try:
            current_url = self.driver.current_url
            
            # If we're on a LinkedIn page that's not the login page, we're likely logged in
            if "linkedin.com" in current_url and "login" not in current_url:
                logger.info(f"✅ Already logged in! Current page: {current_url}")
                return True
            
            # If we're not on LinkedIn at all, navigate to LinkedIn first
            if "linkedin.com" not in current_url:
                logger.info("📍 Navigating to LinkedIn to check login status...")
                self.driver.get("https://www.linkedin.com")
                time.sleep(3)
                
                current_url = self.driver.current_url
                if "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                    logger.info(f"✅ Already logged in! Redirected to: {current_url}")
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking login status: {e}")
            return False
    
    def login_to_linkedin(self, email=None, password=None):
        """Login to LinkedIn using provided credentials or manual input"""
        if self.logged_in:
            logger.info("Already logged in to LinkedIn")
            return True
        
        # First check if already logged in
        if self.check_if_logged_in():
            self.logged_in = True
            return True
            
        try:
            logger.info("🔐 Navigating to LinkedIn login page...")
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(3)
            
            # Check again if we got redirected (already logged in)
            if self.check_if_logged_in():
                self.logged_in = True
                return True
            
            if not email or not password:
                logger.info("\n⚠️ LinkedIn credentials not provided")
                logger.info("Please login manually in the browser window that opened")
                logger.info("After logging in, press Enter here to continue...")
                input("Press Enter after you've completed manual login: ")
                
                # Check if login was successful
                current_url = self.driver.current_url
                if "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                    self.logged_in = True
                    logger.info("✅ Manual login successful!")
                    return True
                else:
                    logger.warning("⚠️ Login verification failed, but continuing...")
                    self.logged_in = True  # Assume success and let posts handle auth
                    return True
            else:
                # Automated login (if credentials provided)
                logger.info("🔐 Attempting automated login...")
                
                email_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
                password_field = self.driver.find_element(By.ID, "password")
                
                email_field.clear()
                email_field.send_keys(email)
                
                password_field.clear()
                password_field.send_keys(password)
                
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
                
                # Wait for login to complete
                time.sleep(5)
                
                # Check if we're redirected to feed or profile
                current_url = self.driver.current_url
                if "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                    self.logged_in = True
                    logger.info("✅ Automated login successful!")
                    return True
                else:
                    logger.warning("⚠️ Automated login may have failed, trying manual login...")
                    logger.info("Please complete login manually in the browser")
                    input("Press Enter after completing manual login: ")
                    self.logged_in = True
                    return True
                    
        except Exception as e:
            logger.error(f"Login failed: {e}")
            logger.info("Please complete login manually in the browser")
            input("Press Enter after completing manual login: ")
            self.logged_in = True
            return True
    
    def extract_comments(self, limit=7):
        """Extract comments from the current LinkedIn post page"""
        comments = []
        
        try:
            # First, try to load more comments by clicking "Show more comments" if available
            try:
                show_more_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    "button[aria-label*='Show more comments'], .comments-comments-list__show-more-comments-button")
                for button in show_more_buttons:
                    if button.is_displayed() and button.is_enabled():
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(2)
                        logger.info("Clicked 'Show more comments'")
                        break
            except Exception as e:
                logger.debug(f"No 'show more comments' button found: {e}")
            
            # XPath selectors to find comment containers
            comment_xpath_selectors = [
                "//div[contains(@class, 'comments-comment-item')]",
                "//article[contains(@data-urn, 'comment')]",
                "//div[contains(@class, 'comments-comment-entity')]",
                "//div[contains(@class, 'comment') and not(contains(@class, 'comments-'))]",
                "//div[@data-test-id='comment']",
                "//div[contains(@class, 'feed-shared-comments')]/div",
                "//section[contains(@class, 'comments')]//div[contains(@class, 'comment-item')]",
                "//div[contains(@class, 'social-details-social-activity')]//div[contains(@class, 'comment')]"
            ]
            
            comment_elements = []
            for xpath_selector in comment_xpath_selectors:
                elements = self.driver.find_elements(By.XPATH, xpath_selector)
                if elements:
                    comment_elements = elements
                    logger.info(f"Found {len(elements)} comments with XPath: {xpath_selector}")
                    break
            
            if not comment_elements:
                logger.info("No comments found on this post")
                return comments
            
            # Limit to the specified number of comments
            comment_elements = comment_elements[:limit]
            
            for i, comment_element in enumerate(comment_elements, 1):
                try:
                    comment_data = {
                        'comment_id': i,
                        'commentor_name': '',
                        'commentor_title': '',
                        'comment_text': '',
                        'comment_date': '',
                        'comment_likes': ''
                    }
                    
                    # Extract commentor name
                    name_selectors = [
                        ".comments-post-meta__name-text",
                        ".comment-author-name",
                        ".comments-comment-entity__content .hoverable-link-text",
                        ".feed-shared-actor__name .hoverable-link-text",
                        "a[href*='/in/'] .hoverable-link-text",
                        ".comments-comment-item__main-content .hoverable-link-text",
                        "span[dir='ltr'] > span:first-child"
                    ]
                    
                    for name_selector in name_selectors:
                        name_elements = comment_element.find_elements(By.CSS_SELECTOR, name_selector)
                        for name_element in name_elements:
                            name_text = name_element.get_attribute('textContent').strip()
                            if name_text and len(name_text) > 1 and not name_text.isdigit():
                                # Clean duplicate names
                                words = name_text.split()
                                if len(words) == 4 and words[0] == words[2] and words[1] == words[3]:
                                    comment_data['commentor_name'] = f"{words[0]} {words[1]}"
                                else:
                                    comment_data['commentor_name'] = name_text
                                break
                        if comment_data['commentor_name']:
                            break
                    
                    # Extract commentor title/description
                    title_selectors = [
                        ".comments-post-meta__headline",
                        ".comment-author-title",
                        ".comments-comment-entity__content .feed-shared-actor__description",
                        ".comments-comment-item__main-content .feed-shared-actor__description"
                    ]
                    
                    for title_selector in title_selectors:
                        title_elements = comment_element.find_elements(By.CSS_SELECTOR, title_selector)
                        for title_element in title_elements:
                            title_text = title_element.get_attribute('textContent').strip()
                            if title_text and title_text != comment_data['commentor_name']:
                                comment_data['commentor_title'] = title_text
                                break
                        if comment_data['commentor_title']:
                            break
                    
                    # Extract comment text using XPath selectors
                    text_xpath_selectors = [
                        ".//div[contains(@class, 'feed-shared-text')]//span",
                        ".//span[contains(@class, 'attributed-text-segment-list__content')]",
                        ".//div[contains(@class, 'attributed-text-segment-list__content')]",
                        ".//div[contains(@class, 'feed-shared-text')]",
                        ".//span[@dir='ltr' and not(ancestor::*[contains(@class, 'actor') or contains(@class, 'meta') or contains(@class, 'name')])]",
                        ".//div[not(contains(@class, 'actor')) and not(contains(@class, 'meta')) and not(contains(@class, 'name')) and not(contains(@class, 'timestamp'))]/text()[normalize-space()]",
                        # Try to get direct text content
                        ".//text()[normalize-space() and string-length(normalize-space()) > 3]"
                    ]
                    
                    for xpath_selector in text_xpath_selectors:
                        try:
                            # Try to find text elements using XPath
                            text_elements = comment_element.find_elements(By.XPATH, xpath_selector)
                            
                            for text_element in text_elements:
                                comment_text = text_element.get_attribute('textContent') or text_element.text
                                if comment_text:
                                    comment_text = comment_text.strip()
                                    
                                    # Filter out non-comment text like names, dates, action buttons
                                    if (comment_text and 
                                        len(comment_text) > 3 and  # Minimum length
                                        len(comment_text) > len(comment_data['comment_text']) and
                                        comment_text not in [comment_data['commentor_name'], 'Like', 'Reply', 'React', 'Report', 'Share'] and
                                        not comment_text.endswith('ago') and  # Skip time stamps like "1d ago"
                                        not comment_text.endswith('h') and   # Skip "1h", "2h" etc
                                        not comment_text.endswith('d') and   # Skip "1d", "2d" etc
                                        not comment_text.endswith('w') and   # Skip "1w", "2w" etc
                                        not comment_text.isdigit()):
                                        comment_data['comment_text'] = comment_text
                                        logger.info(f"Found comment text with XPath {xpath_selector}: {comment_text[:50]}...")
                                        break
                            
                            if comment_data['comment_text']:
                                break
                                
                        except Exception as e:
                            logger.debug(f"Comment text XPath {xpath_selector} failed: {e}")
                            continue
                    
                    # If still no comment text found, try a more direct approach
                    if not comment_data['comment_text']:
                        try:
                            # Get all text content and try to filter out non-comment text
                            all_text = comment_element.get_attribute('textContent').strip()
                            
                            # Split by common separators and find the longest meaningful text
                            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                            
                            for line in lines:
                                if (line and 
                                    len(line) > 10 and  # Reasonable minimum length for comment
                                    line not in [comment_data['commentor_name']] and
                                    not line.endswith('ago') and
                                    not line.endswith('h') and
                                    not line.endswith('d') and
                                    not line.endswith('w') and
                                    line.lower() not in ['like', 'reply', 'react', 'report', 'share'] and
                                    not line.isdigit()):
                                    comment_data['comment_text'] = line
                                    logger.info(f"Found comment text via fallback method: {line[:50]}...")
                                    break
                                    
                        except Exception as e:
                            logger.debug(f"Fallback comment text extraction failed: {e}")
                    
                    # Extract comment date
                    date_elements = comment_element.find_elements(By.CSS_SELECTOR, "time, .comments-comment-item__timestamp")
                    for date_element in date_elements:
                        date_text = date_element.get_attribute('textContent').strip()
                        if date_text:
                            comment_data['comment_date'] = date_text
                            break
                    
                    # Extract comment likes if available
                    like_elements = comment_element.find_elements(By.CSS_SELECTOR, ".reaction-counts-entity__count, .social-counts-reaction__count")
                    if like_elements:
                        comment_data['comment_likes'] = like_elements[0].get_attribute('textContent').strip()
                    
                    # Only add if we have meaningful data
                    if comment_data['commentor_name'] or comment_data['comment_text']:
                        comments.append(comment_data)
                        logger.debug(f"Extracted comment {i}: {comment_data['commentor_name']} - {comment_data['comment_text'][:50]}...")
                    
                except Exception as e:
                    logger.debug(f"Failed to extract comment {i}: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(comments)} comments")
            return comments
            
        except Exception as e:
            logger.warning(f"Comment extraction failed: {e}")
            return comments
    
    def extract_post_data(self, url):
        """Extract all data from a single LinkedIn post"""
        logger.info(f"Starting extraction for URL: {url}")
        
        try:
            self.driver.get(url)
            logger.info("Page loaded, waiting for content...")
            
            # Wait for Angular and network to be ready
            self.wait_for_angular_and_network_idle()
            
            # Expand see more content
            self.expand_see_more()
            
            # Wait a bit more for any dynamic content
            time.sleep(2)
            
            # Initialize post data
            post_data = {
                'url': url,
                'author_name': '',
                'author_title': '',
                'author_location': '',
                'post_text': '',
                'post_date': '',
                'likes': '',
                'comments': '',
                'shares': '',
                'post_links': [],
                'post_images': [],
                'hashtags': [],
                'mentions': [],
                'extraction_timestamp': datetime.now().isoformat(),
                'extraction_success': False
            }
            
            # Extract author information using hybrid XPath and CSS selectors
            try:
                # Combined approach: XPath and CSS selectors for robust author extraction
                author_selectors = [
                    # XPath selectors
                    {'type': 'xpath', 'selector': "//span[@class='feed-shared-actor__name']/span[@dir='ltr']/span[1]/span[1]"},
                    {'type': 'xpath', 'selector': "//div[@class='feed-shared-actor__meta']/span[@class='feed-shared-actor__name']/span"},
                    {'type': 'xpath', 'selector': "//article//span[contains(@class, 'feed-shared-actor__name')]"},
                    {'type': 'xpath', 'selector': "//div[contains(@class, 'feed-shared-header')]//span[contains(@class, 'feed-shared-actor__name')]"},
                    {'type': 'xpath', 'selector': "//span[@class='feed-shared-actor__name']"},
                    {'type': 'xpath', 'selector': "//div[@data-tracking-control-name='public_post_feed-actor-name']//span"},
                    {'type': 'xpath', 'selector': "//a[contains(@class, 'app-aware-link') and contains(@href, '/in/')]//span[contains(@dir, 'ltr')]"},
                    {'type': 'xpath', 'selector': "//span[contains(@class, 'hoverable-link-text') and contains(@dir, 'ltr')]"},
                    
                    # CSS selectors
                    {'type': 'css', 'selector': ".feed-shared-actor__name span[dir='ltr'] span"},
                    {'type': 'css', 'selector': ".feed-shared-actor__name .hoverable-link-text"},
                    {'type': 'css', 'selector': "article .feed-shared-actor__name span"},
                    {'type': 'css', 'selector': "[data-tracking-control-name='public_post_feed-actor-name'] span"},
                    {'type': 'css', 'selector': ".update-components-actor .hoverable-link-text"},
                    {'type': 'css', 'selector': "a[href*='/in/'] span[dir='ltr']"},
                    {'type': 'css', 'selector': ".feed-shared-actor__name span"},
                    {'type': 'css', 'selector': ".app-aware-link span[dir='ltr']"}
                ]
                
                author_name = ''
                for sel in author_selectors:
                    try:
                        if sel['type'] == 'xpath':
                            elements = self.driver.find_elements(By.XPATH, sel['selector'])
                        else:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, sel['selector'])
                            
                        logger.debug(f"Found {len(elements)} elements with {sel['type']} selector: {sel['selector']}")
                        
                        for element in elements:
                            # Make sure we're not in a comment section
                            try:
                                element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'comment') or contains(@class, 'reply')][1]")
                                logger.debug(f"Skipping element in comment section")
                                continue  # Skip if inside comment
                            except:
                                # Not in comment section, use this element
                                text = element.get_attribute('textContent').strip()
                                logger.debug(f"Checking text: '{text}'")
                                if text and len(text) > 2 and not text.isdigit() and text.lower() not in ['like', 'comment', 'share', 'send']:
                                    # Clean up duplicate names (e.g., "Aarti SharmaAarti Sharma" -> "Aarti Sharma")
                                    words = text.split()
                                    # Check if we have a duplicate pattern
                                    if len(words) >= 4:
                                        first_half = ' '.join(words[:len(words)//2])
                                        second_half = ' '.join(words[len(words)//2:])
                                        if first_half == second_half:
                                            author_name = first_half  # Take first occurrence
                                        else:
                                            author_name = text
                                    elif len(words) == 4 and words[0] == words[2] and words[1] == words[3]:
                                        author_name = f"{words[0]} {words[1]}"  # Take first occurrence
                                    else:
                                        author_name = text
                                    logger.info(f"Author found with {sel['type']} selector {sel['selector']}: {author_name}")
                                    break
                        if author_name:
                            break
                    except Exception as e:
                        logger.debug(f"Author {sel['type']} selector {sel['selector']} failed: {e}")
                        continue
                
                post_data['author_name'] = author_name
                logger.info(f"Final author name: {author_name}")
                
            except Exception as e:
                logger.warning(f"Could not extract author: {e}")
            
            # Extract author title using hybrid approach
            try:
                title_selectors = [
                    # XPath selectors
                    {'type': 'xpath', 'selector': "//div[@class='feed-shared-actor__description']/span"},
                    {'type': 'xpath', 'selector': "//span[@class='feed-shared-actor__description']"},
                    {'type': 'xpath', 'selector': "//div[contains(@class, 'feed-shared-actor__meta')]//span[contains(@class, 'feed-shared-actor__description')]"},
                    {'type': 'xpath', 'selector': "//div[contains(@class, 'update-components-actor')]//span[contains(@class, 'feed-shared-actor__description')]"},
                    {'type': 'xpath', 'selector': "//div[contains(@class, 'feed-shared-actor__meta')]//span[2]"},
                    
                    # CSS selectors
                    {'type': 'css', 'selector': ".feed-shared-actor__description"},
                    {'type': 'css', 'selector': ".feed-shared-actor__meta .feed-shared-actor__description"},
                    {'type': 'css', 'selector': ".update-components-actor .feed-shared-actor__description"},
                    {'type': 'css', 'selector': "article .feed-shared-actor__description"},
                    {'type': 'css', 'selector': ".feed-shared-actor__meta > span:nth-child(2)"}
                ]
                
                author_title = ''
                for sel in title_selectors:
                    try:
                        if sel['type'] == 'xpath':
                            elements = self.driver.find_elements(By.XPATH, sel['selector'])
                        else:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, sel['selector'])
                        
                        logger.debug(f"Found {len(elements)} title elements with {sel['type']} selector: {sel['selector']}")
                        
                        for element in elements:
                            # Make sure we're not in a comment section
                            try:
                                element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'comment') or contains(@class, 'reply')][1]")
                                logger.debug(f"Skipping title element in comment section")
                                continue  # Skip if inside comment
                            except:
                                text = element.get_attribute('textContent').strip()
                                logger.debug(f"Checking title text: '{text}'")
                                if text and len(text) > 2 and text != author_name:
                                    author_title = text
                                    logger.info(f"Author title found with {sel['type']} selector {sel['selector']}: {author_title}")
                                    break
                        if author_title:
                            break
                    except Exception as e:
                        logger.debug(f"Author title {sel['type']} selector {sel['selector']} failed: {e}")
                        continue
                
                post_data['author_title'] = author_title
                logger.info(f"Final author title: {author_title}")
                
            except Exception as e:
                logger.debug(f"Could not extract author title: {e}")
            
            # Extract post text using multiple strategies
            try:
                post_text = ''
                
                # Strategy 1: Look for main post content containers
                text_selectors = [
                    ".feed-shared-text",
                    ".feed-shared-update-v2__commentary",
                    "[data-tracking-control-name='public_post_feed-text']",
                    ".feed-shared-inline-show-more-text"
                ]
                
                for selector in text_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            # Make sure this isn't inside a comment
                            try:
                                element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'comment') or contains(@class, 'reply')][1]")
                                continue  # Skip if inside comment
                            except:
                                pass  # Not in comment, continue
                            
                            text_content = element.get_attribute('textContent').strip()
                            if text_content and len(text_content) > post_text.__len__():
                                post_text = text_content
                    except Exception as e:
                        logger.debug(f"Text selector {selector} failed: {e}")
                        continue
                
                post_data['post_text'] = post_text
                logger.info(f"Post text extracted: {len(post_text)} characters")
                
            except Exception as e:
                logger.warning(f"Could not extract post text: {e}")
            
            # Extract post date/timestamp
            try:
                time_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    "time, [data-tracking-control-name='public_post_feed-timestamp']")
                for time_element in time_elements:
                    datetime_attr = time_element.get_attribute('datetime')
                    if datetime_attr:
                        post_data['post_date'] = datetime_attr
                        break
                    else:
                        text_content = time_element.get_attribute('textContent').strip()
                        if text_content:
                            post_data['post_date'] = text_content
                            break
            except Exception as e:
                logger.debug(f"Could not extract post date: {e}")
            
            # Extract engagement metrics
            try:
                # Likes
                like_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    "[data-tracking-control-name='public_post_feed-social-counts-reactions'] .social-counts-reactions__count")
                if like_elements:
                    post_data['likes'] = like_elements[0].get_attribute('textContent').strip()
                
                # Comments
                comment_elements = self.driver.find_elements(By.CSS_SELECTOR,
                    "[data-tracking-control-name='public_post_feed-social-counts-comments'] .social-counts__item-count")
                if comment_elements:
                    post_data['comments'] = comment_elements[0].get_attribute('textContent').strip()
                
                # Shares
                share_elements = self.driver.find_elements(By.CSS_SELECTOR,
                    "[data-tracking-control-name='public_post_feed-social-counts-shares'] .social-counts__item-count")
                if share_elements:
                    post_data['shares'] = share_elements[0].get_attribute('textContent').strip()
                    
            except Exception as e:
                logger.debug(f"Could not extract engagement metrics: {e}")
            
            # Extract links
            try:
                link_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href]")
                links = []
                for link in link_elements:
                    href = link.get_attribute('href')
                    if href and not href.startswith('#') and 'linkedin.com' not in href:
                        links.append(href)
                post_data['post_links'] = list(set(links))  # Remove duplicates
            except Exception as e:
                logger.debug(f"Could not extract links: {e}")
            
            # Extract hashtags and mentions from post text
            if post_data['post_text']:
                hashtags = re.findall(r'#\w+', post_data['post_text'])
                mentions = re.findall(r'@\w+', post_data['post_text'])
                post_data['hashtags'] = hashtags
                post_data['mentions'] = mentions
            
            # Extract comments (up to 7)
            try:
                comments = self.extract_comments(limit=7)
                post_data['comments_data'] = comments
                post_data['comments_count'] = len(comments)
                logger.info(f"Extracted {len(comments)} comments")
            except Exception as e:
                logger.debug(f"Could not extract comments: {e}")
                post_data['comments_data'] = []
                post_data['comments_count'] = 0
            
            # Mark as successful if we got meaningful content
            if post_data['post_text'] or post_data['author_name']:
                post_data['extraction_success'] = True
                logger.info(f"✅ Successfully extracted data for {url}")
            else:
                logger.warning(f"⚠️ Limited data extracted for {url}")
            
            return post_data
            
        except Exception as e:
            logger.error(f"❌ Failed to extract data from {url}: {e}")
            post_data['extraction_success'] = False
            return post_data
    
    def scrape_multiple_posts(self, urls, email=None, password=None):
        """Scrape multiple LinkedIn posts and return combined data"""
        all_posts_data = []
        
        try:
            self.setup_driver()
            
            # Login to LinkedIn first
            logger.info("\n🔐 LinkedIn authentication required...")
            if not self.login_to_linkedin(email, password):
                logger.error("❌ Failed to login to LinkedIn")
                return []
            
            for i, url in enumerate(urls, 1):
                logger.info(f"\n🔄 Processing post {i}/{len(urls)}")
                logger.info(f"URL: {url}")
                
                try:
                    post_data = self.extract_post_data(url)
                    all_posts_data.append(post_data)
                    
                    # Add delay between requests to be respectful
                    if i < len(urls):
                        logger.info("Waiting 5 seconds before next post...")
                        time.sleep(5)
                        
                except Exception as e:
                    logger.error(f"Failed to process {url}: {e}")
                    # Add empty entry to maintain order
                    all_posts_data.append({
                        'url': url,
                        'extraction_success': False,
                        'error': str(e),
                        'extraction_timestamp': datetime.now().isoformat()
                    })
                    continue
            
        except Exception as e:
            logger.error(f"Driver setup failed: {e}")
            return []
        
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("Browser session closed")
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")
        
        return all_posts_data
    
    def save_to_csv(self, posts_data, filename=None):
        """Save posts data to a single CSV file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"outputs/linkedin_batch_posts_{timestamp}.csv"
        
        # Ensure outputs directory exists
        import os
        os.makedirs('outputs', exist_ok=True)
        
        if not posts_data:
            logger.warning("No data to save")
            return filename
        
        # Define CSV columns
        fieldnames = [
            'url', 'author_name', 'author_title', 'author_location',
            'post_text', 'post_date', 'likes', 'comments', 'shares',
            'post_links', 'post_images', 'hashtags', 'mentions',
            'comments_count', 'comments_data_json',
            'extraction_timestamp', 'extraction_success', 'error'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for post_data in posts_data:
                    # Convert lists to strings for CSV
                    csv_row = post_data.copy()
                    for field in ['post_links', 'post_images', 'hashtags', 'mentions']:
                        if field in csv_row and isinstance(csv_row[field], list):
                            csv_row[field] = '; '.join(csv_row[field]) if csv_row[field] else ''
                    
                    # Convert comments data to JSON string
                    if 'comments_data' in csv_row:
                        csv_row['comments_data_json'] = json.dumps(csv_row['comments_data'], ensure_ascii=False)
                        # Remove the original comments_data field as it's now in JSON format
                        csv_row.pop('comments_data', None)
                    
                    writer.writerow(csv_row)
            
            logger.info(f"✅ Data saved to CSV: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Failed to save CSV: {e}")
            return None

def load_config():
    """Load configuration from config.json file"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info("✅ Configuration loaded successfully")
        return config
    except FileNotFoundError:
        logger.warning("⚠️ config.json not found, using default settings")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parsing config.json: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Error loading config: {e}")
        return {}

def main():
    # Load configuration
    config = load_config()
    
    # Get credentials from config
    email = config.get('linkedin_credentials', {}).get('email')
    password = config.get('linkedin_credentials', {}).get('password')
    
    if email and password:
        logger.info(f"🔑 Using credentials for: {email[:3]}***@{email.split('@')[1] if '@' in email else 'unknown'}")
    else:
        logger.warning("⚠️ No LinkedIn credentials found in config.json")
    
    # URLs to scrape - User provided LinkedIn posts
    urls = [
        "https://www.linkedin.com/posts/dipti-pandey-9a24a022a_hiring-productmanager-fintechjobs-activity-7365994755303854080-G80a?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/aaliya-baxamusa-01641a138_hiring-techjobs-productjobs-activity-7366002358796890112-qgAw?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ",
        "https://www.linkedin.com/posts/activity-7365981559994187777-tUdn?utm_source=share&utm_medium=member_android&rcm=ACoAADcXLXUBKetAmB2PMF4eAa5Y-jNVJ7C9GnQ"
    ]
    
    logger.info(f"🚀 Starting batch LinkedIn scraper for {len(urls)} posts")
    
    # Initialize scraper with config
    scraper = BatchLinkedInScraper(config=config)
    
    # Scrape all posts
    posts_data = scraper.scrape_multiple_posts(urls, email, password)
    
    # Save to CSV
    if posts_data:
        csv_filename = scraper.save_to_csv(posts_data)
        logger.info(f"\n✅ Batch scraping completed!")
        logger.info(f"📄 Results saved to: {csv_filename}")
        logger.info(f"📊 Total posts processed: {len(posts_data)}")
        
        # Print summary
        successful = sum(1 for post in posts_data if post.get('extraction_success', False))
        logger.info(f"✅ Successful extractions: {successful}")
        logger.info(f"❌ Failed extractions: {len(posts_data) - successful}")
        
        return csv_filename
    else:
        logger.error("❌ No data was extracted")
        return None

if __name__ == "__main__":
    main()
