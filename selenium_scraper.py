#!/usr/bin/env python3
"""
LinkedIn Selenium Scraper
A robust LinkedIn scraper using Selenium with anti-automation hardening
"""

import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import os
from datetime import datetime
import re
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
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LinkedInSeleniumScraper:
    """
    LinkedIn scraper using Selenium with anti-automation hardening
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the LinkedIn Selenium scraper
        
        Args:
            config_path: Path to configuration JSON file
        """
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        
        # Create output directory if it doesn't exist
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
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
    
    def _setup_chrome_driver(self) -> webdriver.Chrome:
        """
        Set up Chrome driver with anti-automation hardening
        
        Returns:
            Configured Chrome WebDriver instance
        """
        logger.info("Setting up Chrome driver with anti-automation hardening")
        
        # Chrome options
        chrome_options = Options()
        
        # Add automation hardening flags
        for flag in self.config['chrome_options']['disable_automation_flags']:
            chrome_options.add_argument(flag)
        
        # Set custom user agent
        user_agent = self.config['chrome_options']['user_agent']
        chrome_options.add_argument(f"--user-agent={user_agent}")
        
        # Window size
        width, height = self.config['chrome_options']['window_size']
        chrome_options.add_argument(f"--window-size={width},{height}")
        
        # Headless mode
        if self.config['scraping_settings']['headless']:
            chrome_options.add_argument("--headless")
            logger.info("Running in headless mode")
        else:
            logger.info("Running in headed mode (recommended for first run)")
        
        # Additional stealth options
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set up Chrome driver service
        service = Service(ChromeDriverManager().install())
        
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            # Set timeouts
            driver.implicitly_wait(self.config['scraping_settings']['implicit_wait_timeout'])
            driver.set_page_load_timeout(self.config['scraping_settings']['page_load_timeout'])
            
            logger.info("Chrome driver setup completed successfully")
            return driver
            
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            raise
    
    def _random_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None):
        """
        Apply random delay to mimic human behavior
        
        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
        """
        if min_delay is None or max_delay is None:
            delay_range = self.config['scraping_settings']['random_delay_range']
            min_delay, max_delay = delay_range[0], delay_range[1]
        
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"Applying random delay: {delay:.2f} seconds")
        time.sleep(delay)
    
    def initialize_driver(self) -> bool:
        """
        Initialize the Chrome driver
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.driver = self._setup_chrome_driver()
            self.wait = WebDriverWait(
                self.driver, 
                self.config['scraping_settings']['explicit_wait_timeout']
            )
            logger.info("Driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize driver: {e}")
            return False
    
    def login(self) -> Tuple[bool, str]:
        """
        Perform LinkedIn login using credentials from config
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.driver:
            return False, "Driver not initialized"
        
        try:
            logger.info("Starting LinkedIn login process")
            
            # Navigate to LinkedIn login page
            login_url = "https://www.linkedin.com/login"
            logger.info(f"Navigating to {login_url}")
            self.driver.get(login_url)
            
            # Random delay after navigation
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
            credentials = self.config['linkedin_credentials']
            logger.info("Filling in credentials")
            
            username_field.clear()
            username_field.send_keys(credentials['email'])
            self._random_delay(0.5, 1.0)
            
            password_field.clear()
            password_field.send_keys(credentials['password'])
            self._random_delay(0.5, 1.0)
            
            # Find and click submit button
            logger.info("Looking for submit button")
            submit_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
            )
            
            submit_button.click()
            logger.info("Login form submitted")
            
            # Short delay for navigation
            self._random_delay(2.0, 3.0)
            
            # Check if login was successful
            current_url = self.driver.current_url
            logger.info(f"Current URL after login attempt: {current_url}")
            
            # Success indicators
            success_patterns = [
                'feed',
                'mynetwork',
                'jobs',
                'messaging',
                'notifications',
                '/in/',
                'linkedin.com/feed'
            ]
            
            login_successful = any(pattern in current_url.lower() for pattern in success_patterns)
            
            if login_successful:
                logger.info("✅ Login successful!")
                return True, "Login successful"
            else:
                # Check for common error indicators
                page_source = self.driver.page_source.lower()
                
                if 'challenge' in page_source or 'verification' in page_source:
                    message = "Login requires verification (2FA/CAPTCHA). Please complete manually and run again."
                    logger.warning(message)
                    return False, message
                elif 'error' in page_source or 'incorrect' in page_source:
                    message = "Login failed - possibly incorrect credentials"
                    logger.error(message)
                    return False, message
                else:
                    message = f"Login status unclear. Current URL: {current_url}"
                    logger.warning(message)
                    return False, message
                    
        except TimeoutException as e:
            message = f"Timeout during login: {e}"
            logger.error(message)
            return False, message
        except Exception as e:
            message = f"Login failed with error: {e}"
            logger.error(message)
            return False, message
    
    def verify_login_status(self) -> bool:
        """
        Verify if user is currently logged in
        
        Returns:
            True if logged in, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            current_url = self.driver.current_url
            success_patterns = ['feed', 'mynetwork', 'jobs', 'messaging', '/in/']
            return any(pattern in current_url.lower() for pattern in success_patterns)
        except:
            return False
    
    def scrape_post(self, post_url: str) -> Dict[str, Any]:
        """
        Scrape a LinkedIn post and extract all relevant information
        
        Args:
            post_url: LinkedIn post URL to scrape
            
        Returns:
            Dictionary containing all extracted post data
        """
        if not self.driver:
            raise ValueError("Driver not initialized")
        
        if not self.verify_login_status():
            raise ValueError("Not logged in")
        
        logger.info(f"🔍 Starting to scrape post: {post_url}")
        
        try:
            # Navigate to the post
            self.driver.get(post_url)
            self._random_delay(1.0, 2.0)  # Reduced delay
            
            # Wait for main content to load - simplified and faster
            self.wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".main-feed-activity-card")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".feed-shared-update-v2"))
                )
            )
            
            post_data = {
                'post_url': post_url,
                'scraped_at': datetime.now().isoformat(),
                'scraper_version': '1.0'
            }
            
            # Extract all post components
            post_data.update(self._extract_post_content())
            post_data.update(self._extract_post_author())
            post_data.update(self._extract_post_metadata())
            post_data['external_links'] = self._extract_external_links()
            post_data['images'] = self._extract_images()
            post_data['comments'] = self._extract_comments(limit=10)
            
            logger.info(f"✅ Successfully scraped post: {len(post_data.get('comments', []))} comments found")
            return post_data
            
        except Exception as e:
            logger.error(f"Failed to scrape post {post_url}: {e}")
            raise
    
    def _extract_post_content(self) -> Dict[str, str]:
        """Extract post text content with expansion handling"""
        logger.debug("Extracting post content")
        
        # Try to expand content first
        self._expand_post_content()
        
        # Multiple selectors for post content - using exact selectors from provided table
        content_selectors = [
            # Exact selector from provided table
            "p.attributed-text-segment-list__content",
            # Fallback variations
            ".attributed-text-segment-list__content",
            "[data-test-id='main-feed-activity-card__commentary'] .attributed-text-segment-list__content"
        ]
        
        post_text = ""
        for selector in content_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    post_text = elements[0].get_attribute('innerText') or elements[0].text
                    if post_text.strip():
                        break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        return {'post_text': post_text.strip()}
    
    def _extract_post_author(self) -> Dict[str, str]:
        """Extract post author information"""
        logger.debug("Extracting post author info")
        
        author_info = {
            'post_author': '',
            'author_title': '',
            'author_profile_url': ''
        }
        
        # Search for author elements using multiple patterns
        
        # Author name selectors - using exact selector from provided table
        author_selectors = [
            # Exact selector from provided table
            "a[data-tracking-control-name='public_post_feed-actor-name']",
            # Fallback to generic patterns
            "a[href*='/in/']",
            "*[class*='entity-lockup'] a",
            "*[class*='actor'] a", 
            "header a",
            "article a"
        ]
        
        for selector in author_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    element = elements[0]
                    author_text = element.text.strip()
                    if author_text:  # Only set if we actually got text
                        # Clean up the author text - take first meaningful line
                        cleaned_text = author_text.split('\n')[0].strip()
                        # Remove common LinkedIn suffixes
                        cleaned_text = re.sub(r'\s*•.*$', '', cleaned_text)  # Remove • and everything after
                        cleaned_text = re.sub(r'\s*\d+(st|nd|rd|th)\+?$', '', cleaned_text)  # Remove 1st+, 2nd+, etc.
                        
                        if cleaned_text and len(cleaned_text) > 2:  # Make sure we have a real name
                            author_info['post_author'] = cleaned_text
                        
                        # Try to get profile URL if it's a link
                        if element.tag_name == 'a':
                            href = element.get_attribute('href')
                            if href:
                                author_info['author_profile_url'] = href
                        break
            except Exception as e:
                logger.debug(f"Author selector {selector} failed: {e}")
                continue
        
        # Author title/description selectors - using exact selector from provided table
        title_selectors = [
            # Exact selector from provided table
            "p.text-color-text-low-emphasis",
            # Fallback to other selectors
            "[data-test-id='main-feed-activity-card__entity-lockup'] p",
            ".base-main-feed-card__entity-lockup p",
            ".feed-shared-actor__description",
            ".feed-shared-actor__sub-description"
        ]
        
        for selector in title_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Get the first line which is usually the title
                    title_text = elements[0].text.strip()
                    # Split by line and take first line (title)
                    if title_text:
                        first_line = title_text.split('\n')[0].strip()
                        if first_line and not any(word in first_line.lower() for word in ['ago', 'edited', 'hour', 'day', 'week', 'month']):
                            author_info['author_title'] = first_line
                            break
            except Exception as e:
                logger.debug(f"Title selector {selector} failed: {e}")
                continue
        
        return author_info
    
    def _extract_post_metadata(self) -> Dict[str, str]:
        """Extract post date and metadata"""
        logger.debug("Extracting post metadata")
        
        metadata = {'date_posted': ''}
        
        # Time selectors - using exact selector from provided table
        time_selectors = [
            # Exact selector from provided table
            "time",
            # Additional specific time selectors
            "time[datetime]",
            ".text-xs.text-color-text-low-emphasis.comment__duration-since time",
            "time.flex-none",
            "span.text-xs time",
            "[data-test-id='main-feed-activity-card__entity-lockup'] time",
            ".base-main-feed-card__entity-lockup time"
        ]
        
        for selector in time_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    element = elements[0]
                    
                    # Try to get datetime attribute first
                    datetime_attr = element.get_attribute('datetime')
                    if datetime_attr:
                        metadata['date_posted'] = datetime_attr
                        break
                    
                    # Fallback to text content
                    time_text = element.text.strip()
                    if time_text and ('y' in time_text or 'ago' in time_text or 'h' in time_text or 'd' in time_text):
                        metadata['date_posted'] = time_text
                        break
                        
            except Exception as e:
                logger.debug(f"Time selector {selector} failed: {e}")
                continue
        
        return metadata
    
    def _extract_external_links(self) -> List[str]:
        """Extract external links from post content"""
        logger.debug("Extracting external links")
        
        external_links = []
        
        try:
            # Find all links in the post content area - using exact selector from provided table
            link_selectors = [
                # Exact selector from provided table
                "p.attributed-text-segment-list__content a.link",
                # Fallback selectors
                ".feed-shared-update-v2 a[href]",
                ".feed-shared-text a[href]",
                ".feed-shared-article a[href]"
            ]
            
            for selector in link_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    href = element.get_attribute('href')
                    if href and not href.startswith('https://www.linkedin.com'):
                        # Clean up tracking parameters
                        clean_href = href.split('?')[0] if '?' in href else href
                        if clean_href not in external_links:
                            external_links.append(clean_href)
        
        except Exception as e:
            logger.debug(f"Failed to extract external links: {e}")
        
        return external_links
    
    def _extract_images(self) -> List[Dict[str, str]]:
        """Extract image information from the post"""
        logger.debug("Extracting images")
        
        images = []
        
        try:
            # Image selectors - using exact selector from provided table
            image_selectors = [
                # Exact selector from provided table
                "ul[data-test-id='feed-images-content'] img",
                # Fallback selectors
                ".feed-shared-image img",
                ".feed-shared-article__image img",
                ".feed-shared-update-v2 img[src]",
                "img[alt*='image']"
            ]
            
            for selector in image_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    src = element.get_attribute('src')
                    alt = element.get_attribute('alt') or ''
                    
                    if src and 'linkedin.com' in src:
                        image_info = {
                            'url': src,
                            'alt_text': alt
                        }
                        
                        # Avoid duplicates
                        if not any(img['url'] == src for img in images):
                            images.append(image_info)
        
        except Exception as e:
            logger.debug(f"Failed to extract images: {e}")
        
        return images
    
    def _extract_comments(self, limit: int = 10) -> List[Dict[str, str]]:
        """Extract comments from the post"""
        logger.debug(f"Extracting top {limit} comments")
        
        comments = []
        
        try:
            # Expand comments section if needed
            self._expand_comments_section()
            
            # Comment selectors - updated for new LinkedIn structure
            comment_selectors = [
                # New LinkedIn structure from provided HTML
                "section.comment",
                ".comment.flex.grow-1.items-stretch",
                # Fallback to old selectors for compatibility
                ".comments-comment-item",
                ".comment-item",
                "[data-id*='comment']"
            ]
            
            comment_elements = []
            for selector in comment_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    comment_elements = elements
                    break
            
            # Extract data from comment elements
            for i, comment_element in enumerate(comment_elements[:limit]):
                try:
                    comment_data = self._extract_single_comment(comment_element)
                    if comment_data['comment_text'].strip():
                        comments.append(comment_data)
                        
                except Exception as e:
                    logger.debug(f"Failed to extract comment {i}: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"Failed to extract comments: {e}")
        
        logger.info(f"Extracted {len(comments)} comments")
        return comments
    
    def _extract_single_comment(self, comment_element) -> Dict[str, str]:
        """Extract data from a single comment element"""
        comment_data = {
            'commentor': '',
            'comment_text': ''
        }
        
        try:
            # Extract commenter name - using exact selector from provided table
            author_selectors = [
                # Exact selector from provided table
                "a.comment__author",
                # Fallback selectors
                "a.text-sm.link-styled.no-underline.leading-open.comment__author.truncate.pr-6",
                "a[data-tracking-control-name='public_post_comment_actor-name']",
                "a[data-tracking-control-name*='comment_actor-name']",
                ".comments-post-meta__actor-name",
                ".comment-author-name"
            ]
            
            for selector in author_selectors:
                author_elements = comment_element.find_elements(By.CSS_SELECTOR, selector)
                if author_elements:
                    comment_data['commentor'] = author_elements[0].text.strip()
                    break
            
            # Extract comment text - using exact selector from provided table
            text_selectors = [
                # Exact selector from provided table
                "p.comment__text",
                # Fallback selectors
                ".comment__text .attributed-text-segment-list__content",
                ".comment__body .attributed-text-segment-list__content",
                ".comments-comment-textual-entity",
                ".comment-text",
                ".comments-comment-item__main-content span[dir='ltr']"
            ]
            
            for selector in text_selectors:
                text_elements = comment_element.find_elements(By.CSS_SELECTOR, selector)
                if text_elements:
                    comment_data['comment_text'] = text_elements[0].text.strip()
                    break
        
        except Exception as e:
            logger.debug(f"Failed to extract single comment data: {e}")
        
        return comment_data
    
    def _expand_post_content(self):
        """Expand truncated post content by clicking 'Show more' buttons - optimized for speed"""
        try:
            # Quick expansion - try only the most common selectors
            show_more_selectors = [
                "button[aria-label*='more']",
                ".feed-shared-inline-show-more-text button"
            ]
            
            for selector in show_more_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        elements[0].click()
                        time.sleep(0.5)  # Fixed short delay instead of random
                        logger.debug("Expanded post content")
                        return
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"Failed to expand post content: {e}")
    
    def _expand_comments_section(self):
        """Expand comments section and load more comments if needed - optimized for speed"""
        try:
            # Quick scroll to comments area
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.3);")
            time.sleep(0.3)  # Very short fixed delay
            
            # Try to expand comments - only most common selector
            more_comments_selectors = [
                "button[aria-label*='more comments']",
                "a[data-test-id*='see-more-comments']"
            ]
            
            # Only try first selector for speed
            for selector in more_comments_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        elements[0].click()
                        time.sleep(0.8)  # Fixed short delay
                        logger.debug("Expanded comments section")
                        break
                except Exception:
                    continue
                
        except Exception as e:
            logger.debug(f"Failed to expand comments: {e}")
    
    def save_post_data(self, post_data: Dict[str, Any], filename: str = None) -> str:
        """
        Save scraped post data to JSON file
        
        Args:
            post_data: The scraped post data dictionary
            filename: Optional custom filename
            
        Returns:
            Path to the saved file
        """
        if not filename:
            timestamp = datetime.now().strftime(self.config['output_settings']['timestamp_format'])
            filename = f"linkedin_post_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(post_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Post data saved to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save post data: {e}")
            raise
    
    def save_post_data_csv(self, post_data: Dict[str, Any], filename: str = None, single_file: bool = False) -> Tuple[str, str]:
        """
        Save scraped post data to CSV files (separate files for post and comments, or single file with comments as JSON)
        
        Args:
            post_data: The scraped post data dictionary
            filename: Optional custom filename prefix
            single_file: If True, save all data in a single CSV with comments as JSON column
            
        Returns:
            Tuple of (post_csv_path, comments_csv_path) or (single_csv_path, single_csv_path)
        """
        if not filename:
            timestamp = datetime.now().strftime(self.config['output_settings']['timestamp_format'])
            filename_prefix = f"linkedin_post_{timestamp}"
        else:
            filename_prefix = filename.replace('.csv', '')
        
        try:
            if single_file:
                # Save everything in a single CSV file with comments as JSON
                single_csv_path = self.output_dir / f"{filename_prefix}.csv"
                self._save_single_csv(post_data, single_csv_path)
                logger.info(f"✅ Post data saved to single CSV: {single_csv_path}")
                return str(single_csv_path), str(single_csv_path)
            else:
                # Save separate files for post and comments
                post_csv_path = self.output_dir / f"{filename_prefix}_post.csv"
                comments_csv_path = self.output_dir / f"{filename_prefix}_comments.csv"
                
                # Save main post data
                self._save_post_csv(post_data, post_csv_path)
                
                # Save comments data
                self._save_comments_csv(post_data.get('comments', []), comments_csv_path, post_data)
                
                logger.info(f"✅ Post data saved to CSV: {post_csv_path} and {comments_csv_path}")
                return str(post_csv_path), str(comments_csv_path)
                
        except Exception as e:
            logger.error(f"Failed to save post data to CSV: {e}")
            raise
    
    def _save_post_csv(self, post_data: Dict[str, Any], filepath: Path):
        """Save main post data to CSV file"""
        post_row = {
            'post_url': post_data.get('post_url', ''),
            'post_author': post_data.get('post_author', ''),
            'author_title': post_data.get('author_title', ''),
            'author_profile_url': post_data.get('author_profile_url', ''),
            'date_posted': post_data.get('date_posted', ''),
            'post_text': post_data.get('post_text', ''),
            'external_links': '; '.join(post_data.get('external_links', [])),
            'image_count': len(post_data.get('images', [])),
            'image_urls': '; '.join([img.get('url', '') for img in post_data.get('images', [])]),
            'comment_count': len(post_data.get('comments', [])),
            'scraped_at': post_data.get('scraped_at', ''),
            'scraper_version': post_data.get('scraper_version', '')
        }
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            fieldnames = list(post_row.keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(post_row)
    
    def _save_comments_csv(self, comments: List[Dict[str, str]], filepath: Path, post_data: Dict[str, Any]):
        """Save comments data to CSV file"""
        if not comments:
            # Create empty CSV with headers if no comments
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['post_url', 'post_author', 'commentor', 'comment_text']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            return
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['post_url', 'post_author', 'commentor', 'comment_text']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for comment in comments:
                comment_row = {
                    'post_url': post_data.get('post_url', ''),
                    'post_author': post_data.get('post_author', ''),
                    'commentor': comment.get('commentor', ''),
                    'comment_text': comment.get('comment_text', '')
                }
                writer.writerow(comment_row)
    
    def _save_single_csv(self, post_data: Dict[str, Any], filepath: Path):
        """Save all post data to a single CSV file with comments as JSON column"""
        # Convert comments to JSON string
        comments_json = json.dumps(post_data.get('comments', []), ensure_ascii=False)
        
        post_row = {
            'post_url': post_data.get('post_url', ''),
            'post_author': post_data.get('post_author', ''),
            'author_title': post_data.get('author_title', ''),
            'author_profile_url': post_data.get('author_profile_url', ''),
            'date_posted': post_data.get('date_posted', ''),
            'post_text': post_data.get('post_text', ''),
            'external_links': '; '.join(post_data.get('external_links', [])),
            'image_count': len(post_data.get('images', [])),
            'image_urls': '; '.join([img.get('url', '') for img in post_data.get('images', [])]),
            'comment_count': len(post_data.get('comments', [])),
            'comments_json': comments_json,  # Comments as JSON string
            'scraped_at': post_data.get('scraped_at', ''),
            'scraper_version': post_data.get('scraper_version', '')
        }
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            fieldnames = list(post_row.keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(post_row)
    
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


def quick_login_verification() -> bool:
    """
    Quick verification function to test login functionality
    
    Returns:
        True if login verification passed, False otherwise
    """
    logger.info("🚀 Starting LinkedIn login verification")
    
    try:
        with LinkedInSeleniumScraper() as scraper:
            # Initialize driver
            if not scraper.initialize_driver():
                logger.error("❌ Failed to initialize driver")
                return False
            
            # Attempt login
            success, message = scraper.login()
            
            if success:
                logger.info("✅ Login verification PASSED")
                logger.info(f"Current URL: {scraper.driver.current_url}")
                
                # Additional verification
                if scraper.verify_login_status():
                    logger.info("✅ Login status verified")
                    return True
                else:
                    logger.warning("⚠️ Login may not be complete")
                    return False
            else:
                logger.error(f"❌ Login verification FAILED: {message}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Login verification failed with exception: {e}")
        return False


if __name__ == "__main__":
    """
    Run quick login verification when script is executed directly
    """
    print("LinkedIn Selenium Scraper - Quick Login Verification")
    print("="*50)
    
    # Check if config exists
    if not os.path.exists("config.json"):
        print("❌ config.json not found!")
        print("Please create config.json with your LinkedIn credentials")
        print("Example:")
        print(json.dumps({
            "linkedin_credentials": {
                "email": "your-email@example.com",
                "password": "your-password-here"
            }
        }, indent=2))
        exit(1)
    
    # Run verification
    success = quick_login_verification()
    
    if success:
        print("\n✅ SUCCESS: Login verification passed!")
        print("You can now proceed with scraping operations.")
    else:
        print("\n❌ FAILED: Login verification failed!")
        print("Please check:")
        print("1. Your credentials in config.json")
        print("2. Network connection")
        print("3. LinkedIn account status")
        print("4. Check scraper.log for detailed error information")
        
        # If running in headless mode and failed, suggest headed mode
        with open("config.json", 'r') as f:
            config = json.load(f)
        if config.get('scraping_settings', {}).get('headless', False):
            print("5. Try setting 'headless': false in config.json for troubleshooting")
