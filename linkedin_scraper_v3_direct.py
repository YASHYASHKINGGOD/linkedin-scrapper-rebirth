#!/usr/bin/env python3
"""
LinkedIn Scraper V3 - Direct Approach

New strategy based on debug findings:
1. REMOVE comment filtering from post content extraction entirely
2. Use direct, specific selectors for post content
3. Separate post and comment extraction completely
4. Focus on elements we KNOW contain the post text

Based on debug evidence:
- p[data-test-id='main-feed-activity-card__commentary'] contains the post text
- Current scraper fails because it thinks this is inside a comment
- Solution: Extract post content DIRECTLY without ancestor checking
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
import argparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger("linkedin-scraper-v3-direct")


class LinkedInDirectScraper:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None

        self.output_dir = Path(self.config["output_settings"]["output_directory"])
        self.output_dir.mkdir(exist_ok=True, parents=True)

    # ---------- Setup ----------
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # defaults
        config.setdefault("chrome_options", {})
        config["chrome_options"].setdefault(
            "disable_automation_flags",
            [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        config["chrome_options"].setdefault(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        )
        config["chrome_options"].setdefault("window_size", [1366, 900])

        config.setdefault("scraping_settings", {})
        config["scraping_settings"].setdefault("headless", False)
        config["scraping_settings"].setdefault("implicit_wait_timeout", 5)
        config["scraping_settings"].setdefault("page_load_timeout", 45)
        config["scraping_settings"].setdefault("explicit_wait_timeout", 20)
        config["scraping_settings"].setdefault("random_delay_range", [0.7, 1.4])

        config.setdefault("output_settings", {})
        config["output_settings"].setdefault("output_directory", "outputs")
        config["output_settings"].setdefault("timestamp_format", "%Y%m%d_%H%M%S")
        return config

    def _setup_chrome_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        for flag in self.config["chrome_options"]["disable_automation_flags"]:
            chrome_options.add_argument(flag)
        ua = self.config["chrome_options"]["user_agent"]
        chrome_options.add_argument(f"--user-agent={ua}")
        w, h = self.config["chrome_options"]["window_size"]
        chrome_options.add_argument(f"--window-size={w},{h}")
        if self.config["scraping_settings"]["headless"]:
            chrome_options.add_argument("--headless=new")

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(self.config["scraping_settings"]["implicit_wait_timeout"])
        driver.set_page_load_timeout(self.config["scraping_settings"]["page_load_timeout"])
        return driver

    def _random_delay(self, lo=None, hi=None):
        if lo is None or hi is None:
            lo, hi = self.config["scraping_settings"]["random_delay_range"]
        time.sleep(random.uniform(lo, hi))

    def initialize_driver(self):
        self.driver = self._setup_chrome_driver()
        self.wait = WebDriverWait(self.driver, self.config["scraping_settings"]["explicit_wait_timeout"])
        return True

    def login(self) -> Tuple[bool, str]:
        self.driver.get("https://www.linkedin.com/login")
        self._random_delay()
        user = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
        pw = self.wait.until(EC.presence_of_element_located((By.ID, "password")))
        creds = self.config["linkedin_credentials"]
        user.clear(); user.send_keys(creds["email"])
        pw.clear(); pw.send_keys(creds["password"])
        self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
        self._random_delay(2, 3.2)
        if any(k in self.driver.current_url for k in ("feed", "mynetwork", "jobs", "/in/", "messaging")):
            return True, "Login successful"
        return False, f"Login failed or verification needed: {self.driver.current_url}"

    def verify_login_status(self):
        return any(k in self.driver.current_url for k in ("feed", "mynetwork", "jobs", "/in/", "messaging"))

    # ---------- Direct Content Extraction (No Comment Filtering) ----------
    def _expand_post_content(self):
        """Expand any 'See more' content in the post"""
        show_more_selectors = [
            "button[aria-label*='more']",
            "button[aria-label*='see more']", 
            "button[data-test-id='see-more-button']",
        ]
        
        for sel in show_more_selectors:
            btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                if btn.is_displayed() and btn.is_enabled():
                    try:
                        btn.click()
                        print(f"✅ Expanded content with: {sel}")
                        time.sleep(2)
                        return  # Only click one
                    except Exception as e:
                        print(f"⚠️ Failed to click {sel}: {e}")
                        continue

    def _extract_post_content_direct(self) -> str:
        """
        DIRECT approach: Extract post content without any comment filtering
        Based on debug findings, these selectors contain the actual post text
        """
        print("\n🔍 DIRECT POST CONTENT EXTRACTION")
        
        # First, try to expand content
        self._expand_post_content()
        
        # Direct selectors that we KNOW contain post content based on debug
        direct_post_selectors = [
            # Primary selector that worked in debug
            "p[data-test-id='main-feed-activity-card__commentary']",
            
            # Alternative selectors for different post types
            "div[data-test-id='main-feed-activity-card__commentary']",
            "[data-test-id='main-feed-activity-card__commentary']",
            
            # Traditional selectors for standard feed posts
            ".feed-shared-update-v2__commentary .attributed-text-segment-list__content",
            ".feed-shared-text .attributed-text-segment-list__content",
            ".update-components-text .attributed-text-segment-list__content",
        ]
        
        extracted_texts = []
        
        for i, selector in enumerate(direct_post_selectors, 1):
            print(f"{i}. Testing selector: {selector}")
            
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"   Found {len(elements)} elements")
                
                for j, element in enumerate(elements, 1):
                    try:
                        # Get text using multiple methods
                        text_methods = [
                            ("innerText", lambda el: el.get_attribute("innerText")),
                            ("textContent", lambda el: el.get_attribute("textContent")), 
                            (".text", lambda el: el.text)
                        ]
                        
                        for method_name, method_func in text_methods:
                            try:
                                text = method_func(element)
                                if text and text.strip():
                                    text = text.strip()
                                    if len(text) > 20:  # Substantial text
                                        print(f"   Element {j} ({method_name}): '{text[:100]}{'...' if len(text) > 100 else ''}'")
                                        if text not in extracted_texts:
                                            extracted_texts.append(text)
                                        break  # Found text, move to next element
                            except Exception as e:
                                print(f"   Element {j} ({method_name}): Error - {e}")
                                continue
                    except Exception as e:
                        print(f"   Element {j}: Error - {e}")
                        continue
                        
            except Exception as e:
                print(f"   Selector error: {e}")
                continue
        
        # Process and clean extracted texts
        if extracted_texts:
            print(f"\n✅ Found {len(extracted_texts)} text blocks")
            
            # Join all texts and clean
            full_text = "\n\n".join(extracted_texts).strip()
            
            # Basic cleaning
            lines = full_text.split('\n')
            clean_lines = []
            
            for line in lines:
                line = line.strip()
                # Skip empty lines and obvious metadata
                if line and not any(skip in line.lower() for skip in [
                    '• 3rd+', '• 2nd', '• 1st', 'followers', 'connections',
                    'like this', 'repost this', 'send this', 'share this',
                    'hours ago', 'days ago', 'minutes ago', 'weeks ago'
                ]):
                    clean_lines.append(line)
            
            final_text = '\n'.join(clean_lines).strip()
            print(f"📝 Final extracted text ({len(final_text)} chars): {final_text[:200]}...")
            return final_text
        else:
            print("❌ No post content found with direct selectors")
            return ""

    def _extract_author_info(self) -> Dict[str, str]:
        """Extract author information"""
        print("\n👤 EXTRACTING AUTHOR INFO")
        
        author_info = {"post_author": "", "author_title": "", "author_profile_url": ""}
        
        # Look for author profile links
        profile_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
        print(f"Found {len(profile_links)} profile links")
        
        for i, link in enumerate(profile_links[:5], 1):  # Check first 5
            try:
                text = link.text.strip()
                href = link.get_attribute("href")
                
                print(f"Link {i}: '{text}' -> {href}")
                
                # Look for meaningful author names (not empty, reasonable length)
                if text and 5 <= len(text) <= 100:
                    # Extract just the name (first line)
                    name = text.split('\n')[0].strip()
                    if name and not any(skip in name.lower() for skip in [
                        'see more', 'like', 'comment', 'share', 'follow', 'connect'
                    ]):
                        author_info["post_author"] = name
                        author_info["author_profile_url"] = href
                        print(f"✅ Selected author: {name}")
                        break
            except Exception as e:
                print(f"Link {i}: Error - {e}")
        
        # Look for author title/description
        title_selectors = [
            "p.text-color-text-low-emphasis",
            ".feed-shared-actor__description", 
            ".feed-shared-actor__sub-description",
            "p[class*='text-low-emphasis']"
        ]
        
        for selector in title_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    text = el.text.strip()
                    # Look for job titles (not timestamps)
                    if text and len(text) < 200 and not any(skip in text.lower() for skip in [
                        'ago', 'hour', 'day', 'week', 'month', 'min'
                    ]):
                        author_info["author_title"] = text
                        print(f"✅ Found title: {text}")
                        break
                if author_info["author_title"]:
                    break
            except Exception:
                continue
        
        return author_info

    def _extract_metadata(self) -> Dict[str, str]:
        """Extract post metadata like timestamp"""
        print("\n📅 EXTRACTING METADATA")
        
        # Look for time elements
        try:
            time_elem = self.driver.find_element(By.CSS_SELECTOR, "time")
            date_posted = time_elem.get_attribute("datetime") or time_elem.text.strip()
            print(f"✅ Found timestamp: {date_posted}")
            return {"date_posted": date_posted}
        except NoSuchElementException:
            # Look for timestamp-like text in spans
            for span in self.driver.find_elements(By.CSS_SELECTOR, "span"):
                text = span.text.strip()
                if text and len(text) < 20 and ('h' in text or 'd' in text or 'w' in text or 'ago' in text):
                    print(f"✅ Found timestamp: {text}")
                    return {"date_posted": text}
            
            print("❌ No timestamp found")
            return {"date_posted": ""}

    def _extract_links(self) -> List[str]:
        """Extract links from the post"""
        links = []
        for a in self.driver.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = a.get_attribute("href")
            if href and href not in links:
                # Include external links and meaningful LinkedIn links
                if not href.startswith('https://www.linkedin.com') or '/in/' in href or '/company/' in href:
                    links.append(href)
        return links

    def _extract_comments_simple(self, limit=10) -> List[Dict[str, str]]:
        """Simple comment extraction - separate from post content"""
        print(f"\n💬 EXTRACTING COMMENTS (limit={limit})")
        
        # Try to click comments to expand
        try:
            comment_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='comment']")
            if comment_buttons:
                print(f"Found {len(comment_buttons)} comment buttons")
                comment_buttons[0].click()
                time.sleep(3)
                print("✅ Comments expanded")
        except Exception as e:
            print(f"⚠️ Could not expand comments: {e}")
        
        comments = []
        
        # Look for comment containers
        comment_selectors = [
            "article[data-id*='comment']",
            ".comment",
            "[class*='comment-container']"
        ]
        
        for selector in comment_selectors:
            comment_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"Found {len(comment_elements)} comment elements with {selector}")
            
            for i, comment_el in enumerate(comment_elements[:limit]):
                try:
                    full_text = comment_el.text.strip()
                    if len(full_text) < 20:
                        continue
                    
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                    
                    # Simple extraction: first meaningful line as author, look for comment text
                    commentor = ""
                    comment_text = ""
                    
                    if lines:
                        # First line is usually the commentor
                        potential_author = lines[0]
                        if len(potential_author) < 100:
                            commentor = potential_author
                    
                        # Look for comment text (skip metadata lines)
                        for line in lines[1:]:
                            if (len(line) > 5 and 
                                not any(skip in line.lower() for skip in [
                                    '• 1st', '• 2nd', '• 3rd', 'followers', 'connections',
                                    'like', 'reply', 'share'
                                ]) and
                                not (len(line) < 15 and any(char in line for char in ['h', 'd', 'w', 'm']))):
                                comment_text = line
                                break
                    
                    if commentor or comment_text:
                        comments.append({
                            "commentor": commentor,
                            "comment_text": comment_text[:300]  # Limit length
                        })
                        print(f"✅ Comment {len(comments)}: '{commentor}' - '{comment_text[:50]}...'")
                    
                except Exception as e:
                    print(f"❌ Error processing comment {i}: {e}")
                    continue
            
            if comments:  # If we found comments with this selector, don't try others
                break
        
        print(f"📊 Total comments extracted: {len(comments)}")
        return comments

    # ---------- Main Scraping ----------
    def scrape_post(self, url: str) -> Dict[str, Any]:
        """Main scraping method using direct approach"""
        print(f"\n🚀 SCRAPING POST: {url}")
        
        self.driver.get(url)
        self._random_delay(2, 4)
        
        # Wait for page to load
        self.wait.until(EC.any_of(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article")),
            EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
        ))
        
        # Extract all components
        data = {
            "post_url": url,
            "scraped_at": datetime.now().isoformat(),
            "scraper_version": "3.0-direct",
        }
        
        # Direct extraction without comment filtering
        data.update(self._extract_author_info())
        data.update(self._extract_metadata())
        data["post_text"] = self._extract_post_content_direct()
        data["links"] = self._extract_links()
        data["comments"] = self._extract_comments_simple(limit=20)
        
        return data

    # ---------- Save Results ----------
    def save_csv(self, post_data: Dict[str, Any]) -> str:
        """Save results to CSV"""
        ts = datetime.now().strftime(self.config["output_settings"]["timestamp_format"])
        csv_path = self.output_dir / f"linkedin_post_v3_{ts}.csv"
        
        # Convert comments to JSON
        comments_json = []
        for comment in (post_data.get("comments") or []):
            comments_json.append({
                "commentor": comment.get("commentor", ""),
                "comment": comment.get("comment_text", "")
            })
        
        # Create CSV row
        row_data = {
            "post_url": post_data.get("post_url", ""),
            "post_author": post_data.get("post_author", ""),
            "author_title": post_data.get("author_title", ""),
            "author_profile_url": post_data.get("author_profile_url", ""),
            "date_posted": post_data.get("date_posted", ""),
            "post_text": post_data.get("post_text", ""),
            "links": "; ".join(post_data.get("links", []) or []),
            "comment_count": len(post_data.get("comments") or []),
            "comments": json.dumps(comments_json, ensure_ascii=False),
            "scraped_at": post_data.get("scraped_at", ""),
            "scraper_version": post_data.get("scraper_version", ""),
        }
        
        # Write CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row_data.keys()))
            writer.writeheader()
            writer.writerow(row_data)
        
        return str(csv_path)

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="LinkedIn post URL")
    parser.add_argument("--config", default="config.json", help="Config file path")
    args = parser.parse_args()

    scraper = LinkedInDirectScraper(config_path=args.config)
    scraper.initialize_driver()
    
    ok, msg = scraper.login()
    if not ok:
        print("❌ Login failed:", msg)
        scraper.close_driver()
        return 1

    try:
        data = scraper.scrape_post(args.url)
        csv_file = scraper.save_csv(data)
        
        print(f"\n✅ SCRAPING COMPLETE!")
        print(f"📁 Saved: {csv_file}")
        print(f"\n📊 RESULTS SUMMARY:")
        print(f"📝 Author: {data.get('post_author', 'N/A')}")
        print(f"👤 Title: {data.get('author_title', 'N/A')}")
        print(f"📅 Date: {data.get('date_posted', 'N/A')}")
        print(f"📄 Post Text: {len(data.get('post_text', ''))} characters")
        print(f"💬 Comments: {len(data.get('comments', []))}")
        print(f"🔗 Links: {len(data.get('links', []))}")
        
        # Show first 200 chars of post text
        post_text = data.get('post_text', '')
        if post_text:
            print(f"\n📝 POST TEXT PREVIEW:")
            print(f"'{post_text[:200]}{'...' if len(post_text) > 200 else ''}'")
        
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        scraper.close_driver()
    
    return 0

if __name__ == "__main__":
    if not os.path.exists("config.json"):
        print("❌ config.json missing. Example:")
        print(json.dumps({
            "linkedin_credentials": {"email": "you@example.com", "password": "YOUR_PASSWORD"},
            "chrome_options": {},
            "scraping_settings": {"headless": False},
            "output_settings": {"output_directory": "outputs", "timestamp_format": "%Y%m%d_%H%M%S"}
        }, indent=2))
        exit(1)
    exit(main())
