#!/usr/bin/env python3
"""
LinkedIn XPath Scraper - FIXED VERSION

✅ Session persistence (uses saved Chrome profile)
✅ Robust XPath selectors with fallbacks  
✅ Quality validation (ensures all data is extracted)
✅ Modern LinkedIn DOM support
✅ Comprehensive error handling

This combines the authentication from selenium_scraper.py with the XPath approach
from linkedin_xpath_scraper_v2.py
"""

import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import os
from datetime import datetime
import csv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    ElementClickInterceptedException,
    StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('linkedin_xpath_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LinkedInXPathScraper:
    """LinkedIn XPath scraper with session persistence and quality validation"""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the LinkedIn XPath scraper"""
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        
        # Create output directory
        self.output_dir = Path(self.config['output_settings']['output_directory'])
        self.output_dir.mkdir(exist_ok=True)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {config_path} not found")
            raise
    
    def _setup_chrome_driver(self) -> webdriver.Chrome:
        """Set up Chrome driver with session persistence and anti-automation hardening"""
        logger.info("Setting up Chrome driver with session persistence")
        
        chrome_options = Options()
        chrome_config = self.config.get('chrome_options', {})
        
        # Add automation hardening flags
        for flag in chrome_config.get('disable_automation_flags', []):
            chrome_options.add_argument(flag)
        
        # Set custom user agent
        user_agent = chrome_config.get('user_agent')
        if user_agent:
            chrome_options.add_argument(f"--user-agent={user_agent}")
        
        # Window size
        window_size = chrome_config.get('window_size', [1920, 1080])
        chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
        
        # 🔑 SESSION PERSISTENCE - CRITICAL for maintaining login state
        user_data_dir = chrome_config.get('user_data_dir')
        if user_data_dir:
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
            logger.info(f"Using Chrome profile directory: {user_data_dir}")
        
        profile_directory = chrome_config.get('profile_directory')
        if profile_directory:
            chrome_options.add_argument(f"--profile-directory={profile_directory}")
            logger.info(f"Using Chrome profile: {profile_directory}")
        
        # Headless mode
        if self.config.get('scraping_settings', {}).get('headless', False):
            chrome_options.add_argument("--headless")
            logger.info("Running in headless mode")
        else:
            logger.info("Running in headed mode")
        
        # Additional stealth options
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2
        })
        
        service = Service(ChromeDriverManager().install())
        
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute stealth scripts
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set timeouts
            driver.implicitly_wait(self.config.get('scraping_settings', {}).get('implicit_wait_timeout', 5))
            driver.set_page_load_timeout(self.config.get('scraping_settings', {}).get('page_load_timeout', 45))
            
            logger.info("Chrome driver setup completed successfully")
            return driver
            
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            raise
    
    def _random_delay(self, min_delay: float = 0.7, max_delay: float = 1.3):
        """Apply random delay to mimic human behavior"""
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"Applying random delay: {delay:.2f} seconds")
        time.sleep(delay)
    
    def initialize_driver(self) -> bool:
        """Initialize the Chrome driver"""
        try:
            self.driver = self._setup_chrome_driver()
            self.wait = WebDriverWait(
                self.driver, 
                self.config.get('scraping_settings', {}).get('explicit_wait_timeout', 20)
            )
            logger.info("Driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize driver: {e}")
            return False
    
    def login(self) -> Tuple[bool, str]:
        """Perform LinkedIn login with session persistence check"""
        if not self.driver:
            return False, "Driver not initialized"
        
        try:
            logger.info("Starting LinkedIn login process")
            
            # 🔍 First check if we're already logged in from saved session
            logger.info("Checking for existing login session...")
            self.driver.get("https://www.linkedin.com/feed")
            self._random_delay(2.0, 3.0)
            
            current_url = self.driver.current_url
            if any(pattern in current_url.lower() for pattern in ['feed', 'mynetwork', 'jobs', '/in/', 'messaging']):
                logger.info("✅ Already logged in from saved session!")
                return True, "Already authenticated from saved session"
            
            # Need to login
            login_url = "https://www.linkedin.com/login"
            logger.info(f"Need to login - navigating to {login_url}")
            self.driver.get(login_url)
            self._random_delay()
            
            # Wait for and find username field
            logger.info("Waiting for username field")
            username_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            # Wait for password field
            logger.info("Waiting for password field") 
            password_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            
            # Fill in credentials
            credentials = self.config.get('linkedin_credentials', {})
            if not credentials.get('email') or not credentials.get('password'):
                return False, "LinkedIn credentials not found in config"
            
            logger.info("Filling in credentials")
            username_field.clear()
            username_field.send_keys(credentials['email'])
            self._random_delay(0.5, 1.0)
            
            password_field.clear() 
            password_field.send_keys(credentials['password'])
            self._random_delay(0.5, 1.0)
            
            # Click submit using XPath
            logger.info("Looking for submit button")
            submit_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            submit_button.click()
            logger.info("Login form submitted")
            
            # Wait for navigation
            self._random_delay(2.0, 3.0)
            
            # Check if login was successful
            final_url = self.driver.current_url
            logger.info(f"Current URL after login attempt: {final_url}")
            
            success_patterns = ['feed', 'mynetwork', 'jobs', 'messaging', 'notifications', '/in/']
            login_successful = any(pattern in final_url.lower() for pattern in success_patterns)
            
            if login_successful:
                logger.info("✅ Login successful!")
                return True, "Login successful"
            else:
                # Check for verification challenges
                if 'challenge' in final_url or 'checkpoint' in final_url:
                    message = "Login requires verification (2FA/CAPTCHA). Please complete manually and run again."
                    logger.warning(message)
                    return False, message
                else:
                    message = f"Login status unclear. Current URL: {final_url}"
                    logger.warning(message)
                    return False, message
                    
        except Exception as e:
            message = f"Login failed with error: {e}"
            logger.error(message)
            return False, message
    
    def verify_login_status(self) -> bool:
        """Verify if user is currently logged in"""
        if not self.driver:
            return False
        
        try:
            current_url = self.driver.current_url
            success_patterns = ['feed', 'mynetwork', 'jobs', 'messaging', '/in/']
            return any(pattern in current_url.lower() for pattern in success_patterns)
        except:
            return False
    
    # ========== XPATH EXTRACTION METHODS ==========
    
    def _get_post_root(self, activity_id: Optional[str] = None):
        """Find the main post container using XPath with strong disambiguation

        On LinkedIn permalinks, comments and other widgets can include nested
        structures that superficially resemble the post. We prefer the article
        that (a) declares a data-activity-urn and (b) contains the entity
        lockup and the commentary region, which comments do not.
        """

        # Try the most specific candidates first: article with activity urn,
        # an entity lockup header, and a commentary block.
        priority_xpaths = [
            "//article[@data-activity-urn and .//*[@data-test-id='main-feed-activity-card__entity-lockup'] and .//*[@data-test-id='main-feed-activity-card__commentary']]",
            "//article[contains(@class,'main-feed-activity-card') and .//*[@data-test-id='main-feed-activity-card__commentary']]",
        ]

        # If we know the activity id from the URL, target it explicitly.
        if activity_id:
            targeted = [
                f"//article[contains(@data-activity-urn,'activity:{activity_id}') and .//*[@data-test-id='main-feed-activity-card__commentary']]",
                f"//article[contains(@data-urn,'activity:{activity_id}') and .//*[@data-test-id='main-feed-activity-card__commentary']]",
            ]
            for xpath in targeted:
                try:
                    roots = self.driver.find_elements(By.XPATH, xpath)
                    if roots:
                        logger.debug(f"✅ Found targeted post root with: {xpath}")
                        return roots[0]
                except Exception as e:
                    logger.debug(f"XPath {xpath} failed: {e}")

        for xpath in priority_xpaths:
            try:
                roots = self.driver.find_elements(By.XPATH, xpath)
                if roots:
                    logger.debug(f"✅ Found specific post root with: {xpath}")
                    return roots[0]
            except Exception as e:
                logger.debug(f"XPath {xpath} failed: {e}")

        # Fall back to any article that has both lockup and commentary.
        fallbacks = [
            "//article[.//*[@data-test-id='main-feed-activity-card__entity-lockup'] and .//*[@data-test-id='main-feed-activity-card__commentary']]",
            "//article[@data-activity-urn]",
            "//article[contains(@class,'main-feed-activity-card')]",
        ]
        for xpath in fallbacks:
            try:
                roots = self.driver.find_elements(By.XPATH, xpath)
                if roots:
                    logger.debug(f"✅ Found fallback post root with: {xpath}")
                    return roots[0]
            except Exception as e:
                logger.debug(f"XPath {xpath} failed: {e}")

        # Last resorts (broad). Avoid using these unless nothing else works.
        broad = [
            "//main//article",
            "//div[contains(@class,'feed-shared-update')]//article",
        ]
        for xpath in broad:
            try:
                roots = self.driver.find_elements(By.XPATH, xpath)
                if roots:
                    logger.debug(f"⚠️ Using broad post root with: {xpath}")
                    return roots[0]
            except Exception as e:
                logger.debug(f"XPath {xpath} failed: {e}")

        raise RuntimeError("Post root element not found with any XPath selector")

    @staticmethod
    def _activity_id_from_url(post_url: str) -> Optional[str]:
        """Extract the numeric activity id from a LinkedIn post URL, if present."""
        try:
            import re
            m = re.search(r"activity:(\d+)", post_url)
            return m.group(1) if m else None
        except Exception:
            return None
    
    def _expand_post_content(self, root):
        """Expand truncated post content using XPath"""
        logger.debug("Expanding post content using XPath")
        
        # Common "show more" button XPaths
        expand_xpaths = [
            ".//*[contains(@data-test-id,'main-feed-activity-card__commentary')]//button[contains(@aria-label,'more')]",
            ".//button[contains(@aria-label,'more')]",
            ".//button[contains(@aria-label,'See more')]",
            ".//button[contains(text(),'see more')]"
        ]
        
        for xpath in expand_xpaths:
            try:
                btn = root.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    # Scroll into view
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.5)
                    
                    try:
                        btn.click()
                    except (ElementClickInterceptedException, StaleElementReferenceException):
                        # Use JavaScript click if normal click fails
                        self.driver.execute_script("arguments[0].click();", btn)
                    
                    logger.debug(f"✅ Expanded content with XPath: {xpath}")
                    time.sleep(1)
                    return
            except NoSuchElementException:
                continue
            except Exception as e:
                logger.debug(f"Failed to expand with XPath {xpath}: {e}")
                continue
    
    def _extract_post_content(self, root) -> str:
        """Extract post text using robust XPath selectors"""
        logger.debug("Extracting post content using XPath")
        
        # Expand content first
        self._expand_post_content(root)
        
        # Only consider elements under the official commentary container to
        # avoid accidentally capturing comment text.
        post_text_xpaths = [
            ".//*[@data-test-id='main-feed-activity-card__commentary']",
            ".//*[@data-test-id='main-feed-activity-card__commentary']//*[contains(@class,'attributed-text-segment-list__content')]",
            ".//*[@data-test-id='main-feed-activity-card__commentary']//p[contains(@class,'break-words')]",
        ]
        
        texts = []
        
        for xpath in post_text_xpaths:
            try:
                elements = root.find_elements(By.XPATH, xpath)
                for element in elements:
                    text = (element.get_attribute('innerText') or element.text or '').strip()
                    if text and len(text) > 10:  # Only substantial text
                        texts.append(text)
                        logger.debug(f"✅ Found text with XPath {xpath}: {len(text)} chars")
                        break
                if texts:  # If we found text, stop looking
                    break
            except Exception as e:
                logger.debug(f"XPath {xpath} failed: {e}")
                continue
        
        # Deduplicate and join
        unique_texts = []
        seen = set()
        for text in texts:
            if text not in seen and len(text) > 10:
                seen.add(text)
                unique_texts.append(text)
        
        final_text = '\n'.join(unique_texts).strip()
        logger.debug(f"Extracted post text: {len(final_text)} characters")
        return final_text
    
    def _extract_author_info(self, root) -> Tuple[str, str, str]:
        """Extract author information using XPath"""
        logger.debug("Extracting author info using XPath")
        
        author = ""
        author_title = ""
        author_url = ""
        
        # Find entity lockup container
        try:
            lockup = root.find_element(By.XPATH, ".//*[@data-test-id='main-feed-activity-card__entity-lockup']")
        except NoSuchElementException:
            lockup = root
        
        # Extract author name and profile URL
        author_xpaths = [
            ".//a[@data-tracking-control-name='public_post_feed-actor-name']",
            ".//a[contains(@data-tracking-control-name,'actor-name')]",
            ".//*[contains(@class,'feed-shared-actor__name')]//a",
            ".//*[contains(@class,'update-components-actor__name')]//a",
            ".//a[contains(@href,'/in/') and contains(@class,'app-aware-link')]",
            ".//h3//a[contains(@href,'/in/')]",
        ]
        
        for xpath in author_xpaths:
            try:
                author_elem = lockup.find_element(By.XPATH, xpath)
                author = (author_elem.get_attribute('innerText') or author_elem.text or '').strip()
                author_url = author_elem.get_attribute('href') or ''
                if author:
                    logger.debug(f"✅ Found author with XPath {xpath}: {author}")
                    break
            except NoSuchElementException:
                continue
        
        # Extract author title/headline
        title_xpaths = [
            ".//p[contains(@class,'text-color-text-low-emphasis')]",
            ".//*[contains(@class,'feed-shared-actor__description')]",
            ".//*[contains(@class,'feed-shared-actor__sub-description')]",
            ".//*[contains(@class,'update-components-actor__description')]",
            ".//p[contains(@class,'text-body-small')]",
        ]
        
        for xpath in title_xpaths:
            try:
                title_elem = lockup.find_element(By.XPATH, xpath)
                title_text = (title_elem.get_attribute('innerText') or title_elem.text or '').strip()
                # Filter out timestamps and other metadata
                if title_text and not any(word in title_text.lower() for word in ['ago', 'hour', 'day', 'week', 'month', 'edited']):
                    author_title = title_text.split('\n')[0].strip()  # Take first line only
                    logger.debug(f"✅ Found author title with XPath {xpath}: {author_title}")
                    break
            except NoSuchElementException:
                continue
        
        return author, author_title, author_url
    
    def _extract_post_metadata(self, root) -> str:
        """Extract post date using XPath"""
        logger.debug("Extracting post metadata using XPath")
        
        date_xpaths = [
            ".//*[@data-test-id='main-feed-activity-card__entity-lockup']//time",
            ".//time[@datetime]",
            ".//time",
            ".//*[contains(@class,'feed-shared-actor__sub-description')]//time",
            ".//*[contains(@aria-label,'ago')]"
        ]
        
        for xpath in date_xpaths:
            try:
                time_elem = root.find_element(By.XPATH, xpath)
                
                # Try datetime attribute first (most reliable)
                datetime_attr = time_elem.get_attribute('datetime')
                if datetime_attr:
                    logger.debug(f"✅ Found datetime with XPath {xpath}: {datetime_attr}")
                    return datetime_attr
                
                # Fallback to text content
                time_text = (time_elem.text or '').strip()
                if time_text and any(word in time_text for word in ['ago', 'h', 'd', 'w', 'm']):
                    logger.debug(f"✅ Found time text with XPath {xpath}: {time_text}")
                    return time_text
                    
            except NoSuchElementException:
                continue
        
        logger.debug("No date found")
        return ""
    
    def _extract_links(self, root) -> List[str]:
        """Extract links from post using XPath"""
        logger.debug("Extracting links using XPath")
        
        link_xpaths = [
            ".//*[@data-test-id='main-feed-activity-card__commentary']//a[@href]",
            ".//*[@data-test-id='main-feed-activity-card__commentary']//*[contains(@class,'attributed-text-segment-list__content')]//a[@href]",
        ]
        
        links = []
        for xpath in link_xpaths:
            try:
                link_elements = root.find_elements(By.XPATH, xpath)
                for link_elem in link_elements:
                    href = (link_elem.get_attribute('href') or '').strip()
                    # Skip internal anchors like hashtags or in-app mentions without http(s)
                    if not href or not href.startswith('http'):
                        continue
                    if href and href not in links:
                        links.append(href)
                        logger.debug(f"✅ Found link: {href}")
            except Exception as e:
                logger.debug(f"Link extraction XPath {xpath} failed: {e}")
                continue
        
        return links
    
    def _extract_images(self, root) -> List[Dict[str, str]]:
        """Extract images using XPath"""
        logger.debug("Extracting images using XPath")
        
        images = []
        image_xpaths = [
            ".//ul[@data-test-id='feed-images-content']//img",
            ".//*[contains(@class,'feed-shared-image')]//img",
            ".//img[contains(@src,'linkedin.com')]"
        ]
        
        for xpath in image_xpaths:
            try:
                img_elements = root.find_elements(By.XPATH, xpath)
                for img in img_elements:
                    src = img.get_attribute('src') or ''
                    alt = img.get_attribute('alt') or ''
                    if src and not any(image['url'] == src for image in images):
                        images.append({'url': src, 'alt_text': alt})
                        logger.debug(f"✅ Found image: {src}")
            except Exception as e:
                logger.debug(f"Image extraction XPath {xpath} failed: {e}")
                continue
        
        return images
    
    def _extract_comments(self, root, limit: int = 10) -> List[Dict[str, str]]:
        """Extract comments using XPath"""
        logger.debug(f"Extracting up to {limit} comments using XPath")
        
        # Try to open comments section
        try:
            comments_button = root.find_element(By.XPATH, ".//*[@data-test-id='social-actions__comments']")
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", comments_button)
            time.sleep(1)
            comments_button.click()
            time.sleep(2)
        except NoSuchElementException:
            logger.debug("No comments button found")
        except Exception as e:
            logger.debug(f"Failed to open comments: {e}")
        
        comments = []
        # Scope comments under the comments list to avoid picking random elements.
        comment_xpaths = [
            "//div[contains(@data-test-id,'comments') or contains(@class,'comments')]/descendant::article[contains(@class,'comment') or contains(@data-test-id,'comment')]|//li[contains(@class,'comments-comment-item')]",
            "//div[contains(@data-test-id,'comments') or contains(@class,'comments')]//*[contains(@class,'comment__body') or contains(@class,'comments-comment-item')]",
        ]
        
        for xpath in comment_xpaths:
            try:
                comment_elements = self.driver.find_elements(By.XPATH, xpath)
                if comment_elements:
                    logger.debug(f"Found {len(comment_elements)} comments with XPath: {xpath}")
                    
                    for comment_elem in comment_elements[:limit]:
                        comment_data = self._extract_single_comment(comment_elem)
                        if comment_data.get('comment_text','').strip():
                            comments.append(comment_data)
                    break  # Use the first working XPath
            except Exception as e:
                logger.debug(f"Comment extraction XPath {xpath} failed: {e}")
                continue
        
        logger.debug(f"Extracted {len(comments)} comments")
        return comments
    
    def _extract_single_comment(self, comment_elem) -> Dict[str, str]:
        """Extract data from a single comment element, including links"""
        comment_data = {'commentor': '', 'comment_text': '', 'links': []}
        
        # Extract commenter name
        commenter_xpaths = [
            ".//a[contains(@class,'comment__author')]",
            ".//a[@data-tracking-control-name='public_post_comment_actor-name']",
            ".//a[contains(@href,'/in/')]"
        ]
        
        for xpath in commenter_xpaths:
            try:
                commenter_elem = comment_elem.find_element(By.XPATH, xpath)
                comment_data['commentor'] = (commenter_elem.get_attribute('innerText') or commenter_elem.text or '').strip()
                if comment_data['commentor']:
                    break
            except NoSuchElementException:
                continue
        
        # Extract comment text
        text_xpaths = [
            ".//*[contains(@class,'comment__text')]",
            ".//*[contains(@class,'attributed-text-segment-list__content')]",
            ".//*[contains(@class,'comment-text')]",
        ]
        
        for xpath in text_xpaths:
            try:
                text_elem = comment_elem.find_element(By.XPATH, xpath)
                comment_data['comment_text'] = (text_elem.get_attribute('innerText') or text_elem.text or '').strip()
                if comment_data['comment_text']:
                    break
            except NoSuchElementException:
                continue

        # Extract any links inside the comment text
        try:
            link_elems = comment_elem.find_elements(By.XPATH, ".//a[@href]")
            for a in link_elems:
                href = (a.get_attribute('href') or '').strip()
                if href.startswith('http') and href not in comment_data['links']:
                    comment_data['links'].append(href)
        except Exception:
            pass

        return comment_data
    
    def _validate_scraping_quality(self, post_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate that we extracted minimum required data"""
        issues = []
        
        # Required fields check
        required_checks = {
            'post_text': 'Post text is empty',
            'post_author': 'Author name is missing', 
        }
        
        for field, error_msg in required_checks.items():
            if not post_data.get(field, '').strip():
                issues.append(error_msg)
        
        # Optional but important fields
        optional_checks = {
            'date_posted': 'Post date is missing',
            'author_title': 'Author title/headline is missing'
        }
        
        for field, warning_msg in optional_checks.items():
            if not post_data.get(field, '').strip():
                logger.warning(f"⚠️ {warning_msg}")
        
        # Quality metrics
        post_text_len = len(post_data.get('post_text', ''))
        if post_text_len < 10:
            issues.append(f"Post text too short ({post_text_len} characters)")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def scrape_post(self, post_url: str) -> Dict[str, Any]:
        """Scrape a LinkedIn post with quality validation"""
        if not self.driver:
            raise ValueError("Driver not initialized")
        
        if not self.verify_login_status():
            raise ValueError("Not logged in")
        
        logger.info(f"🔍 Starting to scrape post: {post_url}")
        
        try:
            # Navigate to post
            self.driver.get(post_url)
            self._random_delay(1.5, 2.5)
            
            # Wait for post content to load
            self.wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, "//article[@data-activity-urn]")),
                    EC.presence_of_element_located((By.XPATH, "//article[contains(@class,'main-feed-activity-card')]")),
                    EC.presence_of_element_located((By.XPATH, "//article")),
                    EC.presence_of_element_located((By.XPATH, "//main"))
                )
            )
            
            # Get post root element
            activity_id = self._activity_id_from_url(post_url)
            root = self._get_post_root(activity_id)
            
            # Extract all data using XPath
            logger.info("📊 Extracting post data...")
            post_text = self._extract_post_content(root)
            author, author_title, author_url = self._extract_author_info(root)
            date_posted = self._extract_post_metadata(root)
            external_links = self._extract_links(root)
            images = self._extract_images(root)
            comments = self._extract_comments(root, limit=10)
            
            # Build result
            post_data = {
                'post_url': post_url,
                'scraped_at': datetime.now().isoformat(),
                'scraper_version': 'xpath-fixed-1.1',
                'post_text': post_text,
                'post_author': author,
                'author_title': author_title,
                'author_profile_url': author_url,
                'date_posted': date_posted,
                'external_links': external_links,
                'images': images,
                'comments': comments
            }
            
            # 🔍 Quality validation
            is_valid, issues = self._validate_scraping_quality(post_data)
            
            if is_valid:
                logger.info(f"✅ Successfully scraped post with high quality!")
                logger.info(f"   📝 Post text: {len(post_text)} characters")
                logger.info(f"   👤 Author: {author}")
                logger.info(f"   📅 Date: {date_posted}")
                logger.info(f"   🔗 Links: {len(external_links)}")
                logger.info(f"   💬 Comments: {len(comments)}")
            else:
                logger.warning(f"⚠️ Scraping completed but with quality issues:")
                for issue in issues:
                    logger.warning(f"   - {issue}")
                post_data['scraping_quality_issues'] = issues
            
            return post_data
            
        except Exception as e:
            logger.error(f"Failed to scrape post {post_url}: {e}")
            raise
    
    def save_post_data(self, post_data: Dict[str, Any], filename: str = None) -> str:
        """Save scraped post data to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_post_xpath_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(post_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Post data saved to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save post data: {e}")
            raise
    
    def close_driver(self):
        """Close the Chrome driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None
                self.wait = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures driver cleanup"""
        self.close_driver()


def main():
    """Test the XPath scraper"""
    import psycopg
    from dotenv import load_dotenv
    load_dotenv()
    
    print("🔗 Testing LinkedIn XPath Scraper with Session Persistence")
    print("=" * 60)
    
    # Get test URL from database
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        result = conn.execute('''
            SELECT id, url, classification 
            FROM linkedin_links 
            WHERE status = 'queued' 
            LIMIT 1
        ''').fetchone()
        
        if not result:
            print('❌ No queued URLs found')
            return
        
        link_id, url, classification = result
        print(f'📋 Testing {classification} (ID: {link_id}):')
        print(f'   URL: {url}')
        print()
    
    # Test scraper
    with LinkedInXPathScraper() as scraper:
        if not scraper.initialize_driver():
            print('❌ Failed to initialize scraper')
            return
        
        # Test login
        success, message = scraper.login()
        if not success:
            print(f'❌ Login failed: {message}')
            return
        
        print(f'✅ {message}')
        print()
        
        # Test scraping
        try:
            post_data = scraper.scrape_post(url)
            
            # Save data
            output_file = scraper.save_post_data(post_data)
            
            print()
            print('🎉 XPath SCRAPING SUCCESS!')
            print('✅ Session persistence working!')
            print('✅ XPath extraction working!')
            print('✅ Quality validation working!')
            print(f'✅ Data saved to: {output_file}')
            
        except Exception as e:
            print(f'❌ Scraping failed: {e}')
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
