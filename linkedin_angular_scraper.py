#!/usr/bin/env python3
"""
LinkedIn Angular-Aware Scraper

LinkedIn heavily uses Angular/JavaScript for dynamic content loading.
This scraper addresses that by:
1. Waiting for Angular to finish loading
2. Explicit waits for dynamic content
3. Multiple retry mechanisms for content that loads asynchronously
4. Network activity monitoring to ensure content is fully loaded
"""

import json
import time
import csv
import random
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

class LinkedInAngularScraper:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.output_dir = Path(self.config["output_settings"]["output_directory"])
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Set defaults for Angular scraping
        config.setdefault("scraping_settings", {})
        config["scraping_settings"].setdefault("headless", False)
        config["scraping_settings"].setdefault("wait_for_angular", True)
        config["scraping_settings"].setdefault("angular_timeout", 30)
        config["scraping_settings"].setdefault("content_load_timeout", 20)
        
        config.setdefault("output_settings", {})
        config["output_settings"].setdefault("output_directory", "outputs")
        config["output_settings"].setdefault("timestamp_format", "%Y%m%d_%H%M%S")
        
        return config

    def _setup_driver(self):
        """Setup Chrome driver optimized for Angular/JavaScript heavy sites"""
        opts = Options()
        
        # Anti-detection measures
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--no-sandbox")
        
        # JavaScript execution optimizations
        opts.add_argument("--disable-web-security")
        opts.add_argument("--allow-running-insecure-content")
        opts.add_argument("--disable-extensions")
        
        # Network optimizations for dynamic content
        opts.add_argument("--disable-background-timer-throttling")
        opts.add_argument("--disable-backgrounding-occluded-windows")
        opts.add_argument("--disable-renderer-backgrounding")
        
        if self.config["scraping_settings"]["headless"]:
            opts.add_argument("--headless=new")
        
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        
        # Anti-detection
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Longer timeouts for dynamic content
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(60)
        
        return driver

    def initialize_driver(self):
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, self.config["scraping_settings"]["content_load_timeout"])
        return True

    def login(self):
        """Login to LinkedIn"""
        print("🔐 Logging in to LinkedIn...")
        self.driver.get("https://www.linkedin.com/login")
        time.sleep(3)
        
        # Wait for login form to load
        self.wait.until(EC.presence_of_element_located((By.ID, "username")))
        
        username = self.driver.find_element(By.ID, "username")
        password = self.driver.find_element(By.ID, "password")
        
        creds = self.config["linkedin_credentials"]
        username.send_keys(creds["email"])
        password.send_keys(creds["password"])
        
        self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Wait for login to complete
        time.sleep(5)
        
        # Check if login was successful
        if any(k in self.driver.current_url for k in ("feed", "mynetwork", "jobs", "/in/", "messaging")):
            print("✅ Login successful!")
            return True
        else:
            print(f"❌ Login may have failed. Current URL: {self.driver.current_url}")
            return False

    def wait_for_angular(self):
        """Wait for Angular to finish loading and executing"""
        if not self.config["scraping_settings"]["wait_for_angular"]:
            return
            
        print("⏳ Waiting for Angular to load...")
        timeout = self.config["scraping_settings"]["angular_timeout"]
        
        # Wait for Angular to be defined
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return typeof window.angular !== 'undefined'")
            )
            print("✅ Angular detected")
        except TimeoutException:
            print("⚠️ Angular not detected, continuing anyway...")
        
        # Wait for Angular to finish bootstrapping
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("""
                    return window.angular && 
                           window.angular.element && 
                           window.angular.element(document).injector()
                """)
            )
            print("✅ Angular bootstrapped")
        except:
            print("⚠️ Could not confirm Angular bootstrap")
        
        # Wait for network activity to settle
        self.wait_for_network_idle()

    def wait_for_network_idle(self, idle_time=2):
        """Wait for network activity to settle (indicates content is loaded)"""
        print("🌐 Waiting for network activity to settle...")
        
        # Use performance API to check for network idle
        script = """
        return new Promise((resolve) => {
            let idleTimer;
            let lastActiveTime = Date.now();
            
            function checkIdle() {
                const entries = performance.getEntriesByType('resource');
                const recentEntries = entries.filter(entry => 
                    entry.responseEnd > Date.now() - 5000
                );
                
                if (recentEntries.length === 0) {
                    if (Date.now() - lastActiveTime >= arguments[0] * 1000) {
                        resolve(true);
                        return;
                    }
                } else {
                    lastActiveTime = Date.now();
                }
                
                setTimeout(checkIdle, 500);
            }
            
            checkIdle();
            
            // Fallback timeout
            setTimeout(() => resolve(true), 10000);
        });
        """
        
        try:
            self.driver.execute_async_script(script, idle_time)
            print("✅ Network idle detected")
        except:
            print("⚠️ Network idle detection failed, continuing...")
        
        # Additional wait for safety
        time.sleep(2)

    def wait_for_dynamic_content(self, selectors: List[str], timeout: int = 15):
        """Wait for specific dynamic content to appear"""
        print(f"🔄 Waiting for dynamic content: {selectors}")
        
        for selector in selectors:
            try:
                # Try both CSS and XPath selectors
                if selector.startswith("//"):
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                else:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                print(f"✅ Found: {selector}")
                return element
            except TimeoutException:
                print(f"⚠️ Timeout waiting for: {selector}")
                continue
        
        print("❌ No dynamic content selectors found")
        return None

    def extract_post_data_angular_aware(self, url: str) -> Dict[str, Any]:
        """Extract post data with Angular-aware techniques"""
        print(f"\n🚀 Scraping post (Angular-aware): {url}")
        
        # Navigate to post
        self.driver.get(url)
        
        # Wait for initial page load
        time.sleep(3)
        
        # Wait for Angular to load
        self.wait_for_angular()
        
        # Wait for key post elements to appear
        post_selectors = [
            "article",
            ".feed-shared-update-v2",
            ".main-feed-activity-card",
            "[data-test-id='main-feed-activity-card__commentary']"
        ]
        
        root_element = self.wait_for_dynamic_content(post_selectors, timeout=20)
        if not root_element:
            print("❌ Could not find post root element")
            return self._empty_post_data(url)
        
        print("✅ Post root element found, extracting data...")
        
        # Extract data with multiple attempts
        data = {
            "post_url": url,
            "scraped_at": datetime.now().isoformat(),
            "scraper_version": "angular-1.0",
        }
        
        # Extract author with retries
        data.update(self._extract_author_with_retries())
        
        # Extract post text with retries
        data["post_text"] = self._extract_post_text_with_retries()
        
        # Extract other elements
        data["date_posted"] = self._extract_date_with_retries()
        data["links"] = self._extract_links_with_retries()
        data["comments"] = self._extract_comments_with_retries()
        data["comment_count"] = len(data["comments"])
        
        return data

    def _extract_author_with_retries(self, max_attempts=3) -> Dict[str, str]:
        """Extract author with multiple attempts and selectors - focus on POST author, not commenters"""
        print("👤 Extracting POST author (with retries)...")
        
        # More specific selectors for POST author (exclude comment areas)
        author_selectors = [
            # Primary selectors for POST author in main feed card
            "article .base-main-feed-card__entity-lockup a[href*='/in/']:first-child",
            "article .feed-shared-actor__container-link",
            "article .feed-shared-actor__name a",
            
            # Specific data-tracking for post author (not comment author)
            "a[data-tracking-control-name='public_post_feed-actor-name']",
            
            # Main lockup container author (excludes comments)
            ".main-feed-activity-card__entity-lockup a[href*='/in/']",
            "[data-test-id='main-feed-activity-card__entity-lockup'] a[href*='/in/']",
        ]
        
        for attempt in range(max_attempts):
            print(f"  Attempt {attempt + 1}/{max_attempts}")
            
            for selector in author_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    print(f"    Checking {len(elements)} elements with selector: {selector}")
                    
                    for element in elements:
                        text = element.text.strip()
                        href = element.get_attribute("href")
                        
                        # Skip if this element is inside a comment section
                        try:
                            # Check if this element is inside a comment container
                            comment_ancestor = element.find_element(By.XPATH, "./ancestor::*[contains(@data-id, 'comment') or contains(@class, 'comment')]")
                            if comment_ancestor:
                                print(f"    Skipping {text} - inside comment section")
                                continue
                        except NoSuchElementException:
                            pass  # Good, not inside a comment
                        
                        if text and href and "/in/" in href:
                            # Clean up the author name (take only the first line)
                            author_name = text.split('\n')[0].strip()
                            
                            # Validate this looks like a real name (not a comment snippet)
                            if (len(author_name.split()) >= 2 and len(author_name) < 100 and
                                not any(skip in author_name.lower() for skip in [
                                    'comment', 'like', 'share', 'student at', 'followers'
                                ])):
                                
                                print(f"  ✅ Found POST author: {author_name}")
                                
                                # Try to get author title
                                author_title = self._extract_author_title_near_element(element)
                                
                                return {
                                    "post_author": author_name,
                                    "author_title": author_title,
                                    "author_profile_url": href
                                }
                            else:
                                print(f"    Rejected {author_name} - doesn't look like main author")
                                
                except Exception as e:
                    print(f"    Error with selector {selector}: {e}")
                    continue
            
            # Wait a bit before next attempt
            if attempt < max_attempts - 1:
                print(f"  ⏳ Waiting before retry...")
                time.sleep(2)
        
        print("  ❌ Could not extract POST author")
        return {"post_author": "", "author_title": "", "author_profile_url": ""}

    def _extract_author_title_near_element(self, author_element) -> str:
        """Extract author title/headline near the author name element"""
        try:
            # Look for title in nearby elements
            parent = author_element.find_element(By.XPATH, "./ancestor::div[contains(@class,'entity-lockup') or contains(@class,'actor')][1]")
            
            title_selectors = [
                ".text-body-small",
                ".update-components-actor__description", 
                "[class*='headline']",
                "p[class*='text-color-text-low-emphasis']"
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = parent.find_element(By.CSS_SELECTOR, selector)
                    title_text = title_elem.text.strip()
                    if title_text and len(title_text) < 200:
                        return title_text
                except:
                    continue
                    
        except Exception:
            pass
            
        return ""

    def _extract_post_text_with_retries(self, max_attempts=3) -> str:
        """Extract post text with multiple attempts and strategies"""
        print("📝 Extracting post text (with retries)...")
        
        # First, try to expand any "see more" buttons
        self._expand_post_content()
        
        text_selectors = [
            # Primary selectors for post content
            "[data-test-id='main-feed-activity-card__commentary']",
            ".feed-shared-text .attributed-text-segment-list__content",
            ".update-components-text span[dir='ltr']",
            
            # Fallback selectors
            ".attributed-text-segment-list__content",
            ".feed-shared-text",
            ".update-components-text",
            "div[data-test-id*='commentary'] p",
        ]
        
        for attempt in range(max_attempts):
            print(f"  Attempt {attempt + 1}/{max_attempts}")
            
            for selector in text_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 20:  # Substantial text
                            # Filter out obvious non-content
                            if not any(skip in text.lower() for skip in [
                                "like", "comment", "share", "• 1st", "• 2nd", "• 3rd",
                                "hours ago", "days ago", "weeks ago"
                            ]):
                                print(f"  ✅ Found post text: {text[:100]}...")
                                return text
                                
                except Exception:
                    continue
            
            # Wait before retry
            if attempt < max_attempts - 1:
                print(f"  ⏳ Waiting before retry...")
                time.sleep(3)
                self.wait_for_network_idle(1)  # Let more content load
        
        print("  ❌ Could not extract post text")
        return ""

    def _expand_post_content(self):
        """Try to expand any truncated post content"""
        expand_selectors = [
            "button[aria-label*='see more']",
            "button[aria-label*='more']",
            ".inline-show-more-text__button",
            "button[data-test-id='see-more-button']"
        ]
        
        for selector in expand_selectors:
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        button.click()
                        print(f"  ✅ Expanded content with: {selector}")
                        time.sleep(2)
                        return
            except Exception:
                continue

    def _extract_date_with_retries(self, max_attempts=2) -> str:
        """Extract date with retries"""
        date_selectors = ["time", "span[class*='time']", "[class*='timestamp']"]
        
        for attempt in range(max_attempts):
            for selector in date_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        # Try datetime attribute first
                        datetime_attr = element.get_attribute("datetime")
                        if datetime_attr:
                            return datetime_attr
                        
                        # Fallback to text content
                        text = element.text.strip()
                        if text and len(text) < 20 and any(char in text for char in ['h', 'd', 'w', 'ago']):
                            return text
                except Exception:
                    continue
            
            time.sleep(1)
        
        return ""

    def _extract_links_with_retries(self) -> List[str]:
        """Extract links from post content"""
        links = []
        try:
            # Look for links in post content area
            link_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href]")
            for link in link_elements:
                href = link.get_attribute("href")
                if href and href not in links:
                    # Include meaningful links (external or profile/company)
                    if (not href.startswith("https://www.linkedin.com") or 
                        "/in/" in href or "/company/" in href):
                        links.append(href)
        except Exception:
            pass
        
        return links

    def _extract_comments_with_retries(self) -> List[Dict[str, str]]:
        """Extract comments with retries"""
        print("💬 Extracting comments...")
        
        # Try to click comments to expand
        try:
            comment_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='comment']")
            if comment_buttons:
                comment_buttons[0].click()
                time.sleep(3)
                print("  ✅ Expanded comments")
        except Exception:
            print("  ⚠️ Could not expand comments")
        
        comments = []
        comment_selectors = [
            "article[data-id*='comment']",
            ".comments-comment-entity",
            "[class*='comment-entity']"
        ]
        
        for selector in comment_selectors:
            try:
                comment_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"  Found {len(comment_elements)} comment elements with {selector}")
                
                for comment_elem in comment_elements[:10]:  # Limit to 10 comments
                    comment_data = self._parse_comment_element(comment_elem)
                    if comment_data["commentor"] or comment_data["comment_text"]:
                        comments.append(comment_data)
                
                if comments:
                    break  # Found comments, don't try other selectors
                    
            except Exception as e:
                continue
        
        print(f"  ✅ Extracted {len(comments)} comments")
        return comments

    def _parse_comment_element(self, comment_elem) -> Dict[str, str]:
        """Parse individual comment element with improved extraction"""
        comment_data = {"commentor": "", "commentor_title": "", "comment_text": ""}
        
        try:
            full_text = comment_elem.text.strip()
            print(f"    Processing comment: {full_text[:100]}...")
            
            # Strategy 1: Try to find specific comment author elements
            try:
                # Look for author name link
                author_selectors = [
                    "a[data-tracking-control-name='public_post_comment_actor-name']",
                    ".comment__author a",
                    ".comments-comment-entity__author a",
                    "a[href*='/in/']:first-child"
                ]
                
                for selector in author_selectors:
                    try:
                        author_link = comment_elem.find_element(By.CSS_SELECTOR, selector)
                        author_name = author_link.text.strip()
                        if author_name and len(author_name) < 100:
                            comment_data["commentor"] = author_name
                            print(f"      Found commentor: {author_name}")
                            break
                    except:
                        continue
            except:
                pass
            
            # Strategy 2: Try to find comment title/headline
            try:
                title_selectors = [
                    ".comment__author-headline",
                    ".comments-comment-entity__author-headline", 
                    "p[class*='headline']",
                    "p[class*='text-color-text-low-emphasis']"
                ]
                
                for selector in title_selectors:
                    try:
                        title_elem = comment_elem.find_element(By.CSS_SELECTOR, selector)
                        title_text = title_elem.text.strip()
                        if title_text and len(title_text) < 200:
                            comment_data["commentor_title"] = title_text
                            print(f"      Found commentor title: {title_text}")
                            break
                    except:
                        continue
            except:
                pass
            
            # Strategy 3: Try to find comment text
            try:
                comment_text_selectors = [
                    ".comment__text",
                    ".comments-comment-entity__text",
                    "[class*='comment-text']",
                    "p.attributed-text-segment-list__content"
                ]
                
                for selector in comment_text_selectors:
                    try:
                        text_elem = comment_elem.find_element(By.CSS_SELECTOR, selector)
                        text_content = text_elem.text.strip()
                        if text_content and len(text_content) > 3:
                            comment_data["comment_text"] = text_content
                            print(f"      Found comment text: {text_content[:50]}...")
                            break
                    except:
                        continue
            except:
                pass
            
            # Fallback: Parse from full text if we didn't find structured elements
            if not comment_data["commentor"] or not comment_data["comment_text"]:
                if full_text:
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                    
                    # Heuristic parsing based on typical LinkedIn comment structure:
                    # Line 1: Commentor name
                    # Line 2: Followers/connections info (• 2,548 followers)
                    # Line 3: Time stamp (15h)
                    # Line 4+: Actual comment text
                    # Last lines: Like/Reply buttons
                    
                    if len(lines) >= 1 and not comment_data["commentor"]:
                        # First line is usually the commentor name
                        potential_name = lines[0]
                        if (len(potential_name) < 100 and 
                            not any(skip in potential_name.lower() for skip in [
                                'followers', 'connections', 'like', 'reply', 'ago'
                            ])):
                            comment_data["commentor"] = potential_name
                            print(f"      Fallback commentor: {potential_name}")
                    
                    # Look for comment text (skip metadata lines)
                    if not comment_data["comment_text"]:
                        for line in lines[1:]:  # Skip first line (name)
                            if (len(line) > 5 and 
                                not any(skip in line.lower() for skip in [
                                    '• 1st', '• 2nd', '• 3rd', 'followers', 'connections',
                                    'like', 'reply', 'share', 'hours ago', 'days ago', 'weeks ago'
                                ]) and
                                not (len(line) < 15 and any(char in line for char in ['h', 'd', 'w', 'm']))):
                                
                                # This looks like actual comment content
                                comment_data["comment_text"] = line
                                print(f"      Fallback comment text: {line[:50]}...")
                                break
        
        except Exception as e:
            print(f"    Error parsing comment: {e}")
            pass
            
        return comment_data

    def _empty_post_data(self, url: str) -> Dict[str, Any]:
        """Return empty post data structure"""
        return {
            "post_url": url,
            "scraped_at": datetime.now().isoformat(),
            "post_author": "",
            "author_title": "",
            "author_profile_url": "",
            "date_posted": "",
            "post_text": "",
            "links": [],
            "comment_count": 0,
            "comments": [],
            "scraper_version": "angular-1.0"
        }

    def save_results(self, data: Dict[str, Any]) -> str:
        """Save results to CSV and JSON"""
        ts = datetime.now().strftime(self.config["output_settings"]["timestamp_format"])
        
        # Save JSON
        json_path = self.output_dir / f"linkedin_post_angular_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Save CSV
        csv_path = self.output_dir / f"linkedin_post_angular_{ts}.csv"
        csv_row = {
            "post_url": data.get("post_url", ""),
            "post_author": data.get("post_author", ""),
            "author_title": data.get("author_title", ""),
            "author_profile_url": data.get("author_profile_url", ""),
            "date_posted": data.get("date_posted", ""),
            "post_text": data.get("post_text", ""),
            "links": "; ".join(data.get("links", [])),
            "comment_count": data.get("comment_count", 0),
            "comments": json.dumps(data.get("comments", []), ensure_ascii=False),
            "scraped_at": data.get("scraped_at", ""),
            "scraper_version": data.get("scraper_version", "")
        }
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_row.keys()))
            writer.writeheader()
            writer.writerow(csv_row)
        
        return str(csv_path)

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Angular-Aware Scraper")
    parser.add_argument("--url", action="append", required=True, help="LinkedIn post URL")
    parser.add_argument("--config", default="config.json", help="Config file path")
    args = parser.parse_args()

    scraper = LinkedInAngularScraper(config_path=args.config)
    scraper.initialize_driver()
    
    try:
        # Login
        if not scraper.login():
            print("❌ Login failed, exiting")
            return 1
        
        # Scrape each URL
        for url in args.url:
            print(f"\n" + "="*80)
            print(f"🎯 PROCESSING: {url}")
            print("="*80)
            
            data = scraper.extract_post_data_angular_aware(url)
            csv_file = scraper.save_results(data)
            
            print(f"\n📊 RESULTS:")
            print(f"✅ Saved: {csv_file}")
            print(f"📝 Author: {data.get('post_author', 'N/A')}")
            print(f"👤 Title: {data.get('author_title', 'N/A')}")
            print(f"📅 Date: {data.get('date_posted', 'N/A')}")
            print(f"📄 Post Text Length: {len(data.get('post_text', ''))} chars")
            print(f"💬 Comments: {data.get('comment_count', 0)}")
            print(f"🔗 Links: {len(data.get('links', []))}")
            
            if data.get('post_text'):
                print(f"\n📝 POST TEXT PREVIEW:")
                print(f"'{data['post_text'][:200]}{'...' if len(data['post_text']) > 200 else ''}'")
            
            print("\n" + "-"*80)
        
        return 0
        
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        scraper.close_driver()

if __name__ == "__main__":
    import os
    if not os.path.exists("config.json"):
        print("❌ config.json missing. Create it first.")
        exit(1)
    exit(main())
